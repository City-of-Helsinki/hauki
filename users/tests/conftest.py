from pytest_factoryboy import register

from hours.tests.conftest import DataSourceFactory, UserFactory

register(UserFactory)
register(DataSourceFactory)
