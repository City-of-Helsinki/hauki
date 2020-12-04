import random
import string
import unittest

import factory
import pytest
from django.utils import timezone
from django_orghierarchy.models import Organization
from faker import Factory as FakerFactory
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hours.models import (
    DataSource,
    DatePeriod,
    Resource,
    ResourceOrigin,
    Rule,
    SignedAuthKey,
    TimeSpan,
    TimeSpanGroup,
)
from users.models import User

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

    class Meta:
        model = Resource


@register
class ResourceOriginFactory(factory.django.DjangoModelFactory):
    origin_id = factory.LazyAttribute(lambda x: "OID-" + faker.pystr())

    class Meta:
        model = ResourceOrigin


@register
class DatePeriodFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "DP-" + faker.pystr())

    class Meta:
        model = DatePeriod


@register
class TimeSpanFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "TS-" + faker.pystr())

    class Meta:
        model = TimeSpan


@register
class TimeSpanGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TimeSpanGroup


@register
class RuleFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "RULE-" + faker.pystr())

    class Meta:
        model = Rule


@register
class OrganizationFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "ORG-" + faker.pystr())

    class Meta:
        model = Organization


@register
class UserFactory(factory.django.DjangoModelFactory):
    username = factory.LazyAttribute(lambda x: "USER-" + faker.pystr())

    class Meta:
        model = User


@register
class SignedAuthKeyFactory(factory.django.DjangoModelFactory):
    signing_key = factory.LazyAttribute(lambda x: faker.pystr(max_chars=40))
    valid_after = factory.LazyAttribute(lambda x: timezone.now())
    valid_until = None

    class Meta:
        model = SignedAuthKey
