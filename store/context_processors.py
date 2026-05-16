from .models import Cart


def cart_summary(request):
    """Expose cart count and total to all templates for server-side rendering."""
    cart = None

    if getattr(request, 'user', None) and request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(pk=cart_id).first()

    if not cart:
        return {'cart_count': 0, 'cart_total': '0.00'}

    count = sum(item.quantity for item in cart.items.all())
    return {'cart_count': count, 'cart_total': f"{cart.total_price():.2f}"}


def notifications_summary(request):
    """Expose unread notification count for authenticated farmers."""

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'farmer_unread_notifications_count': 0}

    # Avoid heavy queries for buyers/non-farmers.
    profile = getattr(user, 'farmer_profile', None)
    if not profile or not getattr(profile, 'is_farmer', False):
        return {'farmer_unread_notifications_count': 0}

    from .models import Notification

    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()
    return {'farmer_unread_notifications_count': unread_count}


def buyer_notifications_summary(request):
    """Expose buyer notification count and latest items for the navbar dropdown."""

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'buyer_unread_notifications_count': 0,
            'buyer_notifications': [],
        }

    profile = getattr(user, 'farmer_profile', None)
    if profile and getattr(profile, 'is_farmer', False):
        return {
            'buyer_unread_notifications_count': 0,
            'buyer_notifications': [],
        }

    from .models import Notification

    notifications = (
        Notification.objects.filter(recipient=user)
        .order_by('-created_at')[:5]
    )
    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()
    return {
        'buyer_unread_notifications_count': unread_count,
        'buyer_notifications': notifications,
    }


def buyer_order_summary(request):
    """Expose buyer order counts for dashboard widgets."""

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'buyer_order_total': 0,
            'buyer_order_pending': 0,
            'buyer_order_approved': 0,
            'buyer_order_rejected': 0,
        }

    profile = getattr(user, 'farmer_profile', None)
    if profile and getattr(profile, 'is_farmer', False):
        return {
            'buyer_order_total': 0,
            'buyer_order_pending': 0,
            'buyer_order_approved': 0,
            'buyer_order_rejected': 0,
        }

    from django.db.models import Count, Q
    from .models import Order

    summary = Order.objects.filter(user=user).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        approved=Count('id', filter=Q(status='APPROVED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
    )
    return {
        'buyer_order_total': summary['total'] or 0,
        'buyer_order_pending': summary['pending'] or 0,
        'buyer_order_approved': summary['approved'] or 0,
        'buyer_order_rejected': summary['rejected'] or 0,
    }


def buyer_settings_summary(request):
    """Expose buyer theme preference and full settings to all templates."""

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        from .models import BuyerSettings
        default_settings = BuyerSettings(theme='light')
        return {
            'buyer_theme': 'light',
            'buyer_settings': default_settings,
        }

    profile = getattr(user, 'farmer_profile', None)
    if profile and getattr(profile, 'is_farmer', False):
        from .models import BuyerSettings
        default_settings = BuyerSettings(theme='light')
        return {
            'buyer_theme': 'light',
            'buyer_settings': default_settings,
        }

    from .models import BuyerSettings

    settings_obj, _ = BuyerSettings.objects.get_or_create(user=user)
    return {
        'buyer_theme': settings_obj.theme if settings_obj else 'light',
        'buyer_settings': settings_obj,
    }
