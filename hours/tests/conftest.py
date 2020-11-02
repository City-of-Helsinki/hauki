import random
import string

import factory
import pytest
from django_orghierarchy.models import Organization
from faker import Factory as FakerFactory
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hours.models import DataSource, DatePeriod, Resource, Rule, TimeSpan, TimeSpanGroup
from users.models import User

faker = FakerFactory.create(locale="fi_FI")


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

    class Meta:
        model = Resource


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
