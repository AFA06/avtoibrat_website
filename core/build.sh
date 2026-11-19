#!/usr/bin/env bash
# Install, collect static files, migrate, and load bundled exam content.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

python -m pip install -r ../requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py import_bilets
python manage.py import_road_signs --official
python manage.py import_materials
if [[ -n "${DEMO_PASSWORD:-}" ]]; then
    python manage.py seed_demo
fi
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
    python manage.py seed_admin
fi
