from django.contrib import admin
from django.http import HttpResponse, HttpResponseRedirect

from django.shortcuts import render
from django import forms
from django.contrib import messages

from .models import *
from .views import *

class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'price', 'quantity', 'min_quantity', 
                    'rating', 'review_count', 'updated_at', 'url']
    search_fields = ['title', 'bullet_points']
    actions = ['export_products']
    list_filter = ('category',)

    def export_products(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        ids = ','.join([str(item.id) for item in queryset])
        fields = [f.name for f in Product._meta.get_fields() 
                  if f.name not in ['updated_at', 'is_new']]
        return render(request, 'product_properties.html', locals())    

    export_products.short_description = "Export products as CSV file"  


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'url', 'parent']
    search_fields = ['title', 'url']


class ScrapyTaskForm(forms.ModelForm):
    class Meta:
        model = ScrapyTask
        fields = '__all__'

    def clean(self):
        mode = self.cleaned_data.get('mode')
        category = self.cleaned_data.get('category')
        products = self.cleaned_data.get('products')

        if mode == 1:
            if not category:
                raise forms.ValidationError("Category should be provided in " 
                                          + "Category mode.")
        elif mode == 2:
            # validate product IDs or file
            if products.strip():
                products = products.replace('\n', ',')
                for item in products.split(','):
                    try:
                        Product.objects.get(id=int(item))
                    except Exception, e:
                        raise forms.ValidationError("Products should be comma "
                            + "seperated VALID product id list e.g) 12432, 12424, ...")
            elif not self.cleaned_data.get('products_file'):
                raise forms.ValidationError("Please provide a list of product IDs or a file")

        return self.cleaned_data


class ScrapyTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'mode', 'status', 'interval', 'last_run',
                    'created_at']
    search_fields = ['title']
    exclude = ['status', 'last_run']
    form = ScrapyTaskForm
    actions = ['export_products']
    list_filter = ('status',)

    fieldsets = (
        (None, {
            'fields': ('title', 'mode')
        }),
        ('Category Mode', {
            'classes': ('collapse',),
            'fields': ('category',),
        }),
        ('Products Mode', {
            'classes': ('collapse',),
            'fields': ('products', 'products_file', 'interval'),
        }),
    )

    def export_products(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        if len(selected) > 1:
            messages.error(request, "Choose only one instance.")
        else:
            st = queryset.first()
            if st.mode == 1:
                result = []
                for cate in st.category.get_all_children():
                    # only for new products
                    for item in Product.objects.filter(category=cate, 
                                                       is_new=True):
                        result.append(str(item.id))
                ids = ','.join(result)
            else:
                ids = st.products
            fields = [f.name for f in Product._meta.get_fields() 
                      if f.name not in ['updated_at', 'is_new']]
            return render(request, 'product_properties.html', locals())    

    export_products.short_description = "Export products as CSV file"  

admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(ScrapyTask, ScrapyTaskAdmin)
