from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class RoleBasedAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """Redirect after login (including social) based on role selection.

        Priority:
        1) Explicit role selected on the login page (stored in session)
        2) Existing user role (FarmerProfile presence)
        3) Default (home)
        """
        role = None
        if request is not None:
            role = request.session.get("selected_role")

        user = getattr(request, "user", None) if request is not None else None

        if role == "Farmer" or (user and hasattr(user, "farmer_profile")):
            return reverse('store:farmer_dashboard')
        return reverse('store:buyer_dashboard')
