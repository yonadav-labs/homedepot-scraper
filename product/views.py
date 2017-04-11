import os
import re
import csv
import datetime
import mimetypes
import scrapy
import subprocess

from django.shortcuts import render
from django.utils.encoding import smart_str
from wsgiref.util import FileWrapper
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.conf import settings

from .models import *


@login_required(login_url='/admin/login/')
def init_category(request):
    ALL_CATEGORIES = {
        'electronics': 'Electronics',
        'computers': 'Computers',
        'appliances': 'Appliances',
        'furniture': 'Furniture & Mattresses',
        'auto-tires': 'Tires & Auto',
        'holiday-gifts': 'Floral, Gifts & Tickets',
        'jewelry': 'Jewelry & Watches',
        'patio-lawn-garden': 'Patio, Lawn & Garden',
        'hardware': 'Home Improvement',
        'home-and-decor': 'Home & Kitchen',
        'office-products': 'Office Products',
        'clothing': 'Clothing & Luggage',
        'health-beauty': 'Health & Beauty',
        'baby-kids': 'Baby, Kids & Toys',
        'grocery-household': 'Grocery, Household & Pet',
        'sports-fitness': 'Sports & Fitness'  
    }

    create_category(None, '/', 'All')
    for url, title in ALL_CATEGORIES.items():
        create_category('/', url, title)

    return HttpResponse('Top categories are successfully initiated')


@login_required(login_url='/admin/login/')
def export_products(request):
    if request.method == "POST":
        product_ids = request.POST.get('ids').strip().split(',')
        result_csv_fields = request.POST.getlist('props[]')
        path = datetime.datetime.now().strftime("/tmp/.homedepot_products_%Y_%m_%d_%H_%M_%S.csv")

        if product_ids == [u'']:
            queryset = Product.objects.all()
        else:
            queryset = Product.objects.filter(id__in=product_ids)

        write_report(queryset, path, result_csv_fields)
        
        wrapper = FileWrapper( open( path, "r" ) )
        content_type = mimetypes.guess_type( path )[0]

        response = HttpResponse(wrapper, content_type = content_type)
        response['Content-Length'] = os.path.getsize( path ) # not FileField instance
        response['Content-Disposition'] = 'attachment; filename=%s/' % smart_str( os.path.basename( path ) ) # same here        
        return response
    else:
        fields = [f.name for f in Product._meta.get_fields() 
                  if f.name not in ['updated_at', 'is_new']]
        return render(request, 'product_properties.html', locals())    


def write_report(queryset, path, result_csv_fields):
    result = open(path, 'w')
    result_csv = csv.DictWriter(result, fieldnames=result_csv_fields)
    result_csv.writeheader()

    for product in queryset:
        product_ = model_to_dict(product, fields=result_csv_fields)
        for key, val in product_.items():
            if type(val) not in (float, int, long) and val:
                product_[key] = val.encode('utf-8')

        try:
            result_csv.writerow(product_)
        except Exception, e:
            print product_

    result.close()


def get_subcategories(parent='/', title=''):
    """
    return direct child categories
    """
    categories = Category.objects.filter(parent=parent, title__contains=title)
    return [item.url for item in categories]


def create_category(parent, url, title):
    try:
        Category.objects.create(parent_id=parent, url=url, title=title)
    except Exception, e:
        print str(e)


def get_category_products(category, attr='url'):
    """
    param: category as url
    """
    category = Category.objects.get(url=category)
    result = []
    for cate in category.get_all_children():
        for item in Product.objects.filter(category=cate):
            result.append(getattr(item, attr))
    return result


def set_old_category_products(category):
    """
    Set is_new flag False for existing products for the category
    """
    for cate in category.get_all_children():
        Product.objects.filter(category=cate).update(is_new=False)

def get_ids(list_str):
    ids = list_str.replace('\n', ',')
    return [int(item) for item in ids.split(',') if item]
