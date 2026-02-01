web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level info
