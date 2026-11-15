#!/bin/sh
# Disposable local verification; never reuses a deployment database or volume.
set -eu
image=${1:-homeinventory:test}
container="homeinventory-smoke-$$"
volume="homeinventory-smoke-data-$$"
cleanup() {
    docker rm -f "$container" >/dev/null 2>&1 || true
    docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
docker volume create "$volume" >/dev/null
docker run --rm --volume "$volume:/data" --env DEBUG=True "$image" python manage.py migrate --noinput
docker run --detach --name "$container" --volume "$volume:/data" --env DEBUG=True "$image" >/dev/null
attempt=0
until docker exec "$container" python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=2).status == 200" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then docker logs "$container"; exit 1; fi
    sleep 1
done
test "$(docker exec "$container" id -u)" != 0
docker exec "$container" python -c "from pathlib import Path; import sqlite3; assert sqlite3.connect('/data/db.sqlite3').execute('select count(*) from django_migrations').fetchone()[0]>0; Path('/data/media/smoke.txt').write_text('persistent')"
docker restart "$container" >/dev/null
docker exec "$container" python -c "from pathlib import Path; assert Path('/data/media/smoke.txt').read_text()=='persistent'"
echo 'Docker migrations, non-root startup, health and persisted data verified.'
