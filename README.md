# hauki

Django application and REST API for managing opening hours across all services

## Prerequisites

* PostgreSQL (>= 10)
* Python (>= 3.7)

## Installation

### Database

hauki runs on PostgreSQL. Install the server on Debian-based systems with:

```bash
sudo apt install postgresql
```

Then create a database user and the database itself as the `postgres` system user:

```bash
createuser <your username>
createdb -l fi_FI.UTF8 -E UTF8 -T template0 -O <your username> hauki
```

### Code

Clone the repo:
```
git clone https://github.com/City-of-Helsinki/hauki.git
cd hauki
```

Initiate a virtualenv and install the Python requirements:
```
pyenv virtualenv hauki-env
pyenv local hauki-env
pip install -r requirements.txt
```

Create `local_settings.py` in the repo base dir containing the following line:
```
DEBUG = True
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
