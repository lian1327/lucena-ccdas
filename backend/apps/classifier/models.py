from django.conf import settings
from django.db import models


class ModelVersion(models.Model):
    """One trained classifier. Exactly one is active; older ones are kept with their evaluation for comparison."""

    version = models.PositiveIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    trained_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    algorithm = models.CharField(max_length=60)
    file = models.CharField(max_length=255, help_text="Path of the joblib artifact under ML_MODEL_DIR.")
    n_train = models.PositiveIntegerField(default=0)
    n_test = models.PositiveIntegerField(default=0)
    data_sources = models.JSONField(default=dict, blank=True, help_text='{"synthetic": 3200, "real": 0, "extra_csv": 0}')
    metrics = models.JSONField(default=dict, blank=True, help_text="Held-out test metrics, model comparison, confusion matrix.")
    challenge_metrics = models.JSONField(default=dict, blank=True, help_text="Hand-written challenge set (ml/challenge_set.csv).")
    is_active = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]

    def __str__(self):
        return f"v{self.version} {self.algorithm}{' (active)' if self.is_active else ''}"
