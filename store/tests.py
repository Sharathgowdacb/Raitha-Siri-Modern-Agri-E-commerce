from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Category, FarmerProfile, Product, Cart, CartItem, Order, PhoneVerificationCode, Notification
from .forms import ProductForm


User = get_user_model()


class StoreModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='farmer1', password='pass12345')
        self.profile = FarmerProfile.objects.create(
            user=self.user,
            full_name='Farmer One',
            village='Green Village',
            address='123 Farm Road',
            gender='other',
            phone_number='9999999999',
            email='farmer1@example.com',
            is_farmer=True,
            date_of_birth=date(1990, 1, 1),
            profile_photo=SimpleUploadedFile(
                'profile.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
                content_type='image/png',
            ),
        )

    def test_category_slug_auto_generated(self):
        category = Category.objects.create(name='Leafy Greens')
        self.assertEqual(category.slug, 'leafy-greens')

    def test_product_slug_uniqueness(self):
        p1 = Product.objects.create(
            name='Tomato',
            price=Decimal('2.50'),
            category='Vegetables',
            quantity=5,
            farmer=self.profile,
        )
        p2 = Product.objects.create(
            name='Tomato',
            price=Decimal('3.00'),
            category='Vegetables',
            quantity=7,
            farmer=self.profile,
        )
        self.assertNotEqual(p1.slug, p2.slug)

    def test_cart_total_price(self):
        p1 = Product.objects.create(
            name='Carrot',
            price=Decimal('2.00'),
            category='Vegetables',
            quantity=10,
            farmer=self.profile,
        )
        p2 = Product.objects.create(
            name='Cabbage',
            price=Decimal('5.00'),
            category='Vegetables',
            quantity=12,
            farmer=self.profile,
        )
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=p1, quantity=2)
        CartItem.objects.create(cart=cart, product=p2, quantity=1)

        self.assertEqual(cart.total_price(), Decimal('9.00'))

    def test_product_form_requires_dairy_subcategory(self):
        form = ProductForm(
            data={
                'name': 'Milk',
                'category': 'Dairy',
                'subcategory': '',
                'quantity': 10,
                'price': '20.00',
                'description': 'Fresh milk',
                'is_available': True,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('subcategory', form.errors)

    def test_product_form_clears_subcategory_for_non_dairy(self):
        form = ProductForm(
            data={
                'name': 'Apple',
                'category': 'Fruits',
                'subcategory': 'Milk',
                'quantity': 5,
                'price': '4.00',
                'description': 'Apples',
                'is_available': True,
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['subcategory'], '')


class StoreViewTests(TestCase):
    def setUp(self):
        self.farmer_user = User.objects.create_user(username='farmer2', password='pass12345')
        self.customer = User.objects.create_user(username='customer1', password='pass12345')
        self.other_customer = User.objects.create_user(username='customer2', password='pass12345')
        self.profile = FarmerProfile.objects.create(
            user=self.farmer_user,
            full_name='Farmer Two',
            village='River Town',
            address='456 Market Street',
            gender='male',
            phone_number='8888888888',
            email='farmer2@example.com',
            is_farmer=True,
            date_of_birth=date(1992, 5, 5),
            profile_photo=SimpleUploadedFile(
                'profile.png',
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
                content_type='image/png',
            ),
        )

        self.cat_veg = Category.objects.create(name='Vegetables')
        self.cat_fruit = Category.objects.create(name='Fruits')

        self.potato = Product.objects.create(
            name='Potato',
            price=Decimal('3.00'),
            category='Vegetables',
            quantity=10,
            farmer=self.profile,
        )
        self.apple = Product.objects.create(
            name='Apple',
            price=Decimal('4.00'),
            category='Fruits',
            quantity=8,
            farmer=self.profile,
        )

    def test_home_filter_by_query_and_category(self):
        response = self.client.get(
            reverse('store:home'),
            {'q': 'Pot', 'category': self.cat_veg.slug},
        )
        products = list(response.context['products'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, 'Potato')

    def test_home_sort_by_price_ascending(self):
        response = self.client.get(reverse('store:home'), {'sort': 'price_asc'})
        products = list(response.context['products'])

        self.assertGreaterEqual(len(products), 2)
        self.assertEqual(products[0].name, 'Potato')
        self.assertEqual(products[1].name, 'Apple')

    def test_home_pagination(self):
        for i in range(15):
            Product.objects.create(
                name=f'Item {i}',
                price=Decimal('1.00'),
                category='Vegetables',
                quantity=5,
                farmer=self.profile,
            )

        response = self.client.get(reverse('store:home'), {'page': 2, 'sort': 'name'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertLessEqual(len(response.context['products']), 9)

    def test_add_to_cart(self):
        response = self.client.post(
            reverse('store:add_to_cart'),
            {'product_id': self.potato.id, 'quantity': 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['cart_count'], 2)

    def test_update_and_remove_cart_item(self):
        self.client.post(reverse('store:add_to_cart'), {'product_id': self.apple.id, 'quantity': 1})
        cart = Cart.objects.first()
        item = cart.items.first()

        update_response = self.client.post(
            reverse('store:update_cart_item', args=[item.id]),
            {'quantity': 4},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()['cart_count'], 4)

        remove_response = self.client.post(reverse('store:remove_cart_item', args=[item.id]))
        self.assertEqual(remove_response.status_code, 200)
        self.assertEqual(remove_response.json()['cart_count'], 0)

    def test_checkout_creates_order_and_clears_cart(self):
        self.client.login(username='customer1', password='pass12345')
        self.client.post(reverse('store:add_to_cart'), {'product_id': self.potato.id, 'quantity': 3})

        response = self.client.post(reverse('store:checkout'))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:order_history'))
        order = Order.objects.get(user=self.customer)
        self.assertEqual(order.product, self.potato)
        self.assertEqual(order.farmer, self.profile)
        self.assertEqual(order.quantity, 3)
        self.assertEqual(order.status, 'PENDING')
        self.assertEqual(order.total_price, Decimal('9.00'))

        self.assertTrue(
            Notification.objects.filter(recipient=self.farmer_user, order=order, product=self.potato).exists()
        )

        cart = Cart.objects.filter(user=self.customer).first()
        self.assertIsNotNone(cart)
        self.assertEqual(cart.items.count(), 0)

    def test_order_tracking_permissions(self):
        order = Order.objects.create(
            user=self.customer,
            farmer=self.profile,
            product=self.potato,
            quantity=1,
            total_price=Decimal('10.00'),
            status='PENDING',
        )

        self.client.login(username='customer1', password='pass12345')
        own_response = self.client.get(reverse('store:order_detail', args=[order.id]))
        self.assertEqual(own_response.status_code, 200)

        self.client.logout()
        self.client.login(username='customer2', password='pass12345')
        other_response = self.client.get(reverse('store:order_detail', args=[order.id]))
        self.assertEqual(other_response.status_code, 404)

    def test_register_customer_and_farmer_flows(self):
        customer_response = self.client.post(
            reverse('store:register'),
            {
                'username': 'newcustomer',
                'email': 'c@example.com',
                'password1': 'StrongPass123',
                'password2': 'StrongPass123',
            },
        )
        self.assertEqual(customer_response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newcustomer').exists())
        self.assertFalse(FarmerProfile.objects.filter(user__username='newcustomer').exists())

        farmer_response = self.client.post(
            reverse('store:register'),
            {
                'username': 'newfarmer',
                'email': 'f@example.com',
                'password1': 'StrongPass123',
                'password2': 'StrongPass123',
                'is_farmer': 'on',
            },
        )
        self.assertEqual(farmer_response.status_code, 302)
        self.assertTrue(FarmerProfile.objects.filter(user__username='newfarmer').exists())

    def test_login_logout_flow(self):
        login_response = self.client.post(
            reverse('store:login') + '?next=/',
            {'username': 'customer1', 'password': 'pass12345'},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

        logout_response = self.client.post(reverse('store:logout'))
        self.assertEqual(logout_response.status_code, 302)
        self.assertRedirects(logout_response, '/login/')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_farmer_dashboard_requires_farmer_profile(self):
        self.client.login(username='customer1', password='pass12345')
        response = self.client.get(reverse('store:farmer_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_farmer_dashboard_for_farmer_user(self):
        self.client.login(username='farmer2', password='pass12345')
        response = self.client.get(reverse('store:farmer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_farmer_profile_requires_farmer(self):
        self.client.login(username='customer1', password='pass12345')
        response = self.client.get(reverse('store:farmer_profile_view'))
        self.assertEqual(response.status_code, 302)

    def test_farmer_profile_for_farmer_user(self):
        self.client.login(username='farmer2', password='pass12345')
        response = self.client.get(reverse('store:farmer_profile_view'))
        self.assertEqual(response.status_code, 200)

    def test_farmer_phone_verification_send_creates_code(self):
        self.client.login(username='farmer2', password='pass12345')

        response = self.client.post(
            reverse('store:farmer_phone_verify'),
            {'action': 'send'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_phone_verify'))
        self.assertTrue(self.profile.phone_verification_codes.exists())

    def test_farmer_phone_verification_verify_sets_verified(self):
        self.client.login(username='farmer2', password='pass12345')

        PhoneVerificationCode.issue(self.profile, '123456', ttl_minutes=10)
        response = self.client.post(
            reverse('store:farmer_phone_verify'),
            {'action': 'verify', 'code': '123456'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_settings_view'))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_verified)

    def test_phone_change_resets_verification(self):
        self.profile.is_verified = True
        self.profile.save(update_fields=['is_verified'])

        self.profile.phone_number = '7777777777'
        self.profile.save(update_fields=['phone_number'])

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_verified)

    def test_farmer_stats_api_requires_farmer(self):
        self.client.login(username='customer1', password='pass12345')
        response = self.client.get(reverse('store:farmer_stats_api'))
        self.assertEqual(response.status_code, 403)

    def test_farmer_stats_api_for_farmer_user(self):
        self.client.login(username='farmer2', password='pass12345')
        response = self.client.get(reverse('store:farmer_stats_api'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('total_products', payload)
        self.assertIn('available_products', payload)
        self.assertIn('recent_products', payload)

    def test_farmer_product_crud(self):
        self.profile.is_verified = True
        self.profile.save(update_fields=['is_verified'])
        self.client.login(username='farmer2', password='pass12345')
        create_response = self.client.post(
            reverse('store:farmer_product_create'),
            {
                'name': 'Spinach',
                'category': 'Vegetables',
                'quantity': 12,
                'description': 'Fresh spinach',
                'price': '6.00',
                'is_available': True,
            },
        )
        self.assertEqual(create_response.status_code, 302)
        created = Product.objects.get(name='Spinach')

        edit_response = self.client.post(
            reverse('store:farmer_product_edit', args=[created.id]),
            {
                'name': 'Spinach Premium',
                'category': 'Vegetables',
                'quantity': 15,
                'description': 'Updated',
                'price': '7.00',
                'is_available': True,
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.name, 'Spinach Premium')

        delete_response = self.client.post(reverse('store:farmer_product_delete', args=[created.id]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Product.objects.filter(id=created.id).exists())

    def test_farmer_product_create_requires_phone_verification(self):
        # Not verified by default
        self.client.login(username='farmer2', password='pass12345')
        response = self.client.post(
            reverse('store:farmer_product_create'),
            {
                'name': 'Unverified Item',
                'category': 'Vegetables',
                'quantity': 1,
                'description': 'Should be blocked',
                'price': '1.00',
                'is_available': True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_phone_verify'))

    def test_farmer_order_approve_requires_phone_verification(self):
        order = Order.objects.create(
            user=self.customer,
            farmer=self.profile,
            product=self.potato,
            quantity=1,
            total_price=Decimal('3.00'),
            status='PENDING',
        )

        self.client.login(username='farmer2', password='pass12345')
        response = self.client.post(reverse('store:farmer_order_approve', args=[order.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_phone_verify'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'PENDING')

    def test_farmer_order_approve_creates_notification_for_buyer(self):
        self.profile.is_verified = True
        self.profile.save(update_fields=['is_verified'])

        order = Order.objects.create(
            user=self.customer,
            farmer=self.profile,
            product=self.potato,
            quantity=1,
            total_price=Decimal('3.00'),
            status='PENDING',
        )

        self.client.login(username='farmer2', password='pass12345')
        response = self.client.post(reverse('store:farmer_order_approve', args=[order.id]))
        self.assertEqual(response.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, 'APPROVED')
        self.assertTrue(Notification.objects.filter(recipient=self.customer, order=order).exists())

    def test_farmer_notifications_page_lists_notifications(self):
        Notification.objects.create(
            recipient=self.farmer_user,
            title='Test notification',
            message='Hello',
            level='info',
        )

        self.client.login(username='farmer2', password='pass12345')
        response = self.client.get(reverse('store:farmer_notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notifications')
        self.assertContains(response, 'Test notification')

    def test_role_based_login_redirects_farmer(self):
        self.farmer_user.email = 'farmer2@example.com'
        self.farmer_user.save(update_fields=['email'])

        response = self.client.post(
            reverse('store:login'),
            {
                'email': 'farmer2@example.com',
                'password': 'pass12345',
                'role': 'Farmer',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_dashboard'))

    def test_role_based_login_redirects_buyer(self):
        self.customer.email = 'customer1@example.com'
        self.customer.save(update_fields=['email'])

        response = self.client.post(
            reverse('store:login'),
            {
                'email': 'customer1@example.com',
                'password': 'pass12345',
                'role': 'Buyer',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:buyer_dashboard'))

    def test_role_based_login_blocks_non_farmer_on_farmer_role(self):
        self.customer.email = 'customer1@example.com'
        self.customer.save(update_fields=['email'])

        response = self.client.post(
            reverse('store:login'),
            {
                'email': 'customer1@example.com',
                'password': 'pass12345',
                'role': 'Farmer',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not registered as a farmer')

    def test_buyer_dashboard_requires_authentication(self):
        response = self.client.get(reverse('store:buyer_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_buyer_dashboard_for_logged_in_buyer(self):
        self.client.login(username='customer1', password='pass12345')
        response = self.client.get(reverse('store:buyer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_role_switch_button_visible_for_farmer_on_buyer_dashboard(self):
        self.client.login(username='farmer2', password='pass12345')
        response = self.client.get(reverse('store:buyer_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('store:farmer_dashboard'))

    def test_forgot_password_route_and_link(self):
        login_page = self.client.get(reverse('store:login'))
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, reverse('store:password_reset'))

        reset_page = self.client.get(reverse('store:password_reset'))
        self.assertEqual(reset_page.status_code, 200)
