#!/bin/bash
# This file is for any management commands Hauki needs to run hourly i.e. cronjobs
./manage.py import_organizations -c tprek http://www.hel.fi/palvelukarttaws/rest/v4/department/
./manage.py hours_import tprek --resources
./manage.py hours_import kirjastot --openings