#!/usr/bin/env bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE="config.settings_test"

echo "Running Django system check..."
python manage.py check

echo "Running Backend Tests..."
python manage.py test financeiro_core -v 2

echo "Running Frontend Linter and Build..."
(
  cd financeiro-frontend
  npm ci
  npm run lint
  npm run build
)

echo "Baseline validation successful!"
