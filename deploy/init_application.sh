#!/bin/bash
# This file is for any extra management commands Hauki needs to initialize after migrations

set -e

./manage.py compilemessages
./manage.py create_e2e_test_data
