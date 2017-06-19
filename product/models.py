from __future__ import unicode_literals

import os
import subprocess

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

class Product(models.Model):
    id = models.CharField(primary_key=True, max_length=15)
    title = models.CharField(max_length=250)
    price = models.CharField(max_length=20)
    picture = models.CharField(max_length=250)
    rating = models.FloatField()
    review_count = models.IntegerField()
    delivery_time = models.TextField(null=True, blank=True)
    bullet_points = models.TextField(null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    promo = models.TextField(null=True, blank=True)
    special = models.TextField(null=True, blank=True)
    category = models.ForeignKey('Category')
    quantity = models.IntegerField()
    min_quantity = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    url = models.CharField(max_length=200)
    is_new = models.BooleanField(default=True)

    def __unicode__(self):
        return self.title


class Category(models.Model):    
    url = models.CharField(max_length=250, primary_key=True)
    title = models.CharField(max_length=250)
    parent = models.ForeignKey('Category', null=True)

    def __unicode__(self):
        return self.title

    def get_all_children(self, include_self=True):
        r = []
        if include_self:
            r.append(self)
        for c in Category.objects.filter(parent=self):
            _r = c.get_all_children(include_self=True)
            if 0 < len(_r):
                r.extend(_r)
        return r

    class Meta:
        verbose_name_plural = "categories"

MODE = (
    (1, 'Category'),
    (2, 'Products')
)

STATUS = (
    (0, 'Finished'),
    (1, 'Running'),
    (2, 'Sleeping'),
    (3, 'Stopped'),      # ready for export
)

class ScrapyTask(models.Model):
    title = models.CharField(max_length=50)
    mode = models.IntegerField(choices=MODE)
    status = models.IntegerField(choices=STATUS)
    category = models.ForeignKey(Category, blank=True, null=True)
    products = models.TextField(blank=True, null=True)
    products_file = models.FileField(blank=True, null=True)
    interval = models.PositiveIntegerField("Interval (minutes)",
                                           validators=[MinValueValidator(5)],
                                           default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    last_run = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.status = 1

            super(ScrapyTask, self).save(*args, **kwargs)

            if self.mode == 2 and self.products_file:
                with open(settings.MEDIA_ROOT+'/'+self.products_file.name, 'r') as products_file:
                    self.products = products_file.read()
                self.update()
            self.run_scraper()

    def update(self):
        super(ScrapyTask, self).save()

    def delete(self, *args, **kwargs):
        self.status = 3     # Stopped
        self.update()

    def run_scraper(self):
        path = settings.BASE_DIR + '/homedepot_scraper/celery_crawler.py'
        subprocess.Popen(["python", 
                          path, 
                          str(self.pk)])

