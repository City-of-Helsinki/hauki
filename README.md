# hauki

[![Build Status](https://dev.azure.com/City-of-Helsinki/infra/_apis/build/status/hauki/City-of-Helsinki.hauki?branchName=master)](https://dev.azure.com/City-of-Helsinki/infra/_build/latest?definitionId=14&branchName=master)

Django application and REST API for managing opening hours across all services

## Issue tracking
Jira: https://helsinkisolutionoffice.atlassian.net/projects/HAUKI/issues/?filter=allissues

## Prerequisites

* Docker
* Docker Compose

OR

* PostgreSQL (>= 10)
* Python (>= 3.7)

## Docker Installation

### Development

The easiest way to develop is

```
git clone https://github.com/City-of-Helsinki/hauki.git
cd hauki
docker-compose run dev
```

and open your browser to http://127.0.0.1:8000/.

Run tests with 

```
docker-compose run dev test
```

If you wish to change settings when developing, copy the development config file example `config_dev.env.example`
to `config_dev.env`:
```
cp config_dev.env.example config_dev.env
```

Also, uncomment line https://github.com/City-of-Helsinki/hauki/blob/master/docker-compose.yml#L29 to activate
configuring the dev environment with a local file.

### Production

Correspondingly, production container can be brought up with

```
docker-compose run deploy
```

In production, configuration is done with corresponding environment variables.

## Local installation

### Database

hauki runs on PostgreSQL. Install the server on Debian-based systems with:

```bash
sudo apt install postgresql
```

Then create a database user and the database itself as the `postgres` system user:

```bash
createuser <your username>
createdb -l fi_FI.UTF-8 -E UTF8 -T template0 -O <your username> hauki;'
```

### Development

Clone the repo:
```
git clone https://github.com/City-of-Helsinki/hauki.git
cd hauki
```

Initiate a virtualenv and install the Python requirements plus development requirements:
```
pyenv virtualenv hauki-env
pyenv local hauki-env
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

Copy the development config file example `config_dev.env.example` to `config_dev.env` 
(feel free to edit the configuration file if you have any settings you wish to change):
```
cp config_dev.env.example config_dev.env
```

Run tests:
```
pytest
```

Run migrations:
```
python manage.py migrate
```

Run dev server:
```
python manage.py runserver
```
and open your browser to http://127.0.0.1:8000/.

## Importing data

Currently, importing units from City of Helsinki unit registry (TPREK) is supported. Import all units from TPREK API by
```
python manage.py hours_import tprek --all
```
Opening hours may be imported from Helmet libraries. This requires that the libraries are already present in the database (e.g. imported from TPREK). Import future opening hours from Helmet API by
```
python manage.py hours_import kirjastot --openings
```
