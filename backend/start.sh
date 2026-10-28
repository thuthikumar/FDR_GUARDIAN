#!/bin/sh
set -eu

python -c "from app.core.config import validate_security_settings, validate_storage_root; validate_security_settings(); validate_storage_root()"
python -m alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
