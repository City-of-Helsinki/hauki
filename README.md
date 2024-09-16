# hauki

[![Build Status](https://dev.azure.com/City-of-Helsinki/hauki/_apis/build/status/City-of-Helsinki.hauki-experimental?branchName=master)](https://dev.azure.com/City-of-Helsinki/hauki/_build/latest?definitionId=21&branchName=main)

Django application and REST API for managing opening hours across all services

## Issue tracking
Jira: https://helsinkisolutionoffice.atlassian.net/projects/HAUKI/issues/?filter=allissues

## Documentation

API documentation automatically generated from OpenAPI schema can be found from [http://127.0.0.1:8000/api_docs/](http://127.0.0.1:8000/api_docs/).

The OpenAPI schema is served from [http://127.0.0.1:8000/openapi/](http://127.0.0.1:8000/openapi/).

(Assuming you are running the project locally)

## Prerequisites

* Docker
* Docker Compose

OR

* PostgreSQL (>= 10)
* Python (>= 3.9)

## Docker Installation

### Development

The easiest way to develop is

```
git clone https://github.com/City-of-Helsinki/hauki.git
cd hauki
```

Copy the development config file example `config_dev.env.example`
to `config_dev.env` (feel free to edit the configuration file if you have any settings you wish to change):
```
cp config_dev.env.example config_dev.env
docker compose up dev
```

and open your browser to http://127.0.0.1:8000/.

Run tests with

```
docker compose run dev test
```

Also, uncomment line https://github.com/City-of-Helsinki/hauki/blob/main/compose.yml#L27-L28 to activate
configuring the dev environment with a local file.

### Production

Production setup will require a separate PostgreSQL database server (see "Database") below. Once you have a
PostGIS database server running,

```
docker run hauki
```

In production, configuration is done with corresponding environment variables. See `config_dev.env.example`
for the environment variables needed to set in production.

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

#### Prerequisites

* [Pyenv](https://github.com/pyenv/pyenv)
* [Pyenv virtualenv](https://github.com/pyenv/pyenv-virtualenv)

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
pip install -r requirements-dev.txt
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

## Pre-commit hooks

Before committing files to the repository it's advisable to use the configured pre-commit hooks (see [`.pre-commit-config.yaml`](./.pre-commit-config.yaml)). The CI pipeline will fail if the files are not formatted correctly.

pre-commit is included in the requirements-dev.txt. After cloning the repository you should install the requirements and then install the hooks by running:

```
pre-commit install
```

The pre-commit hook runs isort, black and flake8 checks on the staged files before committing. The badly formatted files are not automatically changed, you have to run black and/or isort yourself.

You can at any time run the following command if you would like to check all of the files.

```
pre-commit run --all-files
```

## Commit message format

!!!Note New commit messages must adhere to the [Conventional Commits](https://www.conventionalcommits.org/)
specification, and line length is limited to 72 characters.

When [`pre-commit`](https://pre-commit.com/) is in use, [`commitlint`](https://github.com/conventional-changelog/commitlint)
checks new commit messages for the correct format.

## Git blame ignore refs

Project includes a `.git-blame-ignore-revs` file for ignoring certain commits from `git blame`.
This can be useful for ignoring e.g. formatting commits, so that it is more clear from `git blame`
where the actual code change came from. Configure your git to use it for this project with the
following command:

```shell
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

## Release

### Publish to Dev environment

#### Review environment

New commit to PR will trigger review pipeline. Review pipeline builds application and deploys a dynamic environment to the Openshift dev. The review environment can be used to verify PR.

#### Dev environment

Deployment to dev environment is handled automatically from main branch. Updates to main branch triggers
azure pipeline that will run tests, build and deploy to dev environment hosted by red hat openshift.
Currently azure-pipeline is configured directly from version control, but red hat openshift configuration resides in openshift cluster.

### Release to Test, Stage and Production environments

Release is done by [release-please](https://helsinkisolutionoffice.atlassian.net/wiki/spaces/DD/pages/8278966368/Releases+with+release-please).
It creates release PR based on commits messages. Merge of the PR will trigger a release pipeline that build and deploys to stage and test environments automatically.

Release-please update the package.json version number automatically and it is included to release PR.

#### Publish to production environments
Publishing to production requires manual approval in the DevOps release pipeline.

## Importing data

Currently, importing *resources* from Helsinki metropolitan area unit registry (TPREK) is supported. Import all resources from [TPREK API](https://www.hel.fi/palvelukarttaws/restpages/ver4.html) by
```
python manage.py hours_import tprek --resources
```

This imports all TPREK units and some of their child resources that are expected to have opening hours. Identical child resources may be merged into a single child having multiple parents, as they most often will have the same opening hours. Merging identical child resources can be done by running the import instead with
```
python manage.py hours_import tprek --resources --merge
```

---

*Opening hours* may be imported for any Finnish libraries from the [kirjastot.fi API](https://api.kirjastot.fi/).

This requires that libraries already exist in the database (imported from TPREK or created by other means), with correct kirkanta ids in the `identifiers` field. The kirjastot.fi importer doesn't currently import any libraries into the database, but you may suggest a PR that imports all libraries as resources, if you wish to import libraries outside the Helsinki area from the kirjastot.fi API.

Import library opening hours from the kirjastot.fi API for all resources that have kirkanta identifiers by
```
python manage.py hours_import kirjastot --openings
```

This imports opening hours for the libraries starting from today and ending one year in the future. If you wish to specify another start date, you may use

```
python manage.py hours_import kirjastot --openings --date 2021-01-01
```

If you only wish to import opening hours for a single library, you may use its kirkanta id, e.g. for Kallion kirjasto

```
python manage.py hours_import kirjastot --openings --single 84860
```

---

*Opening hours* may also be imported by trying to parse strings provided in [TPREK API](https://www.hel.fi/palvelukarttaws/restpages/ver4.html) for all known TPREK units. This feature should not be run automatically in production, as you must manually verify that the resulting opening hours are the same as the intention of the TPREK data.

Import all existing TPREK opening hours (and be prepared for errors and mistakes in the data) by

```
python manage.py hours_import tprek --openings
```

or, if your db contains merged TPREK resources,

```
python manage.py hours_import tprek --openings --merge
```

---

*Organizations* may be imported for the City of Helsinki decision makers from the [Paatos API](http://api.hel.fi/paatos/v1/), or for the TPREK data publishers (including City of Helsinki opening hour publishers) from the [TPREK API](https://www.hel.fi/palvelukarttaws/restpages/ver4.html).

Import all TPREK publisher organizations by
```
python manage.py import_organizations -c tprek http://www.hel.fi/palvelukarttaws/rest/v4/department/
```
