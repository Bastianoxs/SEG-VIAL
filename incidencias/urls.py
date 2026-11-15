from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    vista_reporte_ciudadano,
    vista_dashboard_municipal,
    RegisterView,
    PerfilView,
    ClasificacionRiesgoViewSet,
    IncidenciaCiudadanaViewSet,
    IncidenciaMunicipalViewSet,
)

router = DefaultRouter()
router.register(r'clasificaciones', ClasificacionRiesgoViewSet, basename='clasificaciones')
router.register(r'incidencias', IncidenciaCiudadanaViewSet, basename='incidencias')
router.register(r'municipal/incidencias', IncidenciaMunicipalViewSet, basename='municipal-incidencias')

urlpatterns = [
    path('reportar/', vista_reporte_ciudadano, name='vista-reportar'),
    path('municipal/', vista_dashboard_municipal, name='vista-municipal'),
    path('api/auth/register/', RegisterView.as_view(), name='auth-register'),
    path('api/auth/perfil/', PerfilView.as_view(), name='auth-perfil'),
    path('api/', include(router.urls)),
]