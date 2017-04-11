# -*- coding: utf-8 -*-

import os
from os import sys, path
import django
import json

sys.path.append(path.dirname(path.dirname(path.dirname(path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homedepot_site.settings")
django.setup()

from product.models import *

class HomedepotScraperPipeline(object):
    def process_item(self, item, spider):
        try:
            Product.objects.update_or_create(id=item['id'], defaults=item)
        except Exception, e:
            pass
        return item
