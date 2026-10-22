"""
One-time copy of local photos (backend/media/) to the production object storage, keeping the same paths,
so records restored from your local database still find their images.

    python manage.py upload_media              # skips files that are already there
    python manage.py upload_media --dry-run
Run on your computer with the MEDIA_S3_* variables set in .env.
"""
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload backend/media/ to the configured S3-compatible storage."

    def add_arguments(self, p):
        p.add_argument("--dry-run", action="store_true")

    def handle(self, *a, **o):
        if isinstance(default_storage, FileSystemStorage):
            raise CommandError("Default storage is the local disk. Set MEDIA_S3_* variables first.")
        root = Path(settings.MEDIA_ROOT)
        files = [p for p in root.rglob("*") if p.is_file()]
        up = skip = 0
        for p in files:
            key = p.relative_to(root).as_posix()
            if default_storage.exists(key):
                skip += 1
                continue
            if not o["dry_run"]:
                with p.open("rb") as fh:
                    default_storage.save(key, File(fh))
            up += 1
            if up % 50 == 0:
                self.stdout.write(f"  {up} uploaded…")
        self.stdout.write(self.style.SUCCESS(f"{'Would upload' if o['dry_run'] else 'Uploaded'} {up}, already there {skip}."))
