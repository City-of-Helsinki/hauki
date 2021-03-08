from dateutil.parser import parse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .authentication import (
    InsufficientParamsError,
    SignatureValidationError,
    get_auth_params,
    validate_params_and_signature,
)
from .models import SignedAuthEntry


@extend_schema(
    operation_id="invalidate_signature",
    summary="Invalidate the current Hauki Signed Auth signature",
    description="Invalidate the current Hauki Signed Auth signature",
)
@api_view(http_method_names=["POST"])
def invalidate_hauki_auth_signature(request):
    params = get_auth_params(request)

    try:
        validate_params_and_signature(params)
    except (InsufficientParamsError, SignatureValidationError):
        raise ValidationError(detail=_("Invalid hsa_signature"))

    SignedAuthEntry.objects.create(
        signature=params["hsa_signature"],
        created_at=parse(params["hsa_created_at"]),
        valid_until=parse(params["hsa_valid_until"]),
        invalidated_at=timezone.now(),
    )

    return Response({"success": True})
