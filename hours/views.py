import datetime
from operator import itemgetter
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django_orghierarchy.models import Organization
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import calculate_signature, join_params
from .filters import parse_maybe_relative_date_string
from .models import Resource
from .serializers import DailyOpeningHoursSerializer
from .utils import get_resource_pk_filter


class ResourceOpeningHoursView(APIView):
    def get_view_name(self):
        return _("Resource opening hours for a date period")

    def get(self, request, resource_id=None):
        try:
            resource = Resource.objects.get(**get_resource_pk_filter(resource_id))
        except Resource.DoesNotExist:
            raise APIException("Resource does not exist")

        if not request.query_params.get("start_date") or not request.query_params.get(
            "end_date"
        ):
            raise APIException("start_date and end_date GET parameters are required")

        try:
            start_date = parse_maybe_relative_date_string(
                request.query_params.get("start_date", "")
            )
        except ValueError:
            raise APIException("Invalid start_date")

        try:
            end_date = parse_maybe_relative_date_string(
                request.query_params.get("end_date", ""), end_date=True
            )
        except ValueError:
            raise APIException("Invalid end_date")

        if start_date > end_date:
            raise APIException("start_date must be before end_date")

        opening_hours = resource.get_daily_opening_hours(start_date, end_date)

        opening_hours_list = []
        for the_date, time_elements in opening_hours.items():
            opening_hours_list.append(
                {
                    "date": the_date,
                    "times": time_elements,
                }
            )
        opening_hours_list.sort(key=itemgetter("date"))

        serializer = DailyOpeningHoursSerializer(opening_hours_list, many=True)

        return Response(serializer.data)


# TODO: This is a temporary demonstration. Remove before production deployment.
class HaukiSignedAuthGeneratorForm(forms.Form):
    username = forms.CharField(label="User name", max_length=100)
    resource = forms.ModelChoiceField(queryset=Resource.objects.all(), required=False)
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(), required=False
    )


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
                "username": form.cleaned_data["username"],
                "created_at": now.isoformat() + "Z",
                "valid_until": (now + datetime.timedelta(minutes=60)).isoformat() + "Z",
            }

            if form.cleaned_data["resource"]:
                resource = form.cleaned_data["resource"]
                tprek_origin = resource.origins.filter(data_source_id="tprek").first()

                if tprek_origin:
                    params["resource"] = (
                        f"{tprek_origin.data_source.id}:" f"{tprek_origin.origin_id}"
                    )
                else:
                    params["resource"] = form.cleaned_data["resource"].id

            if form.cleaned_data["organization"]:
                params["organization"] = form.cleaned_data["organization"].id

            data_string = join_params(params)
            calculated_signature = calculate_signature(data_string)

            params["signature"] = calculated_signature
            context["link"] = client_base_url + "?" + urlencode(params)
    else:
        form = HaukiSignedAuthGeneratorForm()

    context["form"] = form

    return render(request, "hours/hauki_signed_auth_link_generator.html", context)


# TODO: This is a temporary demonstration. Remove before production deployment.
