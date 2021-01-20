import hashlib
import hmac
import urllib.parse

from dateutil.parser import parse
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    TokenAuthentication,
    get_authorization_header,
)

from hours.models import DataSource, Resource, SignedAuthEntry, SignedAuthKey
from users.models import UserOrigin

User = get_user_model()

REQUIRED_AUTH_PARAM_NAMES = [
    "hsa_source",
    "hsa_username",
    "hsa_created_at",
    "hsa_valid_until",
    "hsa_signature",
]
OPTIONAL_AUTH_PARAM_NAMES = [
    "hsa_organization",
    "hsa_resource",
    "hsa_has_organization_rights",
]


def get_auth_params_from_authz_header(request) -> dict:
    auth = get_authorization_header(request).split()

    if not auth or auth[0].lower() != b"haukisigned":
        return {}

    if len(auth) == 1:
        msg = _("Invalid Authorization header. No credentials provided.")
        raise exceptions.AuthenticationFailed(msg)
    elif len(auth) > 2:
        msg = _(
            "Invalid Authorization header. Credentials string should not "
            "contain spaces."
        )
        raise exceptions.AuthenticationFailed(msg)

    all_param_names = REQUIRED_AUTH_PARAM_NAMES + OPTIONAL_AUTH_PARAM_NAMES

    try:
        header_params = dict(urllib.parse.parse_qsl(auth[1].decode("utf-8")))
    except UnicodeError:
        raise exceptions.AuthenticationFailed(_("Invalid unicode"))

    return {k: v for k, v in header_params.items() if k in all_param_names}


def get_auth_params_from_query_params(request) -> dict:
    all_param_names = REQUIRED_AUTH_PARAM_NAMES + OPTIONAL_AUTH_PARAM_NAMES

    return {k: v for k, v in request.query_params.items() if k in all_param_names}


def get_auth_params(request):
    header_params = get_auth_params_from_authz_header(request)
    query_params = get_auth_params_from_query_params(request)

    # We support parameters both from Authorization header and GET-parameters
    # TODO: Maybe don't allow mix and matching
    return {**header_params, **query_params}


def join_params(params):
    fields_in_order = [
        i
        for i in (REQUIRED_AUTH_PARAM_NAMES + OPTIONAL_AUTH_PARAM_NAMES)
        if i != "hsa_signature"
    ]

    return "".join([params.get(field_name, "") for field_name in fields_in_order])


def calculate_signature(signing_key, source_string):
    return hmac.new(
        key=signing_key.encode("utf-8"),
        msg=source_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def compare_signatures(first, second):
    return hmac.compare_digest(first.lower(), second.lower())


class InsufficientParamsError(Exception):
    pass


class SignatureValidationError(Exception):
    pass


def validate_params_and_signature(params) -> bool:
    if not len(params):
        raise InsufficientParamsError()

    if not all([params.get(k) for k in REQUIRED_AUTH_PARAM_NAMES]):
        raise InsufficientParamsError()

    now = timezone.now()

    try:
        signed_auth_key = SignedAuthKey.objects.get(
            Q(data_source__id=params["hsa_source"])
            & Q(valid_after__lt=now)
            & (Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        )
    except SignedAuthKey.DoesNotExist:
        raise SignatureValidationError(_("Invalid source"))

    calculated_signature = calculate_signature(
        signed_auth_key.signing_key, join_params(params)
    )

    if not compare_signatures(params["hsa_signature"], calculated_signature):
        raise SignatureValidationError(_("Invalid hsa_signature"))

    try:
        created_at = parse(params["hsa_created_at"])
        try:
            if created_at > timezone.now():
                raise SignatureValidationError(_("Invalid hsa_created_at"))
        except TypeError:
            raise SignatureValidationError(_("Invalid hsa_created_at"))
    except ValueError:
        raise SignatureValidationError(_("Invalid hsa_created_at"))

    try:
        valid_until = parse(params["hsa_valid_until"])
        try:
            if valid_until < timezone.now():
                raise SignatureValidationError(_("Invalid hsa_valid_until"))
        except TypeError:
            raise SignatureValidationError(_("Invalid hsa_valid_until"))
    except ValueError:
        raise SignatureValidationError(_("Invalid hsa_valid_until"))

    return True


class HaukiSignedAuthData:
    def __init__(self):
        self.user = None
        self.user_origin = None
        self.original_params = None
        self.organization = None
        self.resource = None
        self.has_organization_rights = False


class HaukiSignedAuthentication(BaseAuthentication):
    def authenticate(self, request):
        params = get_auth_params(request)

        try:
            validate_params_and_signature(params)
        except InsufficientParamsError:
            # Missing params, let other authentication backends try
            return None
        except SignatureValidationError as e:
            raise exceptions.AuthenticationFailed(str(e))

        if SignedAuthEntry.objects.filter(
            signature=params["hsa_signature"], invalidated_at__isnull=False
        ).exists():
            raise exceptions.AuthenticationFailed(_("Signature has been invalidated"))

        data_source = DataSource.objects.get(id=params["hsa_source"])

        try:
            user = User.objects.get(username=params["hsa_username"])

            try:
                user_origin = user.origins.get(data_source=data_source)
            except UserOrigin.DoesNotExist:
                raise exceptions.AuthenticationFailed(
                    _("User not from the same data source")
                )
        except User.DoesNotExist:
            user = User()
            user.set_unusable_password()
            user.username = params["hsa_username"]
            user.save()

            user_origin = UserOrigin.objects.create(user=user, data_source=data_source)

        if not user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))

        hsa_auth_data = HaukiSignedAuthData()
        hsa_auth_data.user = user
        hsa_auth_data.user_origin = user_origin
        hsa_auth_data.original_params = params

        if params.get("hsa_organization"):
            try:
                organization = Organization.objects.get(id=params["hsa_organization"])

                # Allow joining users only to organizations that are from
                # the same data source
                if data_source == organization.data_source:
                    users_organizations = user.organization_memberships.all()

                    if organization not in users_organizations:
                        user.organization_memberships.add(organization)

                    hsa_auth_data.organization = organization
            except Organization.DoesNotExist:
                # TODO: Should we raise exception here
                pass

        hsa_auth_data.has_organization_rights = False
        if params.get("hsa_has_organization_rights", "").lower() == "true":
            hsa_auth_data.has_organization_rights = True

        hsa_auth_data.resource = None
        if params.get("hsa_resource"):
            try:
                resource = Resource.objects.get(id=params["hsa_resource"])
                resource_data_source_ids = [ds.id for ds in resource.data_sources.all()]
                resource_data_source_ids.extend(resource.ancestry_data_source)

                if data_source.id in resource_data_source_ids:
                    hsa_auth_data.resource = resource
            except Resource.DoesNotExist:
                # TODO: Should we raise exception here
                pass

        return user, hsa_auth_data


class HaukiTokenAuthentication(TokenAuthentication):
    keyword = "APIToken"


class HaukiSignedAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "hours.authentication.HaukiSignedAuthentication"
    name = "HaukiSignedAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            "description": "A simple query parameter based authentication method for "
            "trusted third parties.",
            "type": "apiKey",
            "in": "query",
            "name": "signature",
        }
