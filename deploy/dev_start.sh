#!/bin/bash

set -e

# Wait for database present as docker compose is bringing it up in paraller
if [[ "$WAIT_FOR_IT_ADDRESS" ]]; then
    until nc --verbose --wait 30 -z "$WAIT_FOR_IT_ADDRESS" 5432
    do
      echo "Waiting for postgres database connection..."
      sleep 1
    done
    echo "Database is up!"
fi

./manage.py migrate

exec ./manage.py runserver 0:8000
