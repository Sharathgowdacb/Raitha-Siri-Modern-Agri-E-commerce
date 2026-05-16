from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, authenticate, get_user_model
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Count
from .models import Product, FarmerProfile, Category, Order, PhoneVerificationCode, Notification, Wishlist, BuyerProfile, BuyerSettings, SupportRequest
from .forms import UserRegistrationForm, ProductForm, FarmerProfileForm, BuyerProfileForm
from .decorators import farmer_required
from .decorators import buyer_required
from .decorators import farmer_profile_complete_required
from .decorators import farmer_profile_required
from .decorators import farmer_phone_verified_required

import secrets
import re

User = get_user_model()


def home(request):
    products = Product.objects.filter(is_available=True).select_related('farmer__user')
    categories = Category.objects.all()

    q = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'newest').strip()

    if q:
        products = products.filter(name__icontains=q)
    if category_slug:
        selected_category = categories.filter(slug=category_slug).first()
        if selected_category:
            products = products.filter(category=selected_category.name)
        else:
            products = products.none()

    sort_map = {
        'price_asc': 'price',
        'price_desc': '-price',
        'name': 'name',
        'newest': '-created_at',
    }
    products = products.order_by(sort_map.get(sort, '-created_at'))

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')

    wishlist_products = set()
    if request.user.is_authenticated:
        wishlist_products = set(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))

    category_counts = (
        Product.objects.filter(is_available=True)
        .values('category')
        .annotate(count=Count('id'))
    )
    category_map = {row['category']: row['count'] for row in category_counts}
    featured_products = products[:4]

    is_buyer = request.user.is_authenticated and not hasattr(request.user, 'farmer_profile')
    template_name = 'store/buyer/home.html' if is_buyer else 'store/home.html'

    return render(
        request,
        template_name,
        {
            'products': page_obj.object_list,
            'page_obj': page_obj,
            'categories': categories,
            'q': q,
            'selected_category': category_slug,
            'selected_sort': sort,
            'query_string': query_params.urlencode(),
            'page_range': page_range,
            'wishlist_products': wishlist_products,
            'category_map': category_map,
            'featured_products': featured_products,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    is_buyer = request.user.is_authenticated and not hasattr(request.user, 'farmer_profile')
    template_name = 'store/buyer/product_detail.html' if is_buyer else 'store/product_detail.html'
    return render(request, template_name, {'product': product})


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            is_farmer = form.cleaned_data.get('is_farmer')
            if is_farmer:
                FarmerProfile.objects.create(
                    user=user,
                    full_name=user.get_full_name() or user.get_username(),
                    village='Unknown',
                    address='Unknown',
                    gender='other',
                    phone_number='',
                    email=user.email or 'unknown@example.com',
                    is_farmer=True,
                )
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Registration successful.')
            if is_farmer:
                messages.info(request, 'Please complete your farmer profile to continue.')
                return redirect('store:farmer_profile_edit')
            return redirect('store:home')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """Role-aware login supporting email or username identifier."""
    context = {
        'selected_role': 'Buyer',
        'email_value': '',
        'errors': {},
    }

    if request.method == 'POST':
        identifier = (request.POST.get('email') or request.POST.get('username') or '').strip()
        password = request.POST.get('password', '')
        selected_role = request.POST.get('role') or 'Buyer'
        remember_me = request.POST.get('remember') == '1'

        context['selected_role'] = selected_role if selected_role in ('Farmer', 'Buyer') else 'Farmer'
        context['email_value'] = identifier
        request.session['selected_role'] = context['selected_role']

        errors = {}
        if not identifier:
            errors['email'] = 'Email or username is required.'
        if not password:
            errors['password'] = 'Password is required.'

        resolved_username = identifier
        if '@' in identifier:
            user_by_email = User.objects.filter(email__iexact=identifier).first()
            if user_by_email:
                resolved_username = user_by_email.get_username()

        user = None
        if not errors:
            user = authenticate(request, username=resolved_username, password=password)
            if not user:
                errors['general'] = 'Invalid credentials. Please check your email/username and password.'

        if user and not errors:
            if context['selected_role'] == 'Farmer' and not hasattr(user, 'farmer_profile'):
                errors['general'] = 'This account is not registered as a farmer. Choose Buyer instead.'

        if errors:
            messages.error(request, errors.get('general') or 'Please fix the errors below.')
            context['errors'] = errors
            return render(request, 'registration/login.html', context)

        login(request, user)

        # Remember-me session
        # - checked: keep default session age
        # - unchecked: expire when browser closes
        if remember_me:
            request.session.set_expiry(None)
        else:
            request.session.set_expiry(0)

        messages.success(request, 'Logged in successfully.')
        if context['selected_role'] == 'Farmer':
            return redirect('store:farmer_dashboard')
        return redirect('store:buyer_dashboard')

    return render(request, 'registration/login.html', context)


def oauth_start(request, provider):
    """Start OAuth login while capturing Farmer/Buyer selection."""
    if provider not in ('google', 'facebook'):
        messages.error(request, 'Unsupported login provider.')
        return redirect('store:login')

    role = request.GET.get('role') or 'Buyer'
    role = role if role in ('Farmer', 'Buyer') else 'Buyer'
    request.session['selected_role'] = role

    next_path = reverse('store:farmer_dashboard') if role == 'Farmer' else reverse('store:buyer_dashboard')
    provider_login_path = reverse(f'{provider}_login')
    return redirect(f"{provider_login_path}?{urlencode({'next': next_path})}")


@login_required
def dashboard_redirect(request):
    if hasattr(request.user, 'farmer_profile'):
        return redirect('store:farmer_dashboard')
    return redirect('store:buyer_dashboard')


@buyer_required
def buyer_dashboard(request):
    products = Product.objects.filter(is_available=True).select_related('farmer__user').order_by('-created_at')
    category_counts = (
        Product.objects.filter(is_available=True)
        .values('category')
        .annotate(count=Count('id'))
    )
    category_map = {row['category']: row['count'] for row in category_counts}
    featured_products = products[:4]
    recent_orders = request.user.orders.all().order_by('-created_at')[:5]

    return render(
        request,
        'store/buyer/home.html',
        {
            'products': products[:12],
            'featured_products': featured_products,
            'category_map': category_map,
            'recent_orders': recent_orders,
        },
    )


@buyer_required
def buyer_settings(request):
    """Buyer profile/settings page."""
    profile, created = BuyerProfile.objects.get_or_create(user=request.user)
    settings_obj, _ = BuyerSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        theme = (request.POST.get('theme') or 'light').lower()
        valid_themes = {choice[0] for choice in BuyerSettings.THEME_CHOICES}
        if theme not in valid_themes:
            theme = 'light'

        settings_obj.theme = theme
        settings_obj.email_updates = request.POST.get('email_updates') == 'on'
        settings_obj.sms_updates = request.POST.get('sms_updates') == 'on'
        settings_obj.order_updates = request.POST.get('order_updates') == 'on'
        settings_obj.product_updates = request.POST.get('product_updates') == 'on'
        settings_obj.save()
        messages.success(request, 'Settings updated successfully.')
        return redirect('store:buyer_settings')

    return render(
        request,
        'store/buyer/settings.html',
        {
            'profile': profile,
            'settings': settings_obj,
        },
    )


@buyer_required
def buyer_profile_edit(request):
    """Edit buyer profile."""
    profile, created = BuyerProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = BuyerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('store:buyer_settings')
    else:
        form = BuyerProfileForm(instance=profile)
    
    return render(request, 'store/buyer/profile_edit.html', {'form': form, 'profile': profile})


@buyer_required
def buyer_change_password(request):
    """Change buyer password."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password changed successfully. Please log in again.')
            return redirect('store:login')
    else:
        form = PasswordChangeForm(request.user)
        # Add classes to form fields
        form.fields['old_password'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500'
        })
        form.fields['new_password1'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500'
        })
        form.fields['new_password2'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500'
        })
    
    return render(request, 'store/buyer/change_password.html', {'form': form})


@buyer_required
def wishlist(request):
    """Buyer wishlist page."""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product__farmer__user')
    return render(request, 'store/buyer/wishlist.html', {'wishlist_items': wishlist_items})


@buyer_required
def add_to_wishlist(request, product_id):
    """Add product to user's wishlist."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    product = get_object_or_404(Product, pk=product_id, is_available=True)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if created:
        return JsonResponse({'ok': True, 'added': True})
    else:
        return JsonResponse({'ok': True, 'added': False, 'message': 'Already in wishlist'})


@buyer_required
def remove_from_wishlist(request, product_id):
    """Remove product from user's wishlist."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    product = get_object_or_404(Product, pk=product_id)
    deleted, _ = Wishlist.objects.filter(user=request.user, product=product).delete()
    
    return JsonResponse({'ok': True, 'removed': deleted > 0})


@buyer_required
def buyer_notifications_page(request):
    """Buyer notifications page."""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return render(
        request,
        'store/buyer/notifications.html',
        {
            'notifications': notifications,
            'unread_count': unread_count,
        },
    )


@buyer_required
def buyer_notifications_api(request):
    """Return latest buyer notifications for the navbar dropdown."""
    notifications = (
        Notification.objects.filter(recipient=request.user)
        .order_by('-created_at')[:10]
    )
    payload = [
        {
            'id': n.pk,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'target_url': n.target_url or '',
        }
        for n in notifications
    ]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'ok': True, 'unread_count': unread_count, 'notifications': payload})


@buyer_required
def buyer_notification_mark_read(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=400)

    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    return JsonResponse({'ok': True})


@buyer_required
def buyer_notifications_mark_all_read(request):
    if request.method != 'POST':
        return redirect('store:buyer_notifications')

    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    messages.success(request, 'All notifications marked as read.')
    return redirect('store:buyer_notifications')


def help_center(request):
    """Help Center page (public, UI-only)."""
    is_buyer = request.user.is_authenticated and not hasattr(request.user, 'farmer_profile')
    template_name = 'store/buyer/help_center.html' if is_buyer else 'store/help_center.html'
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        email = (request.POST.get('email') or '').strip()
        subject = (request.POST.get('subject') or '').strip()
        message = (request.POST.get('message') or '').strip()

        if not (name and email and subject and message):
            messages.error(request, 'Please fill out all fields before submitting.')
            return render(request, template_name, {'form_error': True})

        SupportRequest.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=name,
            email=email,
            subject=subject,
            message=message,
        )
        messages.success(request, 'Thanks! Your support request has been submitted.')
        return redirect('store:help_center')

    return render(request, template_name)


@farmer_required
@farmer_profile_complete_required
def farmer_notifications(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:50]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return render(
        request,
        'store/farmer/notifications.html',
        {
            'notifications': notifications,
            'unread_count': unread_count,
        },
    )


@farmer_required
@farmer_profile_complete_required
def farmer_notification_mark_read(request, pk):
    if request.method != 'POST':
        return redirect('store:farmer_notifications')

    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    next_url = request.POST.get('next') or notification.target_url or reverse('store:farmer_notifications')
    return redirect(next_url)


@farmer_required
@farmer_profile_complete_required
def farmer_notifications_mark_all_read(request):
    if request.method != 'POST':
        return redirect('store:farmer_notifications')

    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    messages.success(request, 'All notifications marked as read.')
    return redirect('store:farmer_notifications')


def _generate_otp_code() -> str:
    # 6 digits, zero-padded
    return f"{secrets.randbelow(1_000_000):06d}"


@farmer_required
@farmer_profile_complete_required
def farmer_dashboard(request):
    profile = request.user.farmer_profile
    products = profile.products.all()
    available_count = products.filter(is_available=True).count()
    recent_products = products.order_by('-created_at')[:5]

    incoming_orders = Order.objects.filter(farmer=profile)
    pending_orders_count = incoming_orders.filter(status='PENDING').count()
    approved_orders_count = incoming_orders.filter(status='APPROVED').count()
    rejected_orders_count = incoming_orders.filter(status='REJECTED').count()
    return render(
        request,
        'store/farmer/dashboard.html',
        {
            'profile': profile,
            'products': products,
            'products_count': products.count(),
            'available_count': available_count,
            'recent_products': recent_products,
            'pending_orders_count': pending_orders_count,
            'approved_orders_count': approved_orders_count,
            'rejected_orders_count': rejected_orders_count,
            'can_switch_to_buyer': True,
        },
    )


@farmer_required
@farmer_profile_complete_required
def farmer_product_list(request):
    profile = request.user.farmer_profile
    products = profile.products.all()
    return render(request, 'store/farmer/product_list.html', {'products': products})


@farmer_required
@farmer_profile_complete_required
@farmer_phone_verified_required
def farmer_product_create(request):
    profile = request.user.farmer_profile

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.farmer = profile
            product.save()
            # Notify buyers about the new product (respect preferences).
            buyer_users = (
                User.objects.filter(farmer_profile__isnull=True)
                .exclude(pk=request.user.pk)
                .filter(Q(buyer_settings__product_updates=True) | Q(buyer_settings__isnull=True))
            )
            if buyer_users.exists():
                Notification.objects.bulk_create(
                    [
                        Notification(
                            recipient=buyer,
                            title='New product available',
                            message=f'{product.name} is now available from {profile.full_name}.',
                            level='info',
                            target_url=reverse('store:product_detail', args=[product.slug]),
                            product=product,
                        )
                        for buyer in buyer_users
                    ]
                )
            messages.success(request, 'Product created.')
            return redirect('store:farmer_product_list')
    else:
        form = ProductForm()
    return render(request, 'store/farmer/product_form.html', {'form': form})


@farmer_required
@farmer_profile_complete_required
@farmer_phone_verified_required
def farmer_product_edit(request, pk):
    profile = request.user.farmer_profile

    product = get_object_or_404(Product, pk=pk, farmer=profile)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated.')
            return redirect('store:farmer_product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'store/farmer/product_form.html', {'form': form, 'product': product})


@farmer_required
@farmer_profile_complete_required
@farmer_phone_verified_required
def farmer_product_delete(request, pk):
    profile = request.user.farmer_profile

    product = get_object_or_404(Product, pk=pk, farmer=profile)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('store:farmer_product_list')
    return render(request, 'store/farmer/confirm_delete.html', {'product': product})


# ===== Farmer Dashboard Profile & Settings Views =====

@farmer_required
@farmer_profile_complete_required
def farmer_profile_view(request):
    """Display farmer profile information."""
    profile = request.user.farmer_profile
    products = profile.products.all()
    available_count = products.filter(is_available=True).count()
    latest_products = products.order_by('-created_at')[:3]

    return render(
        request,
        'store/farmer/profile.html',
        {
            'profile': profile,
            'products_count': products.count(),
            'available_count': available_count,
            'latest_products': latest_products,
        },
    )


@farmer_required
def farmer_profile_edit(request):
    """Edit farmer profile information."""
    profile = request.user.farmer_profile
    if request.method == 'POST':
        form = FarmerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            was_complete = profile.is_profile_complete()
            form.save()
            is_now_complete = profile.is_profile_complete()
            if not was_complete and is_now_complete:
                messages.success(request, 'Profile completed successfully.')
                return redirect('store:farmer_dashboard')
            messages.success(request, 'Profile updated successfully.')
            return redirect('store:farmer_profile_view')
    else:
        form = FarmerProfileForm(instance=profile)
    
    return render(request, 'store/farmer/profile_edit.html', {'form': form})


@farmer_required
@farmer_profile_complete_required
def farmer_settings_view(request):
    """Display and handle farmer account settings."""
    profile = request.user.farmer_profile
    context = {
        'profile': profile,
        'theme': request.session.get('theme', 'light'),
    }
    
    return render(request, 'store/farmer/settings.html', context)


@farmer_required
@farmer_profile_complete_required
def farmer_phone_verify(request):
    """Send/resend an OTP and verify the farmer phone number."""

    profile = request.user.farmer_profile
    latest_code = profile.phone_verification_codes.order_by('-created_at').first()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip().lower()

        if action in ('send', 'resend'):
            if profile.is_verified:
                messages.info(request, 'Your phone number is already verified.')
                return redirect('store:farmer_phone_verify')

            if not (profile.phone_number or '').strip():
                messages.error(request, 'Please add a phone number first.')
                return redirect('store:farmer_profile_edit')

            # Basic cooldown to prevent spamming.
            if latest_code and (timezone.now() - latest_code.created_at).total_seconds() < 60:
                messages.warning(request, 'Please wait a minute before requesting a new code.')
                return redirect('store:farmer_phone_verify')

            raw_code = _generate_otp_code()
            PhoneVerificationCode.issue(profile, raw_code)

            # Temporary "SMS" simulation.
            print(f"[Phone OTP] User={request.user.username} Phone={profile.phone_number} OTP={raw_code}")
            messages.success(request, 'Verification code sent. (Check server logs in development)')
            return redirect('store:farmer_phone_verify')

        if action == 'verify':
            raw_code = (request.POST.get('code') or '').strip()

            if not re.fullmatch(r'\d{6}', raw_code):
                messages.error(request, 'Enter the 6-digit code.')
                return redirect('store:farmer_phone_verify')

            # Re-fetch most recent code after a send.
            latest_code = profile.phone_verification_codes.order_by('-created_at').first()
            if not latest_code:
                messages.error(request, 'No verification code found. Please request a new code.')
                return redirect('store:farmer_phone_verify')

            if latest_code.phone_number != profile.phone_number:
                messages.error(request, 'Your phone number has changed. Please request a new code.')
                return redirect('store:farmer_phone_verify')

            if latest_code.is_expired:
                messages.error(request, 'That code has expired. Please request a new one.')
                return redirect('store:farmer_phone_verify')

            if latest_code.is_consumed:
                messages.error(request, 'That code was already used. Please request a new one.')
                return redirect('store:farmer_phone_verify')

            ok = latest_code.check_and_consume(raw_code)
            if not ok:
                messages.error(request, 'Invalid code. Please try again.')
                return redirect('store:farmer_phone_verify')

            profile.is_verified = True
            profile.save(update_fields=['is_verified'])
            messages.success(request, 'Phone number verified successfully.')
            return redirect('store:farmer_settings_view')

        messages.error(request, 'Invalid action.')
        return redirect('store:farmer_phone_verify')

    return render(
        request,
        'store/farmer/phone_verify.html',
        {
            'profile': profile,
            'is_verified': profile.is_verified,
            'latest_code': latest_code,
        },
    )


@farmer_profile_required
def farmer_stats_api(request):
    """Lightweight stats endpoint for future dashboard widgets."""
    profile = request.farmer_profile
    products = profile.products.all().order_by('-created_at')
    recent_products = []
    for product in products[:5]:
        recent_products.append({
            'id': product.id,
            'name': product.name,
            'category': product.category,
            'price': str(product.price),
            'is_available': product.is_available,
        })

    return JsonResponse({
        'total_products': products.count(),
        'available_products': products.filter(is_available=True).count(),
        'recent_products': recent_products,
    })


# ===== Cart and Order APIs =====

@buyer_required
def cart_api(request):
    """Get cart data as JSON."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=400)
    
    cart = _get_or_create_cart(request)
    items_data = []
    
    for item in cart.items.select_related('product', 'product__farmer').all():
        items_data.append({
            'id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'price': str(item.product.price),
            'subtotal': str(item.subtotal()),
            'available_stock': item.product.quantity,
        })
    
    return JsonResponse({
        'ok': True,
        'cart_id': cart.id,
        'items': items_data,
        'total': str(cart.total_price()),
        'item_count': sum(i.quantity for i in cart.items.all()),
    })


@buyer_required
def orders_api(request):
    """Get buyer's orders as JSON."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=400)
    
    orders = request.user.orders.select_related('product', 'farmer', 'farmer__user').order_by('-created_at')
    
    orders_data = []
    for order in orders:
        orders_data.append({
            'id': order.id,
            'product_name': order.product.name if order.product else 'N/A',
            'quantity': order.quantity,
            'total_price': str(order.total_price),
            'status': order.status,
            'farmer_name': order.farmer.full_name if order.farmer else 'N/A',
            'created_at': order.created_at.isoformat(),
            'url': reverse('store:order_detail', args=[order.pk]),
        })
    
    return JsonResponse({
        'ok': True,
        'orders': orders_data,
        'total_count': len(orders_data),
    })


@buyer_required
def order_api(request, pk):
    """Get specific order details as JSON."""
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=400)
    
    order = get_object_or_404(Order, pk=pk, user=request.user)
    
    return JsonResponse({
        'ok': True,
        'id': order.id,
        'product_id': order.product.id if order.product else None,
        'product_name': order.product.name if order.product else 'N/A',
        'quantity': order.quantity,
        'total_price': str(order.total_price),
        'status': order.status,
        'farmer_id': order.farmer.id if order.farmer else None,
        'farmer_name': order.farmer.full_name if order.farmer else 'N/A',
        'farmer_contact': order.farmer.user.email if order.farmer else 'N/A',
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat() if hasattr(order, 'updated_at') else None,
    })


def _get_or_create_cart(request):
    """Return a Cart instance for the session or user."""
    from .models import Cart
    cart = None
    # If user is authenticated, prefer user's active cart
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if not cart:
            cart = Cart.objects.create(user=request.user)
            request.session['cart_id'] = cart.id
        return cart

    # Anonymous session cart
    cart_id = request.session.get('cart_id')
    if cart_id:
        try:
            cart = Cart.objects.get(pk=cart_id)
        except Cart.DoesNotExist:
            cart = None
    if not cart:
        cart = Cart.objects.create()
        request.session['cart_id'] = cart.id
    return cart


def add_to_cart(request):
    from .models import Product, CartItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    product_id = request.POST.get('product_id')
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid quantity'}, status=400)
    if quantity < 1:
        return JsonResponse({'error': 'Quantity must be at least 1'}, status=400)
    product = get_object_or_404(Product, pk=product_id, is_available=True)

    cart = _get_or_create_cart(request)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity = item.quantity + quantity
    else:
        item.quantity = quantity
    item.save()

    return JsonResponse({
        'ok': True,
        'cart_count': sum(i.quantity for i in cart.items.all()),
        'item_id': item.id,
        'item_quantity': item.quantity,
    })


def update_cart_item(request, item_id):
    from .models import CartItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    cart = _get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid quantity'}, status=400)

    if quantity < 1:
        item.delete()
        return JsonResponse({
            'ok': True,
            'removed': True,
            'cart_count': sum(i.quantity for i in cart.items.all()),
            'cart_total': f"{cart.total_price():.2f}",
        })

    item.quantity = quantity
    item.save()
    return JsonResponse({
        'ok': True,
        'removed': False,
        'cart_count': sum(i.quantity for i in cart.items.all()),
        'cart_total': f"{cart.total_price():.2f}",
        'item_subtotal': f"{item.subtotal():.2f}",
    })


def remove_cart_item(request, item_id):
    from .models import CartItem

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    cart = _get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    return JsonResponse({
        'ok': True,
        'cart_count': sum(i.quantity for i in cart.items.all()),
        'cart_total': f"{cart.total_price():.2f}",
    })


@buyer_required
def view_cart(request):
    cart = _get_or_create_cart(request)
    return render(request, 'store/cart.html', {'cart': cart})


@buyer_required
def checkout(request):
    cart = _get_or_create_cart(request)
    if not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('store:home')

    if request.method == 'POST':
        from django.db import transaction
        
        try:
            with transaction.atomic():
                created_count = 0
                total_price_all = 0
                order_ids = []
                
                for ci in cart.items.select_related('product', 'product__farmer').all():
                    product = ci.product
                    
                    # Validate stock availability
                    if product.quantity < ci.quantity:
                        messages.error(
                            request,
                            f'Insufficient stock for "{product.name}". Available: {product.quantity}, Requested: {ci.quantity}'
                        )
                        return render(request, 'store/checkout.html', {'cart': cart})
                    
                    # Create order
                    order = Order.objects.create(
                        user=request.user,
                        farmer=product.farmer,
                        product=product,
                        quantity=ci.quantity,
                        total_price=product.price * ci.quantity,
                        status='PENDING',
                    )
                    
                    # Update product stock
                    product.quantity -= ci.quantity
                    product.save(update_fields=['quantity'])
                    
                    # Notify farmer
                    Notification.objects.create(
                        recipient=product.farmer.user,
                        title=f'New order #{order.pk}',
                        message=f'{request.user.username} ordered {ci.quantity} × {product.name}.',
                        level='info',
                        target_url=reverse('store:farmer_orders_received'),
                        order=order,
                        product=product,
                    )
                    
                    created_count += 1
                    total_price_all += order.total_price
                    order_ids.append(order.id)

                # Clear cart
                cart.items.all().delete()
                try:
                    del request.session['cart_id']
                except KeyError:
                    pass

                messages.success(
                    request,
                    f'Order Placed Successfully! {created_count} item(s) ordered. Total: ₹{total_price_all:.2f}'
                )
                request.session['last_order_ids'] = order_ids
                return redirect('store:order_history')
        
        except Exception as e:
            messages.error(request, f'Error placing order: {str(e)}')
            return render(request, 'store/checkout.html', {'cart': cart})

    return render(request, 'store/checkout.html', {'cart': cart})


@buyer_required
def order_history(request):
    orders = request.user.orders.select_related('product', 'farmer', 'farmer__user').all().order_by('-created_at')
    return render(request, 'store/orders.html', {'orders': orders})


@buyer_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'store/order_detail.html', {'order': order})


# ===== Farmer Order Management =====


@farmer_required
@farmer_profile_complete_required
def farmer_orders_received(request):
    profile = request.user.farmer_profile
    orders = (
        Order.objects.filter(farmer=profile)
        .select_related('user', 'product')
        .order_by('-created_at')
    )
    return render(request, 'store/farmer/orders_received.html', {'orders': orders})


@farmer_required
@farmer_profile_complete_required
@farmer_phone_verified_required
def farmer_order_approve(request, pk):
    if request.method != 'POST':
        return redirect('store:farmer_orders_received')

    profile = request.user.farmer_profile
    order = get_object_or_404(Order, pk=pk, farmer=profile)
    if order.status != 'PENDING':
        messages.info(request, 'Only pending orders can be approved.')
        return redirect('store:farmer_orders_received')

    order.status = 'APPROVED'
    order.save(update_fields=['status'])
    if order.user_id:
        settings_obj = BuyerSettings.objects.filter(user=order.user).first()
        if settings_obj is None or settings_obj.order_updates:
            Notification.objects.create(
                recipient=order.user,
                title=f'Order #{order.pk} approved',
                message='Your order was approved by the farmer.',
                level='success',
                target_url=reverse('store:order_detail', args=[order.pk]),
                order=order,
                product=order.product,
            )
    messages.success(request, f'Approved order #{order.pk}.')
    return redirect('store:farmer_orders_received')


@farmer_required
@farmer_profile_complete_required
@farmer_phone_verified_required
def farmer_order_reject(request, pk):
    if request.method != 'POST':
        return redirect('store:farmer_orders_received')

    profile = request.user.farmer_profile
    order = get_object_or_404(Order, pk=pk, farmer=profile)
    if order.status != 'PENDING':
        messages.info(request, 'Only pending orders can be rejected.')
        return redirect('store:farmer_orders_received')

    order.status = 'REJECTED'
    order.save(update_fields=['status'])
    if order.user_id:
        settings_obj = BuyerSettings.objects.filter(user=order.user).first()
        if settings_obj is None or settings_obj.order_updates:
            Notification.objects.create(
                recipient=order.user,
                title=f'Order #{order.pk} rejected',
                message='Your order was rejected by the farmer.',
                level='warning',
                target_url=reverse('store:order_detail', args=[order.pk]),
                order=order,
                product=order.product,
            )
    messages.success(request, f'Rejected order #{order.pk}.')
    return redirect('store:farmer_orders_received')

