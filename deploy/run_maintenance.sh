#!/bin/bash
# This file is for any management commands Hauki needs to run hourly i.e. cronjobs

set -e

# TPREK organization structure must be up to date so users have the correct organization rights
./manage.py import_organizations -c tprek http://www.hel.fi/palvelukarttaws/rest/v4/department/
# TPREK units and connections must be up to date so changed TPREK data is present in Hauki
# NOTE! --parse-nothing should be used here when Hauki is in production. It will prevent new
# opening hours being created when resources contain opening hours strings.
./manage.py hours_import tprek --resources --parse-nothing
# Library opening hours must be up to date, because they will not be edited in Hauki
./manage.py hours_import kirjastot --openings
