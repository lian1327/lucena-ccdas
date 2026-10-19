from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "role", "department", "division", "barangay", "is_active")
    list_filter = ("role", "department", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("CCADSS", {"fields": ("role", "contact_number", "barangay", "department", "division")}),
    )


admin.site.site_header = "CCADSS Administration"
admin.site.site_title = "CCADSS Admin"
admin.site.site_url = "http://localhost:5173/staff"
