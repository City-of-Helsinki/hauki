import logging
from datetime import datetime, timezone
from secrets import token_hex

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django_orghierarchy.models import Organization

from hours.models import DataSource, Resource, ResourceOrigin, SignedAuthKey
from users.models import UserOrigin


class Command(BaseCommand):
    help = "Create test objects in the database for running e2e tests"

    def handle(self, *args, **options):
        logger = logging.getLogger("create_e2e_test_data")

        test_data_source, created = DataSource.objects.get_or_create(
            id="test", name_fi="Cypress E2E Tester"
        )
        if created:
            logger.info(f"Created test data source with id {test_data_source.id}")
        else:
            logger.info(
                f"Test data source with id {test_data_source.id} already exists"
            )
        test_signed_auth_key, created = SignedAuthKey.objects.get_or_create(
            data_source=test_data_source,
            defaults={
                "valid_after": datetime.now(timezone.utc),
                "signing_key": token_hex(64),
            },
        )
        if created:
            logger.info(
                f"Created test signed auth key {test_signed_auth_key.signing_key}"
            )
        else:
            logger.info(
                f"Test signed auth key {test_signed_auth_key.signing_key} already exists"  # noqa
            )

        test_organization, created = Organization.objects.get_or_create(
            id="test:cypress",
            name="Cypress E2E Tester",
            data_source=test_data_source,
            origin_id="cypress",
        )
        if created:
            logger.info(f"Created test organization with id {test_organization.id}")
        else:
            logger.info(
                f"Test organization with id {test_organization.id} already exists"
            )

        test_resource, created = Resource.objects.get_or_create(
            name="E2E Test Resource",
            organization=test_organization,
            defaults={"is_public": False},
        )
        if created:
            logger.info(f"Created test resource with id {test_resource.id}")
        else:
            logger.info(f"Test resource with id {test_resource.id} already exists")
        test_resource_origin, created = ResourceOrigin.objects.get_or_create(
            data_source=test_data_source, origin_id="1", resource=test_resource
        )
        if created:
            logger.info(f"Created test resource origin {test_resource_origin}")
        else:
            logger.info(f"Test resource origin {test_resource_origin} already exists")

        test_user, created = get_user_model().objects.get_or_create(
            username="cypress_test_user"
        )
        test_organization.regular_users.add(test_user)
        if created:
            logger.info(f"Created test user with username {test_user.username}")
        else:
            logger.info(f"Test user with username {test_user.username} already exists")
        test_user_origin, created = UserOrigin.objects.get_or_create(
            user=test_user, data_source=test_data_source
        )
        if created:
            logger.info(f"Created test user origin {test_user_origin}")
        else:
            logger.info(f"Test user origin {test_user_origin} already exists")
