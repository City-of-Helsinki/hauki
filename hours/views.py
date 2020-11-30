import datetime
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .authentication import (
    InsufficientParamsError,
    SignatureValidationError,
    calculate_signature,
    get_auth_params,
    join_params,
    validate_params_and_signature,
)
from .models import DataSource, Resource, SignedAuthEntry, SignedAuthKey
from .utils import get_resource_pk_filter


@api_view(http_method_names=["POST"])
def invalidate_hauki_auth_signature(request):
    params = get_auth_params(request)

    try:
        validate_params_and_signature(params)
    except (InsufficientParamsError, SignatureValidationError):
        raise ValidationError(detail=_("Invalid hsa_signature"))

    SignedAuthEntry.objects.create(
        signature=params["hsa_signature"],
        created_at=params["hsa_created_at"],
        valid_until=params["hsa_valid_until"],
        invalidated_at=timezone.now(),
    )

    return Response({"success": True})


# TODO: This is a temporary demonstration. Remove before production deployment.
class HaukiSignedAuthGeneratorForm(forms.Form):
    username = forms.CharField(label="User name (*)", max_length=100)
    data_source = forms.ModelChoiceField(queryset=DataSource.objects.all())
    resource = forms.CharField(label="Resource id", required=False)
    organization = forms.CharField(label="Organization id", required=False)
    valid_minutes = forms.ChoiceField(
        label="Valid for",
        choices=(
            (10, "10 minutes"),
            (30, "30 minutes"),
            (60, "60 minutes"),
            (60 * 24, "24 hours"),
            (60 * 24 * 7, "a week"),
        ),
    )

    def clean_data_source(self):
        try:
            SignedAuthKey.objects.get(data_source=self.cleaned_data["data_source"])

            return self.cleaned_data["data_source"]
        except SignedAuthKey.DoesNotExist:
            raise forms.ValidationError(_("No signing key for selected data " "source"))

    def clean_resource(self):
        if not self.cleaned_data.get("resource"):
            return None

        try:
            return Resource.objects.get(
                **get_resource_pk_filter(self.cleaned_data.get("resource"))
            )
        except (ValueError, Resource.DoesNotExist):
            raise forms.ValidationError("Unknown resource")

    def clean_organization(self):
        if not self.cleaned_data.get("organization"):
            return None

        try:
            return Organization.objects.get(pk=self.cleaned_data.get("organization"))
        except (ValueError, Organization.DoesNotExist):
            raise forms.ValidationError("Unknown organization")


def hauki_signed_auth_link_generator(request):
    if not settings.DEBUG:
        raise Http404

    client_base_url = request.GET.get("client_base_url", "http://localhost:5000/")

    now = datetime.datetime.utcnow()

    context = {}
    if request.method == "POST":
        form = HaukiSignedAuthGeneratorForm(request.POST)
        if form.is_valid():
            params = {
                "hsa_source": form.cleaned_data["data_source"].id,
                "hsa_username": form.cleaned_data["username"],
                "hsa_created_at": now.isoformat() + "Z",
                "hsa_valid_until": (
                    now
                    + datetime.timedelta(
                        minutes=int(form.cleaned_data["valid_minutes"])
                    )
                ).isoformat()
                + "Z",
            }

            if form.cleaned_data["resource"]:
                resource = form.cleaned_data["resource"]
                tprek_origin = resource.origins.filter(data_source_id="tprek").first()

                if tprek_origin:
                    params["hsa_resource"] = (
                        f"{tprek_origin.data_source.id}:" f"{tprek_origin.origin_id}"
                    )
                else:
                    params["hsa_resource"] = form.cleaned_data["resource"].id

            if form.cleaned_data["organization"]:
                params["hsa_organization"] = form.cleaned_data["organization"].id

            try:
                signed_auth_key = SignedAuthKey.objects.get(
                    data_source=form.cleaned_data["data_source"]
                )
            except SignedAuthKey.DoesNotExist:
                raise forms.ValidationError(
                    _("No signing key for the selected data_source")
                )

            data_string = join_params(params)
            calculated_signature = calculate_signature(
                signed_auth_key.signing_key, data_string
            )

            params["hsa_signature"] = calculated_signature
            context["link"] = client_base_url + "?" + urlencode(params)
    else:
        form = HaukiSignedAuthGeneratorForm()

    context["form"] = form

    return render(request, "hours/hauki_signed_auth_link_generator.html", context)


# TODO: This is a temporary demonstration. Remove before production deployment.
