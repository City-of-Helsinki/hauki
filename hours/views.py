from dateutil.parser import isoparse
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Resource
from .serializers import DailyOpeningHoursSerializer
from .viewsets import get_resource_pk_filter


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
            start_date = isoparse(request.query_params.get("start_date", "")).date()
        except ValueError:
            raise APIException("Invalid start_date")

        try:
            end_date = isoparse(request.query_params.get("end_date", "")).date()
        except ValueError:
            raise APIException("Invalid end_date")

        if start_date > end_date:
            raise APIException("start_date must be before end_date")

        opening_hours = resource.get_daily_opening_hours(start_date, end_date)
        serializer = DailyOpeningHoursSerializer(opening_hours)

        return Response(serializer.data)
