# -*- coding: utf-8 -*-
import re
import os
import django
import scrapy
import requests
import json
import datetime
from os import sys, path
from scrapy.selector import Selector

sys.path.append(path.dirname(path.dirname(path.dirname(path.dirname(path.abspath(__file__))))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homedepot_site.settings")
django.setup()

from product.models import *
from product.views import *

class HomedepotSpider(scrapy.Spider):
    name = "homedepot"

    custom_settings = {
        'USER_AGENT': 'homedepot_scraper (+http://www.yourdomain.com)',
    }

    def __init__(self, task_id):
        self.task = ScrapyTask.objects.get(id=int(task_id))

        if self.task.mode == 1:
            set_old_category_products(self.task.category)
            if self.task.category.url == '/':
                self.categories = get_subcategories()
                self.excludes = [item.url for item in Product.objects.all()]
            else:
                self.categories = [self.task.category.url]
                self.excludes = get_category_products(self.categories[0])
        elif self.task.mode == 2:
            self.products = Product.objects.filter(id__in=get_ids(self.task.products))

    def start_requests(self):    
        if self.task.mode == 1:
            cate_requests = []
            for item in self.categories:
                request = scrapy.Request('http://www.homedepot.com'+item,
                                         callback=self.parse)
                request.meta['category'] = item
                # request.meta['proxy'] = 'http://'+random.choice(self.proxy_pool)
                cate_requests.append(request)
            return cate_requests
        else:
            product_requests = []
            for product in self.products:
                request = scrapy.Request(product.url, 
                                         callback=self.detail)
                request.meta['model_num'] = product.special
                request.meta['category'] = product.category_id
                product_requests.append(request)
            return product_requests    

    def closed(self, reason):
        self.update_run_time()
        self.store_report()

    def parse(self, response):
        if self.stop_scrapy():
            return

        products = response.css('div.pod-plp__container div.pod-inner')
        cates_url = response.css('ul.activeLevel li a::attr(href)').extract() or \
                      response.css('ul.list li.list__item--padding-none a::attr(href)').extract()        
        cates_title = response.css('ul.activeLevel li a::text').extract() or \
                        response.css('ul.list li.list__item--padding-none a::text').extract()
 
        if products:
            for product in products:
                detail = product.css('div.plp-pod__image a::attr(href)').extract_first()                
                detail = 'http://www.homedepot.com'+detail
                if not detail in self.excludes:
                    category = response.url.split('http://www.homedepot.com')[1]
                    request = scrapy.Request(detail, callback=self.detail)
                    request.meta['category'] = category
                    yield request

            # for other pages / pagination
            offset = response.meta.get('offset', 0)
            total_records = response.meta.get('total_records', self.get_total_records(response))
            
            if offset + 24 < total_records:
                offset += 24
                base_url = response.url.split('?')[0]
                next_url = base_url+'?Nao={}'.format(offset)
                request = scrapy.Request(next_url, callback=self.parse)
                request.meta['offset'] = offset
                request.meta['total_records'] = total_records
                yield request

        elif cates_url:
            parent = response.meta['category']
            for item in zip(cates_url, cates_title):
                url = item[0].split('?')[0]
                if self.is_category(url):
                    cate_ = '/{}/'.format(url.split('/')[2])
                    if not Category.objects.filter(url__contains=cate_):
                        Category.objects.create(parent_id=parent, url=url, title=item[1])

                        request = scrapy.Request('http://www.homedepot.com'+url, callback=self.parse)
                        request.meta['category'] = url
                        # request.meta['proxy'] = 'http://'+random.choice(self.proxy_pool)
                        yield request

    def is_category(self, cate_str):
        if not cate_str.startswith('/b/'):
            return False        
        return cate_str.count("/")

    def get_total_records(self, response):
        total_records = response.css('div[id=allProdCount]::text').extract_first()
        return int(total_records.replace(',', ''))

    def get_url_id(self, url):
        return url

    def detail(self, response):
        pid = response.css('span[id=product_internet_number]::text').extract_first()
        quantity = self.get_real_quantity(pid)
        
        special = response.css('h2.modelNo::text').extract_first().replace('\n', '').strip()
        brand = response.css('h2.product-title__brand::text').extract_first() or ''
        brand = re.sub(r'\s+', ' ', brand).strip()

        price = response.css('input[id=ciItemPrice]::attr(value)').extract_first()
        if price:
            price = '$' + price
        else:
            price = ''

        item = {
            'id': pid,
            'title': response.css('h1.product-title__title::text').extract_first(),
            'price': price,
            'picture': response.xpath("//img[@id='mainImage']/@src").extract_first(),
            'rating': response.css('span[itemprop=ratingValue]::text').extract_first() or 0,
            'review_count': response.css('span[itemprop=reviewCount]::text').extract_first() or 0,
            'promo': response.css('div.product_promo_ctn a span::text').extract_first(),
            'category_id': response.meta['category'].split('?')[0],
            'delivery_time': '',
            'bullet_points': '\n'.join(response.css('div.buybox li::text').extract()),
            'details': 'Brand: '+brand,
            'quantity': quantity,
            'min_quantity': 1,
            'special': special,
            'url': self.get_url_id(response.url)
        }        

        try:
            Product.objects.update_or_create(id=item['id'], defaults=item)
        except Exception, e:
            pass

        yield item        

    def get_real_quantity(self, pid):
        url = 'https://secure2.homedepot.com/TouchWebServices/v2/Cart'
        header = {
            'Content-Type': 'application/json', 
            'Accept': 'application/json; charset=utf-8',
            'Cookie': "THD_CACHE_NAV_PERSIST=; THD_SESSION=; MYLIST_ON=true; MYLIST_THROTTLE=true; HD_DC=origin; AMCVS_F6421253512D2C100A490D45%40AdobeOrg=1; THD_GLOBAL=238e7e4c-e8ce-18c0-9678-00e0ed452d44; THD_CACHE_NAV_SESSION=C20%7e8119%5f%7eC20%5fEXP%7e%5f%7eC22%7e1710%5f%7eC22%5fEXP%7e%5f%7eC26%7eNone%5f%7eC26%5fEXP%7e; WCSSESSIONID=0000Uy7jhrlW13on0NKbZNBZlWu:16826g0rg; WC_SESSION_ESTABLISHED=true; WC_PERSISTENT=V4FQ%2fCefHXdfMq8Sa%2biA2yASAz4%3d%0a%3b2017%2d04%2d14+04%3a41%3a18%2e043%5f1492159278031%2d16769%5f10051%5f1295601165%2c%2d1%2cUSD%5f10051; WC_AUTHENTICATION_1295601165=1295601165%2cGaodGTE1%2fA5URtV%2ftg7VVnT1nQs%3d; WC_ACTIVEPOINTER=%2d1%2c10051; WC_USERACTIVITY_1295601165=1295601165%2c10051%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cAegA%2bHK6OMWS6t7zVicCqhC0hDp4TQcR25hoZSiYJhXA695F6vlPR4p%2fevIMxTzJR6cZIbwSaoTenXnzyH%2fxkKIM5M%2fCsgQzXZrgbQs43oqCfkNu4IhYSMNzA9ILy3ujJEal4SgJPm%2fsqqJhUT0LWfcAAaH9XplMAiIf0u3kYaW7dGHIhqnrtibjRDAcYBI%2fIG9hsXnFHGHM3ghqx52P8A%3d%3d; THD_AUR_DATA=A1%3dM%3a%3bA1%5fEXP%3d1543999295; _px=TF3rhZiJqVt+P5uWudfqlgqSRnEh7UV0i38aYVYFQMfEDHrUIaGsut12fjU8/6yexmxa2X9AP0Shh5sc1rdy2w==:1000:t2HLx0nOEHUyQq0C7prjROsF8MwjDgM9ztvX7jMNnwbi0zn0xSF3PHgJQhJCJNNHVMyuMznCZ3L9Uu+F3/BWt5QVSZr34WxzNUZsLMnUc4oNBPXQFzWOoQuK/Gtz9lsUADLGdyNxetWAA15l3WonV/2OTk/dt+KO8JokreSQH9Auf1gWh+psN38fmr7fHJsGx4dq1RC9YPuLM5kMLJdpYE9mzhfAj3qx0oNZgxZ9P69jI+h2CIB8X0ETVmXUSAESjn+/z1MZg92VHx7m9gMBLQ==; AUR_THROTTLE=false; BTT_X0siD=836231371856423181; BTT_Collect=on; aam_uuid=57659781849465682731514073052420490991; BTT_WCD_Collect=off; mbox=PC#1491864512485-621916.22_13#1493368889|session#1492157623725-583703#1492161149|check#true#1492159349; _ga=GA1.2.1790066098.1491864515; _br_uid_2=uid%3D1462990138455%3Av%3D12.0%3Ats%3D1491864515617%3Ahc%3D22; RES_TRACKINGID=663160305310734; ResonanceSegment=; RES_SESSIONID=111326964704127; WRUID15d=1176399248515136; __CT_Data=gpv=22&apv_4_www23=22&cpv_4_www23=21&rpv_4_www23=20; AMCV_F6421253512D2C100A490D45%40AdobeOrg=-227196251%7CMCIDTS%7C17270%7CMCMID%7C57926169955742438761541442187989903514%7CMCAAMLH-1492469312%7C3%7CMCAAMB-1492764090%7CNRX38WO0n5BH8Th-nqAG_A%7CMCOPTOUT-1492166490s%7CNONE%7CMCAID%7CNONE%7CMCCIDH%7C-1607610227; CT_LOC_STORE=null; CT_THD_FORCE_LOC=null; ctRefUrl=http://www.homedepot.com/p/Stiebel-Eltron-CKT-15E-Wall-Mounted-Electric-Fan-Heater-with-Timer-CKT-15E/204091962; _4c_=fVLdThs9EH2VyhdcZXc9Xv9GQlVIQ%2Ft9LVCaVFyi%2FXGIxWYdeR22Fcq7Mw5QCVR1b9Yz53g8c%2BY8knFjezIFbhgIwwyTwCfk3v4eyPSRBNem3wOZEllpVRqjzNoIa1urSl4zRWsjlC5lrcmE%2FDrWMZJTAUIbOExI69pv%2Fu78%2B2sVeEeTjHOkNbsXwiPZhw55mxh306IYxzHf%2BC0%2Bt%2FMxb%2Fy22BXL6Gxtu2zRxeD7bP51lYFYZDdV12UXft9H2yJmmxhck51XffbFVtGGbHRxk63cFo8vdwpGOTVgJMOu1vtu7bpuGX2w%2F33CFjC324dmUw0Wo0sMaxsrPPrg7lyP8bxzzf2q6uzP4wUAJVEhxjWOD6VExlm3t6vgqv6us7dLOwzO90euLlECrRmqANpwgKQfdrlF2dPLdfDjYAMG801AAT4IhVmf0BvXtwhiGOzahnBkYTS4mBp9IxemG9%2BmNJi8zFn2kJdpVpSbgDKUSkmNzrEX0JJj2wheXax%2B3J4tZvOry5dFDLiJYayG5t0u6mIYij%2BpXfBtAbT4f5lBLotBsJJqjQ8wKsF8nF2fncLJ1rWnQiWXSWOEUJzxUisJggPnDLQy2hhaCuAns%2BvFabLLLvmGpRV1vkGxMULHTsjn2e2z7H%2BdA031xmelTD5LtY4%2BY%2Bw9rhTiz7L%2Fi2VSFXToEaevMAPFKJNS44UYEcZpaPoOh8MT; LPCKEY-31564604=387a73ae-6552-4157-be01-57e1eafbdaca3-10787%7Cnull%7Cnull%7C40; LPVID=UyMmJkYjY5Y2FjYjhkYTM2; LPSID-31564604=1IjkRXqKRmmkXIM_JRJDfg; MCC_ACC=C1%3DWCS; cart_activity=1295601165; X-hostname=central1-b-g-9fhz; THD_PERSIST=C4%3d1710%2bGuam%2520%2d%2520Tamuning%20%2d%20Tamuning%2c%20GU%2b%3a%3bC4%5fEXP%3d1543999333%3a%3bC5%3d7000000000002081190%3a%3bC5%5fEXP%3d1543999333%3a%3bC6%3d%7b%22I1%22%3a%220%22%7d%3a%3bC6%5fEXP%3d1494751333%3a%3bC24%3d96913%3a%3bC24%5fEXP%3d1543999333%3a%3bC25%3dcpaisa8l%2ehomedepot%2ecom%2fWC%5fTHD%2f1492159278032%3a%3bC25%5fEXP%3d1543999333%3a%3bC34%3d1%2e1%2d2%2e1%2d3%2e0%2d4%2e0%2d5%2e0%2d6%2e1%2d7%2e1%2d8%2e1%2d9%2e1%2d10%2e1%2d11%2e1%2d12%2e0%2d13%2e0%2d14%2e0%2d15%2e1%2d18%2e1%2d19%2e1%2d20%2e1%2d21%2e1%2d22%2e1%2d23%2e1%2d26%2e1%2d27%2e1%2d28%2e1%2d29%2e1%2d30%2e0%2d32%2e1%2d35%2e0%2d39%2e1%2d40%2e1%2d50%2e0%2d60%2e0%3a%3bC34%5fEXP%3d1492245733%3a%3bC40%3dC%3a%3bC40%5fEXP%3d1543999333%3a%3bC43%3d1295601165%3a%3bC43%5fEXP%3d1543999333%3a%3bC44%3dWS%5fgBjgLGyGEAkUwaT7yN25cOlRGcvlvuRI2bRgMWEbpniHcDR2N7XDVKQqHN4py1bTqt7DvzH68LiCNS0zvdXzFm2IY8z5to%252FRIJfFCxsVlSYRiSrvjrBcQyKYhnUSXSW4R4yhJFHG3tp980nm1PIPrv4jR27c6n9c1qL8uyH8UK8%253D%3a%3bC44%5fEXP%3d1543999333%3a%3bC45%3dWS%5f15vK28FOVupF05knsD1ZC%252FhYo8%252BHET5UEZ3mrkL8QKtkS7IIyQwzeEDAYAFh%252BxpSwaeMVtjP%252BWh06kB2R6o0HAIwGr2AM8eZUR3yX0qqabF9uPVIWxMNs2eKxoukvjOlBHQCg7Lv9KLIe92M1Av4cUgswrUJv5dDAlkENZ0EPqo%253D%3a%3bC45%5fEXP%3d1543999333%3a%3bC46%3dguest%3a%3bC46%5fEXP%3d1543999333; s_pers=%20productnum%3D10%7C1494750163729%3B%20pfm%3Dbrowse%7C1494750163730%3B%20s_nr%3D1492159321556-Repeat%7C1523695321556%3B%20s_dslv%3D1492159321560%7C1586767321560%3B%20s_dslv_s%3DLess%2520than%25201%2520day%7C1492161121560%3B; aam_uuid=57659781849465682731514073052420490991; MCC_THROTTLE=true; ctm={'pgv':6275246367873713|'vst':6547356517520367|'vstr':2433034502882207|'intr':1492159467680|'v':1|'lvst':372}; s_sess=%20stsh%3D%3B%20s_pv_pName%3Dproductdetails%253E204091962%3B%20s_pv_pType%3Dpip%3B%20s_pv_cmpgn%3D%3B%20s_cc%3Dtrue%3B%20s_sq%3Dhomedepotprod%253D%252526c.%252526a.%252526activitymap.%252526page%25253Dhttp%2525253A%2525252F%2525252Fwww.homedepot.com%2525252Fp%2525252FLasko-23-in-1500-Watt-Ceramic-Tower-Heater-with-Digital-Display-and-Remote-Control-755320%2525252F100669066%252526link%25253DAdd%25252520to%25252520Cart%252526region%25253Dbuybelt%252526.activitymap%252526.a%252526.c%252526pid%25253Dhttp%2525253A%2525252F%2525252Fwww.homedepot.com%2525252Fp%2525252FLasko-23-in-1500-Watt-Ceramic-Tower-Heater-with-Digital-Display-and-Remote-Control-755320%2525252F100669066%252526oid%25253DAdd%25252520to%25252520Cart%2525250A%252526oidt%25253D3%252526ot%25253DSUBMIT%3B"
        }

        body = {"CartRequest":{"itemDetails":[{"itemId":pid,"quantity":"999","fulfillmentLocation":"DirectShip","fulfillmentMethod":"ShipToHome"}]}}

        res = requests.post(url=url, headers=header, data=json.dumps(body))
        CartModel = res.json().get("CartModel")
        
        if 'orderId' in CartModel.keys():
            return 999

        try:
            quantity = CartModel['errorModel'][0]
            if 'inventory' in quantity.keys():
                quantity = quantity['inventory']
                if quantity:
                    quantity = int(quantity)
                else:
                    quantity = 0
            else:
                quantity = 10
        except Exception, e:
            print '=============== 1 ==============', str(res.json())
            print '=============== 2 ==============',str(e)
            return '9999'
        return quantity

    def update_run_time(self):
        self.task.last_run = datetime.datetime.now()
        self.task.status = 2 if self.task.mode == 2 else 0       # Sleeping / Finished
        self.task.update()

    def store_report(self):
        if self.task.mode == 1:
            result = []
            for cate in self.task.category.get_all_children():
                # only for new products
                for item in Product.objects.filter(category=cate, 
                                                   is_new=True):
                    result.append(item)
        else:
            result = Product.objects.filter(id__in=get_ids(self.task.products))

        fields = [f.name for f in Product._meta.get_fields() 
                  if f.name not in ['updated_at', 'is_new']]

        date = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        path = '/home/exports/homedepot-{}-{}.csv'.format(self.task.title, date)
        write_report(result, path, fields)

    def stop_scrapy(self):
        st = ScrapyTask.objects.filter(id=self.task.id).first()
        return not st or st.status == 3
