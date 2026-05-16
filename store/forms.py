from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Product, FarmerProfile, BuyerProfile

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    is_farmer = forms.BooleanField(required=False, help_text='Register as a farmer (can add products)')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'is_farmer')


class FarmerProfileForm(forms.ModelForm):
    """Form for farmers to update their profile information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Enforce profile completion requirements at the form level.
        required_fields = [
            'full_name',
            'gender',
            'village',
            'address',
            'date_of_birth',
            'phone_number',
            'email',
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

        # Only require a photo if they don't already have one.
        if 'profile_photo' in self.fields:
            existing_photo = getattr(self.instance, 'profile_photo', None)
            self.fields['profile_photo'].required = not bool(existing_photo)
    
    class Meta:
        model = FarmerProfile
        fields = ('full_name', 'gender', 'village', 'address', 'date_of_birth', 'phone_number', 'email', 'profile_photo')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your full name',
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
            }),
            'village': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your village name',
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Enter your complete address',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'type': 'date',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your phone number',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your email address',
            }),
            'profile_photo': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*',
            }),
        }


class BuyerProfileForm(forms.ModelForm):
    """Form for buyers to update their profile information."""

    class Meta:
        model = BuyerProfile
        fields = ('full_name', 'phone_number', 'address', 'profile_photo')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your full name',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter your phone number',
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Enter your complete address',
            }),
            'profile_photo': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*',
            }),
        }


class ProductForm(forms.ModelForm):
    """Form for farmers to add/edit products with category-based subcategory filtering."""

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        subcategory = (cleaned_data.get('subcategory') or '').strip()
        price = cleaned_data.get('price')
        quantity = cleaned_data.get('quantity')

        if price is not None and price <= 0:
            self.add_error('price', 'Price must be greater than 0.')

        if quantity is not None and quantity <= 0:
            self.add_error('quantity', 'Quantity must be greater than 0.')

        # Subcategory is only applicable for Dairy.
        if category == 'Dairy':
            if not subcategory:
                self.add_error('subcategory', 'Subcategory is required for Dairy products.')
        else:
            # Normalize: prevent storing subcategory for non-dairy categories.
            cleaned_data['subcategory'] = ''

        return cleaned_data
    
    class Meta:
        model = Product
        fields = ('name', 'category', 'subcategory', 'quantity', 'price', 'description', 'image', 'is_available')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Product name',
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
            }),
            'subcategory': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Quantity',
                'type': 'number',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Price',
                'step': '0.01',
                'type': 'number',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Product description',
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*',
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded',
            }),
        }
