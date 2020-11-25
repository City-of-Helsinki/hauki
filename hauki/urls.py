"""hauki URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

from hours.api import APIRouter
from hours.views import (
    hauki_signed_auth_link_generator,
    invalidate_hauki_auth_signature,
)

admin.autodiscover()

router = APIRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", include(router.urls)),
    path(
        "invalidate_signature/",
        invalidate_hauki_auth_signature,
        name="invalidate_hauki_auth_signature",
    ),
    path("", include("rest_framework.urls", namespace="rest_framework")),
    path("hauki_signed_auth_link_generator/", hauki_signed_auth_link_generator),
    path("", RedirectView.as_view(url="v1/")),
]
