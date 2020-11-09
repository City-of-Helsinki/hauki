import hashlib
import hmac
import urllib.parse

from dateutil.parser import parse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    TokenAuthentication,
    get_authorization_header,
)

User = get_user_model()

REQUIRED_AUTH_PARAM_NAMES = ["username", "created_at", "valid_until", "signature"]
OPTIONAL_AUTH_PARAM_NAMES = ["organization", "resource"]


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
        if i != "signature"
    ]

    return "".join([params.get(field_name, "") for field_name in fields_in_order])


def calculate_signature(source_string):
    return hmac.new(
        key=settings.HAUKI_SIGNED_AUTH_PSK.encode("utf-8"),
        msg=source_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def compare_signatures(first, second):
    return hmac.compare_digest(first.lower(), second.lower())


class HaukiSignedAuthentication(BaseAuthentication):
    def authenticate(self, request):
        if not settings.HAUKI_SIGNED_AUTH_PSK:
            return None

        params = get_auth_params(request)

        if not len(params):
            return None

        if not all([params.get(k) for k in REQUIRED_AUTH_PARAM_NAMES]):
            return None

        data_string = join_params(params)
        calculated_signature = calculate_signature(data_string)

        if not compare_signatures(params["signature"], calculated_signature):
            raise exceptions.AuthenticationFailed(_("Invalid signature"))

        try:
            created_at = parse(params["created_at"])
            try:
                if created_at > timezone.now():
                    raise exceptions.AuthenticationFailed(_("Invalid created_at"))
            except TypeError:
                raise exceptions.AuthenticationFailed(_("Invalid created_at"))
        except ValueError:
            raise exceptions.AuthenticationFailed(_("Invalid created_at"))

        try:
            valid_until = parse(params["valid_until"])
            try:
                if valid_until < timezone.now():
                    raise exceptions.AuthenticationFailed(_("Invalid valid_until"))
            except TypeError:
                raise exceptions.AuthenticationFailed(_("Invalid valid_until"))
        except ValueError:
            raise exceptions.AuthenticationFailed(_("Invalid valid_until"))

        # TODO: Add separate PSKs for different integrations and only allow access
        #       to users initially from the same integration. Also Only allow
        #       using organisations from the same integration.
        try:
            user = User.objects.get(username=params["username"])
        except User.DoesNotExist:
            user = User()
            user.set_unusable_password()
            user.username = params["username"]
            user.save()

        if not user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))

        if params.get("organization"):
            try:
                organization = Organization.objects.get(id=params["organization"])
                users_organizations = user.organization_memberships.all()

                if organization not in users_organizations:
                    user.organization_memberships.add(organization)
            except Organization.DoesNotExist:
                # TODO: Should we raise exception here
                pass

        return user, None


class HaukiTokenAuthentication(TokenAuthentication):
    keyword = "APIToken"
