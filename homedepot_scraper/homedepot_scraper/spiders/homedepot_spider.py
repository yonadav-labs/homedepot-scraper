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
        # 'DOWNLOAD_DELAY': 1,
        # 'AUTOTHROTTLE_ENABLED': True,
        # 'AUTOTHROTTLE_START_DELAY': 3,
        # 'AUTOTHROTTLE_MAX_DELAY': 60,
        # 'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        # 'AUTOTHROTTLE_DEBUG': False
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
            qs = Product.objects.filter(id__in=get_ids(self.task.products))
            self.products = [item.url for item in qs]
            self.categories = [item.category.url for item in qs]

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
        # self.store_report()

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
        # pid = response.url[-14:-5]
        # url = 'https://scontent.webcollage.net/homedepot/power-page?ird=true&channel-product-id=' + pid
       
        # quantity = re.search(r'\s*"maxQty" : "(.+?)",',response.body)
        quantity = 9999
        # min_quantity = re.search(r'\s*"minQty" : "(.+?)",',response.body)
        # min_quantity = min_quantity.group(1) if min_quantity else '0'

        # if int(quantity) == 9999:
        #     quantity = self.get_real_quantity({
        #         'ajaxFlag': True,
        #         'actionType': sel.xpath("//input[@name='actionType']/@value").extract_first(),
        #         'backURL': sel.xpath("//input[@name='backURL']/@value").extract_first(),
        #         'catalogId': sel.xpath("//input[@name='catalogId']/@value").extract_first(),
        #         'langId': sel.xpath("//input[@name='langId']/@value").extract_first(),
        #         'storeId': sel.xpath("//input[@name='storeId']/@value").extract_first(),
        #         'authToken': sel.xpath("//input[@name='authToken']/@value").extract_first(),
        #         'productBeanId': sel.xpath("//input[@name='productBeanId']/@value").extract_first(),
        #         'categoryId': sel.xpath("//input[@name='categoryId']/@value").extract_first(),
        #         'catEntryId': sel.xpath("//input[@name='catEntryId']/@value").extract_first(),
        #         'addedItem': sel.xpath("//input[@name='addedItem']/@value").extract_first(),
        #         'catalogEntryId_1': sel.xpath("//input[@name='catEntryId']/@value").extract_first(),
        #         'quantity': 9999,
        #         'quantity_1': 9999
        #     })

        # des_key = response.css('div.product-info-specs li span::text').extract()
        # des_val = response.css('div.product-info-specs li::text').extract()
        # description = self.get_description(des_key, des_val)
        special = response.css('h2.modelNo::text').extract_first().replace('\n', '').strip()

        item = {
            'id': response.css('span[id=product_internet_number]::text').extract_first(),
            'title': response.css('h1.product-title__title::text').extract_first(),
            'price': '$'+response.css('input[id=ciItemPrice]::attr(value)').extract_first(),
            'picture': response.xpath("//img[@id='mainImage']/@src").extract_first(),
            'rating': response.css('span[itemprop=ratingValue]::text').extract_first() or 0,
            'review_count': response.css('span[itemprop=reviewCount]::text').extract_first() or 0,
            'promo': '',
            'category_id': response.meta['category'].split('?')[0],
            'delivery_time': '',
            'bullet_points': '\n'.join(response.css('div.buybox li::text').extract()),
            'details': 'description',
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
        
    def get_description(self, des_key, des_val):
        description = ''
        if des_key:
            des_val = [item.strip() for item in des_val if item.strip()]
            for idx in range(len(des_val)):
                description += '{} {}\n'.format(des_key[idx].strip().encode('utf-8'), 
                                                des_val[idx].strip().encode('utf-8'))
        return description.replace(',', '')

    def get_real_quantity(self, body):
        url = 'https://www.homedepot.com/AjaxManageShoppingCartCmd'
        header = {
            'Accept':'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding':'gzip, deflate, br',
            'Accept-Language':'en-US,en;q=0.8',
            'Connection':'keep-alive',
            'Content-Length':'334',
            'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'Cookie':'spid=BB039764-30D4-488E-A2DA-3416AB5F90D4; s=undefined; hl_p=ae4eb09f-121c-45cf-a807-78a231307294; WC_SESSION_ESTABLISHED=true; WC_ACTIVEPOINTER=%2d1%2c10301; BVImplmain_site=2070; BVBRANDID=9c062aa4-9478-4cc7-8684-f1c52f41118b; AMCVS_97B21CFE5329614E0A490D45%40AdobeOrg=1; WC_PERSISTENT=1BGhult3vWEtlQhpFPW%2fYyGLB%2f8%3d%0a%3b2017%2d03%2d02+07%3a59%3a56%2e301%5f1487263129490%2d838314%5f10301%5f308580336%2c%2d1%2cUSD%5f10301; WC_USERACTIVITY_308580336=308580336%2c10301%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cnull%2cNPXKfRraLy80H%2facJBFuHUYe3X6iYFGrmBkLoO8pkRG%2fOKYM0Ow8VkcWzCfYx3%2bjEAxPYsnEhIvv%0aI322SzD41rPlK4uX0SGC1rkdkBuu9JeakMfDdJAgGEeK2LE%2fyrt2aTbJUxqqvmaAn0Xzt3aMHf%2b2%0aY0ZUSc2fxbvQDhb3B%2fsevHlNC4Gi8wDnS%2fIntMBnskY%2bRs1g%2btevRm2Lw5k0Fw%3d%3d; BVBRANDSID=cafd4e57-a4aa-47ec-a502-9c0a0b82318d; rr_rcs=eF4NxrENgDAMBMAmFbs8yju2E2_AGkkQEgUdMD9cdSk9cxvTKqN3WDOBuhB5FP1nHjzoecpyvfe5r0KC2ppWD8shFSEAP2Y1EJs; cartCountCookie=1; lastAddedProductId=169831; s_sq=%5B%5BB%5D%5D; C_CLIENT_SESSION_ID=c1672e8d-e50c-4830-862f-007dbffa13f5; WC_AUTHENTICATION_308580336=308580336%2cerDLv1iRML0kyZxjQKZ7DFQJnno%3d; JSESSIONID=0000AkynmIuDDqCCUolR-UPdrns:163c2eho3; ak_bmsc=5BF67D91DB9A91E1ED5BFFF822ECFF3917C663CF22580000095CB85822E90155~pl5UxYn+5vCqxw2Jd99L1zXHJyj3xUPoeqyk74K1w/HJlcCh3okhDXLL1qHo//44Y1pacZ5iTLrzfDpXpL8+RVq2PiRULQ0Xd+KgQ9ddWhr/MZjcx2Z14dUcxJE3VqOTVDRS7ZzDTapWJxcgG+oaPE9cMs9XtNPc+zcct1iunG/tvDwFO63ibb+skGm8hLaqJ0gW43h8VFh+K3sWiApRspwQ==; sp_ssid=1488477229844; WRUIDAWS=1120658076230015; __CT_Data=gpv=58&apv_59_www33=58&cpv_59_www33=58&rpv_59_www33=58; AMCV_97B21CFE5329614E0A490D45%40AdobeOrg=-1330315163%7CMCIDTS%7C17228%7CMCMID%7C14749491232221946818716045741455311554%7CMCAID%7CNONE%7CMCOPTOUT-1488484459s%7CNONE; s_cc=true',
            'DNT':'1',
            'Host':'www.homedepot.com',
            'Origin':'https://www.homedepot.com',
            'Referer':'https://www.homedepot.com/Round-Brilliant-3.00-ctw-VS2-Clarity%2c-I-Color-Diamond-Platinum-Three-Stone-Ring.product.11043679.html',
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
            'X-Requested-With':'XMLHttpRequest'        
        }

        res = requests.post(url=url, data=body)
        try:
            quantity_ = res.json()['orderErrMsgObj']['1']
        except Exception, e:
            print '==============================', str(res)
            # if 'errorMessage' in res.json():
            #     return 0
            return '9999'       # orderErrMsgObj
        quantity = re.search(r'\s*only (.+?) are\s*', quantity_)
        return quantity.group(1) if quantity else '9999'

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
