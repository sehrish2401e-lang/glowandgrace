import threading
import urllib.parse
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CheckoutForm
from .models import Product, Order, OrderItem


# ---------------------------------------------------------------
# Cart helpers (cart session mein save hota hai: {"product_id": quantity})
# ---------------------------------------------------------------
def get_cart(request):
    return request.session.get('cart', {})


def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def cart_count(request):
    return sum(get_cart(request).values())


def build_cart_items(request):
    """Cart ke items, har item ka subtotal, aur total wapas deta hai."""
    cart = get_cart(request)
    products = Product.objects.in_bulk([int(pid) for pid in cart.keys()])
    items = []
    total = Decimal('0')
    for product_id, quantity in cart.items():
        product = products.get(int(product_id))
        if not product:
            continue
        subtotal = product.price * quantity
        total += subtotal
        items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
        })
    return items, total


# ---------------------------------------------------------------
# Naya order aane par admin ko WhatsApp (aur optional email)
# ---------------------------------------------------------------
def _send_whatsapp(text):
    phone = getattr(settings, 'WHATSAPP_PHONE', None)
    apikey = getattr(settings, 'WHATSAPP_APIKEY', None)
    if not phone or not apikey:
        return
    params = urllib.parse.urlencode({'phone': phone, 'text': text, 'apikey': apikey})
    url = f"https://api.callmebot.com/whatsapp.php?{params}"
    try:
        urllib.request.urlopen(url, timeout=10)
    except Exception:
        pass  # WhatsApp fail ho to bhi order save rahe


def notify_new_order(order, items):
    lines = [f"- {i['product'].name} x {i['quantity']} = Rs. {i['subtotal']}" for i in items]
    message = (
        f"Naya order aaya hai!\n\n"
        f"Order #{order.id}\n"
        f"Naam: {order.name}\n"
        f"Phone: {order.phone}\n"
        f"Address: {order.address}\n\n"
        f"Items:\n" + "\n".join(lines) + f"\n\nTotal: Rs. {order.total}"
    )

    # WhatsApp alag thread mein, taake customer ko wait na karna pade
    threading.Thread(target=_send_whatsapp, args=(message,), daemon=True).start()

    # Email (sirf agar settings mein ORDER_NOTIFY_EMAIL likha ho)
    recipient = getattr(settings, 'ORDER_NOTIFY_EMAIL', None)
    if recipient:
        try:
            send_mail(
                subject=f"Naya Order #{order.id} - Rs. {order.total}",
                message=message,
                from_email=None,
                recipient_list=[recipient],
                fail_silently=True,
            )
        except Exception:
            pass


# ---------------------------------------------------------------
# Pages
# ---------------------------------------------------------------
def home(request):
    context = {
        'skincare': Product.objects.filter(category='skincare').order_by('-created_at'),
        'makeup': Product.objects.filter(category='makeup').order_by('-created_at'),
        'haircare': Product.objects.filter(category='haircare').order_by('-created_at'),
        'fragrance': Product.objects.filter(category='fragrance').order_by('-created_at'),
        'cart_count': cart_count(request),
    }
    return render(request, 'shop/home.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'cart_count': cart_count(request),
    })


def about(request):
    return render(request, 'shop/about.html', {'cart_count': cart_count(request)})


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        text = request.POST.get('message', '').strip()
        if name and email and text:
            recipient = getattr(settings, 'ORDER_NOTIFY_EMAIL', None)
            if recipient:
                send_mail(
                    subject=f'Contact form: {name}',
                    message=f'Naam: {name}\nEmail: {email}\n\n{text}',
                    from_email=None,
                    recipient_list=[recipient],
                    fail_silently=True,
                )
            messages.success(request, 'Shukriya! Aapka message mil gaya hai, hum jald reply karenge.')
        else:
            messages.error(request, 'Please saari fields bharein.')
        return redirect('contact')
    return render(request, 'shop/contact.html', {'cart_count': cart_count(request)})


def category_page(request, category):
    valid_categories = [key for key, _ in Product.CATEGORY_CHOICES]
    if category not in valid_categories:
        raise Http404("Category nahi mili")
    products = Product.objects.filter(category=category).order_by('-created_at')
    return render(request, 'shop/category.html', {
        'products': products,
        'category': category,
        'category_name': category.capitalize(),
        'cart_count': cart_count(request),
    })


def search_results(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    return render(request, 'shop/search_results.html', {
        'products': products,
        'query': query,
        'q': query,
        'cart_count': cart_count(request),
    })


# ---------------------------------------------------------------
# Cart
# ---------------------------------------------------------------
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    key = str(product.id)
    cart[key] = cart.get(key, 0) + 1
    save_cart(request, cart)
    messages.success(request, f'{product.name} cart mein add ho gaya.')

    next_url = request.META.get('HTTP_REFERER')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('home')


@require_POST
def remove_from_cart(request, product_id):
    cart = get_cart(request)
    cart.pop(str(product_id), None)
    save_cart(request, cart)
    return redirect('cart_detail')


@require_POST
def update_cart(request, product_id, action):
    cart = get_cart(request)
    key = str(product_id)
    if key in cart:
        if action in ('increase', 'plus', 'inc', 'add'):
            cart[key] += 1
        elif action in ('decrease', 'minus', 'dec', 'sub'):
            cart[key] -= 1
            if cart[key] <= 0:
                del cart[key]
    save_cart(request, cart)
    return redirect('cart_detail')


def cart_detail(request):
    items, total = build_cart_items(request)
    return render(request, 'shop/cart.html', {
        'items': items,
        'cart_items': items,
        'total': total,
        'cart_count': cart_count(request),
    })


def checkout(request):
    items, total = build_cart_items(request)
    if not items:
        messages.error(request, 'Aapka cart khali hai.')
        return redirect('cart_detail')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    name=data['name'],
                    phone=data['phone'],
                    address=data['address'],
                    total=total,
                )
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        product_name=item['product'].name,
                        quantity=item['quantity'],
                        price=item['product'].price,
                    )
                transaction.on_commit(lambda: notify_new_order(order, items))
            save_cart(request, {})
            # Order ID session me rakhein aur success page par redirect karein
            request.session['last_order_id'] = order.id
            return redirect('order_success')
    else:
        form = CheckoutForm()

    return render(request, 'shop/checkout.html', {
        'form': form,
        'items': items,
        'total': total,
        'cart_count': cart_count(request),
    })


def order_success(request):
    order_id = request.session.get('last_order_id')
    if not order_id:
        return redirect('home')
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'shop/order_success.html', {
        'order': order,
        'cart_count': 0,
    })


# ---------------------------------------------------------------
# My Orders (sirf login user ko apne orders nazar aayenge)
# ---------------------------------------------------------------
@login_required(login_url='login')
def my_orders(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items')
        .order_by('-created_at')
    )
    return render(request, 'shop/my_orders.html', {
        'orders': orders,
        'cart_count': cart_count(request),
    })


# ---------------------------------------------------------------
# Login / Register / Logout
# ---------------------------------------------------------------
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                form.add_error('username', 'Ye username pehle se maujood hai. Login karein ya koi aur username chunein.')
            else:
                login(request, user)
                messages.success(request, 'Account ban gaya!')
                return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'shop/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')