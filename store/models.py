from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


class FarmerProfile(models.Model):
    """Profile data for farmers, linked one-to-one to Django `User`."""

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    full_name = models.CharField(max_length=255)
    village = models.CharField(max_length=255)
    address = models.TextField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_photo = models.ImageField(upload_to='farmers/profiles/', blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    is_farmer = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # If the farmer changes their phone number, phone verification must be redone.
        if self.pk:
            previous_phone = (
                FarmerProfile.objects.filter(pk=self.pk)
                .values_list('phone_number', flat=True)
                .first()
            )
            if previous_phone is not None and previous_phone != self.phone_number:
                self.is_verified = False
                update_fields = kwargs.get('update_fields')
                if update_fields is not None:
                    kwargs['update_fields'] = set(update_fields) | {'is_verified'}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Farmer: {self.user.get_full_name() or self.user.username}"

    def is_profile_complete(self) -> bool:
        required_str_fields = [
            self.full_name,
            self.gender,
            self.village,
            self.address,
            self.phone_number,
            self.email,
        ]
        if any(not (value or '').strip() for value in required_str_fields):
            return False
        if not self.date_of_birth:
            return False
        if not self.profile_photo:
            return False
        return True


class BuyerProfile(models.Model):
    """Profile data for buyers, linked one-to-one to Django `User`."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_profile')
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='buyers/profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Buyer: {self.user.get_full_name() or self.user.username}"


class BuyerSettings(models.Model):
    """Buyer settings for theme and notifications."""

    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_settings')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    email_updates = models.BooleanField(default=True)
    sms_updates = models.BooleanField(default=False)
    order_updates = models.BooleanField(default=True)
    product_updates = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BuyerSettings: {self.user_id}"


class SupportRequest(models.Model):
    """Support request submitted from the Help Center."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_requests')
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SupportRequest #{self.pk} ({self.email})"


class PhoneVerificationCode(models.Model):
    """One-time code for farmer phone verification.

    For now we "send" the OTP by logging/printing from the view layer.
    Production SMS integration (e.g., Twilio) can plug into the same flow.
    """

    profile = models.ForeignKey(FarmerProfile, on_delete=models.CASCADE, related_name='phone_verification_codes')
    phone_number = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['profile', '-created_at']),
        ]

    def __str__(self):
        return f"Phone OTP for {self.profile_id} ({self.phone_number})"

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def check_and_consume(self, raw_code: str, *, max_attempts: int = 5) -> bool:
        """Return True if code is valid, and mark it consumed.

        Increments attempts on each call until max_attempts.
        """

        if self.is_consumed or self.is_expired:
            return False

        if self.attempts >= max_attempts:
            return False

        self.attempts = self.attempts + 1
        is_ok = check_password(raw_code, self.code_hash)
        if is_ok:
            self.consumed_at = timezone.now()
        self.save(update_fields=['attempts', 'consumed_at'])
        return is_ok

    @classmethod
    def issue(cls, profile: FarmerProfile, raw_code: str, *, ttl_minutes: int = 10) -> 'PhoneVerificationCode':
        return cls.objects.create(
            profile=profile,
            phone_number=profile.phone_number,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timezone.timedelta(minutes=ttl_minutes),
        )


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Product offered by a farmer."""

    CATEGORY_CHOICES = [
        ('Vegetables', 'Vegetables'),
        ('Fruits', 'Fruits'),
        ('Grains', 'Grains'),
        ('Dairy', 'Dairy'),
    ]

    DAIRY_SUBCATEGORY_CHOICES = [
        ('Milk', 'Milk'),
        ('Butter', 'Butter'),
        ('Ghee', 'Ghee'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subcategory = models.CharField(max_length=20, choices=DAIRY_SUBCATEGORY_CHOICES, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    farmer = models.ForeignKey(FarmerProfile, on_delete=models.CASCADE, related_name='products')
    description = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200]
            slug = base
            n = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Cart(models.Model):
    """Shopping cart. If `user` is null, cart may be used for anonymous/session users."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart #{self.pk} ({self.user})"

    def total_price(self):
        return sum(item.subtotal() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Wishlist(models.Model):
    """User's wishlist for products."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class Order(models.Model):
    """A single-line order for one product, routed to one farmer for approval."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders')
    farmer = models.ForeignKey(FarmerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_orders')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.user} - {self.status}"

    def calculate_total(self):
        unit_price = self.product.price if self.product else 0
        self.total_price = unit_price * self.quantity
        return self.total_price


class Notification(models.Model):
    """In-app notification for a recipient user."""

    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=140)
    message = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    target_url = models.CharField(max_length=255, blank=True)

    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"Notification to {self.recipient_id}: {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
