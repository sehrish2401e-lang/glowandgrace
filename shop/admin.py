from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'name', 'category', 'price', 'created_at')
    list_display_links = ('image_preview', 'name')
    list_filter = ('category',)
    search_fields = ('name', 'description')
    ordering = ('-created_at',)

    @admin.display(description='Image')
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:45px; width:45px; object-fit:contain; border-radius:6px;">',
                obj.image.url,
            )
        return '-'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'quantity', 'price')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'user', 'total', 'status', 'created_at')
    list_editable = ('status',)          # list mein hi status badal sakte hain
    list_filter = ('status', 'created_at')
    search_fields = ('=id', 'name', 'phone')
    readonly_fields = ('user', 'name', 'phone', 'address', 'total', 'created_at')
    inlines = [OrderItemInline]
    ordering = ('-created_at',)
    actions = ['mark_confirmed', 'mark_shipped', 'mark_delivered', 'mark_cancelled']

    @admin.action(description='Selected orders ko Confirmed karein')
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} order(s) Confirmed ho gaye.')

    @admin.action(description='Selected orders ko Shipped karein')
    def mark_shipped(self, request, queryset):
        updated = queryset.update(status='shipped')
        self.message_user(request, f'{updated} order(s) Shipped ho gaye.')

    @admin.action(description='Selected orders ko Delivered karein')
    def mark_delivered(self, request, queryset):
        updated = queryset.update(status='delivered')
        self.message_user(request, f'{updated} order(s) Delivered ho gaye.')

    @admin.action(description='Selected orders ko Cancelled karein')
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} order(s) Cancelled ho gaye.')