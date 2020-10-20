import random
import string

import factory
import pytest
from faker import Factory as FakerFactory
from pytest_factoryboy import register
from rest_framework.test import APIClient

from hours.models import DataSource, DatePeriod, OpeningHours, Resource, Rule

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
class OpeningHoursFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "OH-" + faker.pystr())

    class Meta:
        model = OpeningHours


@register
class RuleFactory(factory.django.DjangoModelFactory):
    name = factory.LazyAttribute(lambda x: "RULE-" + faker.pystr())

    class Meta:
        model = Rule
