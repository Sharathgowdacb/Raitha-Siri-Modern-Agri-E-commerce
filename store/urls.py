from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.home, name='home'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('help-center/', views.help_center, name='help_center'),
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('oauth/<str:provider>/', views.oauth_start, name='oauth_start'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path(
        'password-reset/',
        PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('dashboard/orders/', views.farmer_orders_received, name='farmer_orders_received'),
    path('dashboard/orders/<int:pk>/approve/', views.farmer_order_approve, name='farmer_order_approve'),
    path('dashboard/orders/<int:pk>/reject/', views.farmer_order_reject, name='farmer_order_reject'),
    path('buyer/dashboard/', views.buyer_dashboard, name='buyer_dashboard'),
    path('buyer/settings/', views.buyer_settings, name='buyer_settings'),
    path('buyer/profile/edit/', views.buyer_profile_edit, name='buyer_profile_edit'),
    path('buyer/change-password/', views.buyer_change_password, name='buyer_change_password'),
    path('buyer/notifications/', views.buyer_notifications_page, name='buyer_notifications'),
    path('buyer/notifications/api/', views.buyer_notifications_api, name='buyer_notifications_api'),
    path('buyer/notifications/read-all/', views.buyer_notifications_mark_all_read, name='buyer_notifications_mark_all_read'),
    path('buyer/notifications/<int:pk>/read/', views.buyer_notification_mark_read, name='buyer_notification_mark_read'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),

    # Farmer dashboard
    path('farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),
    path('farmer/profile/', views.farmer_profile_view, name='farmer_profile_view'),
    path('farmer/profile/edit/', views.farmer_profile_edit, name='farmer_profile_edit'),
    path('farmer/settings/', views.farmer_settings_view, name='farmer_settings_view'),
    path('farmer/phone/verify/', views.farmer_phone_verify, name='farmer_phone_verify'),
    path('farmer/notifications/', views.farmer_notifications, name='farmer_notifications'),
    path('farmer/notifications/<int:pk>/read/', views.farmer_notification_mark_read, name='farmer_notification_mark_read'),
    path('farmer/notifications/read-all/', views.farmer_notifications_mark_all_read, name='farmer_notifications_mark_all_read'),
    path('farmer/api/stats/', views.farmer_stats_api, name='farmer_stats_api'),
    path('farmer/products/', views.farmer_product_list, name='farmer_product_list'),
    path('farmer/products/add/', views.farmer_product_create, name='farmer_product_create'),
    path('farmer/products/<int:pk>/edit/', views.farmer_product_edit, name='farmer_product_edit'),
    path('farmer/products/<int:pk>/delete/', views.farmer_product_delete, name='farmer_product_delete'),
    # Cart and checkout
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/items/<int:item_id>/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/items/<int:item_id>/remove/', views.remove_cart_item, name='remove_cart_item'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/api/', views.cart_api, name='cart_api'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/api/', views.orders_api, name='orders_api'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/api/', views.order_api, name='order_api'),
]
