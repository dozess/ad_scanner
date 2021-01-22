source ./venv/bin/activate
celery -A tasks worker -l info -c 1

