"""
Copy trained classifier files between this machine and the production object storage.

    python manage.py sync_models --push     upload backend/ml/models/*.joblib (run locally with the MEDIA_S3_* vars set)
    python manage.py sync_models --pull     download the active model (the server also does this on its own)

The server loads the active model from storage after every restart, so retrain on your own computer
(free hosts have too little memory), then --push, then activate it on the AI Classifier page.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.classifier import pipeline
from apps.classifier.models import ModelVersion


class Command(BaseCommand):
    help = "Push/pull trained classifier files to/from the media object storage."

    def add_arguments(self, p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--push", action="store_true")
        g.add_argument("--pull", action="store_true")

    def handle(self, *a, **o):
        if pipeline._remote_storage() is None:
            raise CommandError("Default storage is the local disk. Set MEDIA_S3_* variables first.")
        if o["push"]:
            files = sorted(pipeline.model_dir().glob("*.joblib"))
            if not files:
                raise CommandError(f"No model files in {pipeline.model_dir()}")
            for f in files:
                pipeline._push_model(f.name)
                self.stdout.write(f"uploaded {f.name}")
            return
        mv = ModelVersion.objects.filter(is_active=True).first()
        if not mv:
            raise CommandError("No active model version in the database.")
        ok = pipeline._pull_model(mv.file)
        self.stdout.write(self.style.SUCCESS(f"v{mv.version}: {'downloaded' if ok else 'not found in storage'}"))
