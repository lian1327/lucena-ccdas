from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        BARANGAY = "barangay", "Barangay Personnel"
        DEPT_STAFF = "dept_staff", "Department Staff"
        CITY_ADMIN = "city_admin", "City Administrator"
        MAYOR = "mayor", "Mayor's Office"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN)
    contact_number = models.CharField(max_length=20, blank=True)
    barangay = models.ForeignKey("geo.Barangay", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="users")
    department = models.ForeignKey("cases.Department", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="staff")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
