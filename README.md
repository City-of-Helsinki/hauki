# hauki

Django application and REST API for managing opening hours across all services

## Issue tracking
Jira: https://helsinkisolutionoffice.atlassian.net/projects/HAUKI/issues/?filter=allissues

## Prerequisites

* PostgreSQL (>= 10) with PostGIS extension
* Python (>= 3.7)

## Installation

### Database

hauki runs on PostgreSQL with the PostGIS extension. Install the server on Debian-based systems with:

```bash
sudo apt install postgresql
sudo apt install postgresql-10-postgis-2.4 
```

Then create a database user and the database itself as the `postgres` system user, and add the PostGIS extension:

```bash
createuser <your username>
createdb -l fi_FI.UTF-8 -E UTF8 -T template0 -O <your username> hauki
psql -d hauki -c 'CREATE EXTENSION postgis;'
```

### Development

Clone the repo:
```
git clone https://github.com/City-of-Helsinki/hauki.git
cd hauki
```

Initiate a virtualenv and install the Python development requirements:
```
pyenv virtualenv hauki-env
pyenv local hauki-env
pip install -r dev-requirements.txt
```

Create `local_settings.py` in the repo base dir containing the following line:
```
DEBUG = True
```

Run tests:
```
pytest
```

Run migrations:
```
python manage.py migrate
```

Create admin user:
```
python manage.py createsuperuser
```

Run dev server:
```
python manage.py runserver
```
and open your browser to http://127.0.0.1:8000/admin/ using the admin user credentials.
