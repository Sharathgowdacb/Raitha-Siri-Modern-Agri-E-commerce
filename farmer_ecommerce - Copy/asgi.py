"""ASGI config for farmer_ecommerce project."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmer_ecommerce.settings')
application = get_asgi_application()
