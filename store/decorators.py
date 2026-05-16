"""
Decorators and utilities for farmer dashboard access control.
Ensures only farmers with valid FarmerProfile can access dashboard routes.
"""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from .models import FarmerProfile


def buyer_required(view_func):
    """Restrict views to authenticated buyers (non-farmers)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in first.')
            return redirect('store:login')

        profile = getattr(request.user, 'farmer_profile', None)
        if profile and getattr(profile, 'is_farmer', False):
            messages.error(request, 'Farmer accounts cannot access buyer pages.')
            return redirect('store:farmer_dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper


def farmer_required(view_func):
    """
    Decorator to restrict dashboard views to farmers only.
    Checks if user has FarmerProfile with is_farmer=True
    
    Usage:
        @farmer_required
        def my_dashboard_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # First check if user is logged in
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in first.')
            return redirect('store:login')
        
        # Check if user has a farmer profile
        try:
            farmer_profile = request.user.farmer_profile
        except FarmerProfile.DoesNotExist:
            messages.error(request, 'You are not registered as a farmer.')
            return redirect('store:home')
        
        # Check if is_farmer flag is True
        if not farmer_profile.is_farmer:
            messages.error(request, 'You do not have farmer permissions.')
            return redirect('store:home')
        
        # All checks passed, execute the view
        return view_func(request, *args, **kwargs)
    
    return wrapper


def farmer_profile_required(view_func):
    """
    Alternative decorator that returns 403 Forbidden instead of redirect.
    Use for API endpoints or AJAX requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden('Authentication required.')
        
        try:
            farmer_profile = request.user.farmer_profile
        except FarmerProfile.DoesNotExist:
            return HttpResponseForbidden('Farmer profile not found.')
        
        if not farmer_profile.is_farmer:
            return HttpResponseForbidden('Farmer status required.')
        
        # Add farmer profile to request for convenient access
        request.farmer_profile = farmer_profile
        return view_func(request, *args, **kwargs)
    
    return wrapper


def farmer_profile_complete_required(view_func):
    """Redirect farmers to profile completion if required fields are missing."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in first.')
            return redirect('store:login')

        try:
            farmer_profile = request.user.farmer_profile
        except FarmerProfile.DoesNotExist:
            messages.error(request, 'You are not registered as a farmer.')
            return redirect('store:home')

        if not farmer_profile.is_farmer:
            messages.error(request, 'You do not have farmer permissions.')
            return redirect('store:home')

        if not farmer_profile.is_profile_complete():
            messages.info(request, 'Please complete your profile to continue.')
            return redirect('store:farmer_profile_edit')

        return view_func(request, *args, **kwargs)

    return wrapper


def farmer_phone_verified_required(view_func):
    """Require farmers to verify phone number before performing sensitive actions."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in first.')
            return redirect('store:login')

        try:
            farmer_profile = request.user.farmer_profile
        except FarmerProfile.DoesNotExist:
            messages.error(request, 'You are not registered as a farmer.')
            return redirect('store:home')

        if not farmer_profile.is_farmer:
            messages.error(request, 'You do not have farmer permissions.')
            return redirect('store:home')

        if not farmer_profile.is_verified:
            messages.info(request, 'Please verify your phone number to continue.')
            return redirect('store:farmer_phone_verify')

        return view_func(request, *args, **kwargs)

    return wrapper
