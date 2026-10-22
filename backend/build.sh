#!/usr/bin/env bash
# Render build step (runs on every deploy). Free plan has no pre-deploy hook, so migrations run here.
set -o errexit
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
# Reference data (offices, categories, holidays, puroks) comes with the database you restore (DEPLOY.md step 2).
# Not re-seeded here on purpose: seed_reference_data would overwrite edits made in the admin, and
# import_boundaries replaces every purok (untagging reports) on each deploy.
