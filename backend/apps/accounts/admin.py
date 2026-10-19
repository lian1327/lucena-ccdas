from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "barangay", "department", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("CCADSS", {"fields": ("role", "contact_number", "barangay", "department")}),
    )