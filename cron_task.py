import os
import sys
import django

from datetime import datetime
from os import sys, path

# load settings
sys.path.append(path.dirname(path.dirname(path.dirname(path.dirname(path.abspath(__file__))))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homedepot_site.settings")
django.setup()

from product.models import *

# check scrapy tasks
for st in ScrapyTask.objects.filter(mode=2, status=2):
    sleep_time = (datetime.now() - st.last_run.replace(tzinfo=None)).seconds / 60
    if sleep_time >= st.interval:
        st.status = 1   # Running
        st.update()
        st.run_scraper()
