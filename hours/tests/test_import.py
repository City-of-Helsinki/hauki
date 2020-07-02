import pytest
import requests
import os
import json
from django.core.management import call_command
from hours.models import Target, DataSource, TargetIdentifier, TargetType
from django_orghierarchy.models import Organization

@pytest.mark.django_db
def test_import_tprek(requests_mock):
    test_file_name = 'test_import_tprek_data.json'
    test_file_path = os.path.join(os.path.dirname(__file__), test_file_name)
    with open(test_file_path) as f:
        mock_data = f.read()
        requests_mock.get('http://www.hel.fi/palvelukarttaws/rest/v4/unit/', text=mock_data)
    call_command('hours_import', 'tprek', '--all')

    # Check created objects
    assert Target.objects.count() == 1
    assert DataSource.objects.count() == 3
    assert Organization.objects.count() == 1
    assert TargetIdentifier.objects.count() == 2

    # Also check the fields are imported correctly
    kallio = Target.objects.all()[0]
    test_data = {}
    with open(test_file_path) as f:
        test_data = json.load(f)[0]
    assert kallio.data_source_id == 'tprek'
    assert kallio.origin_id == str(test_data['id'])
    assert kallio.name == test_data['name_fi']
    assert kallio.organization_id == 'tprek:%s' % test_data['dept_id']
    assert kallio.same_as == 'http://www.hel.fi/palvelukarttaws/rest/v4/unit/%s/' % test_data['id']
    assert kallio.target_type == TargetType.UNIT
    identifiers = {x.data_source_id: x for x in kallio.identifiers.all()}
    for source in test_data['sources']:
        assert source['source'] in identifiers
        assert identifiers[source['source']].origin_id == source['id']