from django.db import models


class PriorityScore(models.Model):
    """Latest priority breakdown for a concern (Module 4). Each component is normalized 0–1."""

    concern = models.OneToOneField("concerns.Concern", on_delete=models.CASCADE, related_name="priority")
    severity_component = models.DecimalField(max_digits=5, decimal_places=4)
    affected_component = models.DecimalField(max_digits=5, decimal_places=4)
    duplicate_component = models.DecimalField(max_digits=5, decimal_places=4)
    delay_component = models.DecimalField(max_digits=5, decimal_places=4)
    duplicate_count = models.PositiveIntegerField(default=0)
    days_open = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=5, decimal_places=2)
    computed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.concern.reference_no}: {self.total}"
