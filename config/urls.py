"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView
from rest_framework.routers import SimpleRouter

from monitoring.app import app
from monitoring.signup import AppLoginView, signup
from monitoring.views import (
    CounterEpochViewSet,
    DeviceViewSet,
    ParticipantViewSet,
    SensorCapabilityViewSet,
    SensorViewSet,
    SessionDeviceViewSet,
    SessionViewSet,
    TelemetryBatchView,
    healthz,
    readyz,
)
from monitoring.vital_signs import VitalSignsView

router = SimpleRouter()
router.register("sessions", SessionViewSet, basename="session")
router.register("config/participants", ParticipantViewSet)
router.register("config/devices", DeviceViewSet)
router.register("config/sensors", SensorViewSet)
router.register("config/capabilities", SensorCapabilityViewSet)
router.register("config/assignments", SessionDeviceViewSet)
router.register("config/counter-epochs", CounterEpochViewSet)

urlpatterns = [
    path('', RedirectView.as_view(url='/app/', permanent=False)),
    path('app/', app, name='app'),
    path('accounts/login/', AppLoginView.as_view(), name='login'),
    path('accounts/signup/', signup, name='signup'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/telemetry/batches/', TelemetryBatchView.as_view(), name='telemetry-batches'),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/v1/telemetry/vital-signs/', VitalSignsView.as_view(), name='vital-signs'),
    path('healthz/', healthz),
    path('readyz/', readyz),
]
