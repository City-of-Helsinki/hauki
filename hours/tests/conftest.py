import datetime
import random
import string
import unittest
import uuid

import factory
import pytest
from django.utils import timezone
from django_orghierarchy.models import Organization
from faker import Factory as FakerFactory
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hours.authentication import calculate_signature, join_params
from hours.models import (
    DataSource,
    DatePeriod,
    PeriodOrigin,
    Resource,
    ResourceOrigin,
    Rule,
    SignedAuthKey,
    TimeSpan,
    TimeSpanGroup,
)
from users.models import User, UserOrigin

faker = FakerFactory.create(locale="fi_FI")


@pytest.fixture
def assert_count_equal():
    def do_test(a, b):
        tc = unittest.TestCase()
        tc.assertCountEqual(a, b)

    return do_test


@pytest.fixture
def api_client():
    return APIClient()


@register
class DataSourceFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(
        lambda x: "".join(random.choices(string.ascii_letters, k=10))
    )
    id = factory.LazyAttribute(lambda o: o.name.lower())

    class Meta:
        model = DataSource


@register
class ResourceFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: faker.company())
    address = factory.LazyAttribute(lambda x: faker.address())
    is_public = True
    timezone = "Europe/Helsinki"

    class Meta:
        model = Resource


@register
class ResourceOriginFactory(factory.django.DjangoModelFactory):
    origin_id = factory.LazyAttribute(lambda x: "OID-" + faker.pystr())

    class Meta:
        model = ResourceOrigin


@register
class DatePeriodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DatePeriod

    name = factory.LazyAttribute(lambda x: "DP-" + faker.pystr())
    start_date = factory.LazyAttribute(lambda x: faker.date())

    @factory.post_generation
    def origins(self, create, extracted, **__):
        if not create or not extracted:
            return

        for origin in extracted:
            self.origins.add(origin)

    @factory.post_generation
    def data_sources(self, create, extracted, **__):
        if not create or not extracted:
            return

        for data_source in extracted:
            # Create a new origin for each data source, since data sources
            # are accessed through origins.
            self.origins.add(PeriodOriginFactory(data_source=data_source, period=self))


@register
class PeriodOriginFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PeriodOrigin

    origin_id = factory.LazyAttribute(lambda x: "OID-" + faker.pystr())
    data_source = factory.SubFactory(DataSourceFactory)


@register
class TimeSpanGroupFactory(factory.django.DjangoModelFactory):
    period = factory.SubFactory(DatePeriodFactory)

    class Meta:
        model = TimeSpanGroup


@register
class TimeSpanFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "TS-" + faker.pystr())
    group = factory.SubFactory(TimeSpanGroupFactory)

    class Meta:
        model = TimeSpan


@register
class RuleFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "RULE-" + faker.pystr())
    group = factory.SubFactory(TimeSpanGroupFactory)

    class Meta:
        model = Rule


@register
class OrganizationFactory(factory.django.DjangoModelFactory):
    id = factory.LazyAttribute(lambda x: str(uuid.uuid4()))
    name = factory.LazyAttribute(lambda x: "ORG-" + faker.pystr())

    class Meta:
        model = Organization


@register
class UserFactory(factory.django.DjangoModelFactory):
    username = factory.LazyAttribute(lambda x: "USER-" + faker.pystr())

    class Meta:
        model = User


@register
class UserOriginFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserOrigin


@register
class SignedAuthKeyFactory(factory.django.DjangoModelFactory):
    signing_key = factory.LazyAttribute(lambda x: faker.pystr(max_chars=40))
    valid_after = factory.LazyAttribute(lambda x: timezone.now())
    valid_until = None

    class Meta:
        model = SignedAuthKey


@pytest.fixture
def hsa_params_factory():
    def _make_hsa_params(
        user=None,
        username=None,
        data_source=None,
        organization=None,
        resource=None,
        has_organization_rights=False,
        signed_auth_key=None,
    ):
        if not signed_auth_key:
            signed_auth_key = SignedAuthKeyFactory(data_source=data_source)

        now = datetime.datetime.utcnow()

        data = {
            "hsa_source": data_source.id,
            "hsa_username": user.username if user else username,
            "hsa_created_at": now.isoformat() + "Z",
            "hsa_valid_until": (now + datetime.timedelta(minutes=10)).isoformat() + "Z",
            "hsa_has_organization_rights": str(has_organization_rights),
        }

        if organization:
            data["hsa_organization"] = str(organization.id)

        if resource:
            data["hsa_resource"] = (
                str(resource.id) if isinstance(resource, Resource) else resource
            )

        source_string = join_params(data)
        signature = calculate_signature(signed_auth_key.signing_key, source_string)

        return {**data, "hsa_signature": signature}

    return _make_hsa_params
