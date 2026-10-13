#!/usr/bin/env bash
# Render build step: install, collect static files, migrate, load the exam bilets.
set -o errexit

pip install -r ../requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py import_bilets
python manage.py import_road_signs --sample
python manage.py seed_demo
python manage.py seed_admin
