from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from store.models import FarmerProfile, Product


class Command(BaseCommand):
    help = "Seed demo data for a farmer dashboard."

    def handle(self, *args, **options):
        User = get_user_model()

        farmer_username = "farmer_demo"
        farmer_email = "farmer_demo@example.com"
        farmer_password = "FarmerPass123"

        buyer_username = "buyer_demo"
        buyer_email = "buyer_demo@example.com"
        buyer_password = "BuyerPass123"

        farmer_user, farmer_created = User.objects.get_or_create(
            username=farmer_username,
            defaults={"email": farmer_email},
        )
        if farmer_created:
            farmer_user.set_password(farmer_password)
            farmer_user.save()

        profile, _ = FarmerProfile.objects.get_or_create(
            user=farmer_user,
            defaults={
                "full_name": "Demo Farmer",
                "village": "Green Valley",
                "address": "123 Farm Road, Green Valley",
                "gender": "male",
                "phone_number": "9999999999",
                "email": farmer_email,
                "is_farmer": True,
            },
        )

        buyer_user, buyer_created = User.objects.get_or_create(
            username=buyer_username,
            defaults={"email": buyer_email},
        )
        if buyer_created:
            buyer_user.set_password(buyer_password)
            buyer_user.save()

        demo_products = [
            {
                "name": "Fresh Tomatoes",
                "category": "Vegetables",
                "quantity": 120,
                "price": Decimal("35.00"),
                "description": "Bright red farm tomatoes.",
                "is_available": True,
            },
            {
                "name": "Organic Spinach",
                "category": "Vegetables",
                "quantity": 75,
                "price": Decimal("25.00"),
                "description": "Leafy greens harvested this week.",
                "is_available": True,
            },
            {
                "name": "Golden Mangoes",
                "category": "Fruits",
                "quantity": 60,
                "price": Decimal("80.00"),
                "description": "Sweet mangoes from local orchards.",
                "is_available": True,
            },
            {
                "name": "Farm Milk",
                "category": "Dairy",
                "subcategory": "Milk",
                "quantity": 40,
                "price": Decimal("45.00"),
                "description": "Fresh cow milk, 1L packs.",
                "is_available": True,
            },
            {
                "name": "Brown Rice",
                "category": "Grains",
                "quantity": 90,
                "price": Decimal("55.00"),
                "description": "Whole grain brown rice.",
                "is_available": True,
            },
        ]

        created_count = 0
        for payload in demo_products:
            product, created = Product.objects.get_or_create(
                farmer=profile,
                name=payload["name"],
                defaults=payload,
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
        self.stdout.write("Demo farmer login:")
        self.stdout.write(f"  username: {farmer_username}")
        self.stdout.write(f"  password: {farmer_password}")
        self.stdout.write("Demo buyer login:")
        self.stdout.write(f"  username: {buyer_username}")
        self.stdout.write(f"  password: {buyer_password}")
        self.stdout.write(f"Products created: {created_count}")
