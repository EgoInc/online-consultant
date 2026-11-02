from django.urls import include, path
from drf_spectacular.renderers import OpenApiJsonRenderer
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.views import HealthView

urlpatterns = [
    path("health", HealthView.as_view()),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("openapi.json", SpectacularAPIView.as_view(renderer_classes=[OpenApiJsonRenderer]), name="schema"),
    path("api/v1/", include("api.urls")),
]
