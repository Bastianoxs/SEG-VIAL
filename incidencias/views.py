import math
from datetime import timedelta
from django.shortcuts import render
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Usuario, ClasificacionRiesgo, Incidencia, HistorialEstado
from .serializers import (
    UsuarioSerializer,
    RegisterSerializer,
    ClasificacionRiesgoSerializer,
    IncidenciaPublicaSerializer,
    IncidenciaMunicipalSerializer,
)


def distancia_haversine_metros(lat1, lon1, lat2, lon2):
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def procesar_expiracion_temporal():
    """
    HU-02: Caduca automáticamente los eventos temporales cuyo TTL ha vencido
    y registra el evento en HistorialEstado.
    """
    ahora = timezone.now()
    temporales_activas = Incidencia.objects.select_related('clasificacion').filter(
        clasificacion__tipo='Temporal',
        estado_actual__in=['Reportado', 'Verificado', 'En Reparación'],
    )
    for inc in temporales_activas:
        limite = inc.fecha_creacion + timedelta(hours=inc.clasificacion.duracion_horas)
        if ahora >= limite:
            inc.estado_actual = 'Expirado'
            inc.save(update_fields=['estado_actual'])
            HistorialEstado.objects.create(
                incidencia=inc,
                estado='Expirado',
                fecha=ahora,
                observacion=f'Expiración automática tras {inc.clasificacion.duracion_horas}h (TTL).',
            )


# ==================== VISTAS HTML (PWA CIUDADANA Y DASHBOARD MUNICIPAL) ====================

def vista_reporte_ciudadano(request):
    clasificaciones = ClasificacionRiesgo.objects.all().order_by('tipo', 'nombre_evento')
    return render(request, 'reporte_ciudadano.html', {'clasificaciones': clasificaciones})


def vista_dashboard_municipal(request):
    clasificaciones = ClasificacionRiesgo.objects.all().order_by('tipo', 'nombre_evento')
    return render(request, 'dashboard_municipal.html', {'clasificaciones': clasificaciones})


# ==================== ENDPOINTS DE AUTENTICACIÓN Y PERFIL ====================

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'usuario': UsuarioSerializer(user, context={'request': request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PerfilView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(UsuarioSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        serializer = UsuarioSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== API CIUDADANA (PÚBLICA / ANÓNIMA) ====================

class ClasificacionRiesgoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClasificacionRiesgo.objects.all()
    serializer_class = ClasificacionRiesgoSerializer
    permission_classes = [permissions.AllowAny]


class IncidenciaCiudadanaViewSet(viewsets.ModelViewSet):
    serializer_class = IncidenciaPublicaSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ['create', 'mis_alertas']:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        procesar_expiracion_temporal()
        return Incidencia.objects.select_related('clasificacion').filter(
            estado_actual__in=['Reportado', 'Verificado', 'En Reparación']
        ).order_by('-fecha_creacion')

    def perform_create(self, serializer):
        incidencia = serializer.save(usuario=self.request.user, estado_actual='Reportado')
        HistorialEstado.objects.create(
            incidencia=incidencia,
            estado='Reportado',
            observacion='Reporte ciudadano geolocalizado enviado desde terreno.',
        )

    @action(detail=False, methods=['get'])
    def mis_alertas(self, request):
        procesar_expiracion_temporal()
        qs = Incidencia.objects.select_related('clasificacion').filter(
            usuario=request.user
        ).order_by('-fecha_creacion')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def validar_despeje(self, request, pk=None):
        incidencia = self.get_object()
        if incidencia.clasificacion.tipo != 'Temporal':
            return Response(
                {'detail': 'Solo los eventos temporales pueden despejarse por validación ciudadana.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        incidencia.estado_actual = 'Solucionado'
        incidencia.save(update_fields=['estado_actual'])
        HistorialEstado.objects.create(
            incidencia=incidencia,
            estado='Solucionado',
            observacion='Vía despejada confirmada por validación ciudadana.',
            funcionario=request.user if request.user.is_authenticated else None,
        )
        return Response({'status': 'despejado', 'id': incidencia.id})

    @action(detail=False, methods=['get'])
    def alertas_proximidad(self, request):
        """
        EVA1 / EVA2: Notificaciones proactivas en tiempo real por proximidad GPS.
        """
        procesar_expiracion_temporal()
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
        except (TypeError, ValueError):
            return Response({'alertas': []})

        radio_m = float(request.query_params.get('radio_m', 450))
        modo = request.query_params.get('modo', '')

        activas = Incidencia.objects.select_related('clasificacion').filter(
            estado_actual__in=['Reportado', 'Verificado', 'En Reparación']
        )

        cercanas = []
        for inc in activas:
            det = inc.clasificacion
            if modo and not (det.nivel_riesgo == modo or det.tipo == 'Temporal' or det.riesgo_climatico):
                continue
            dist = distancia_haversine_metros(lat, lng, inc.latitud, inc.longitud)
            if dist <= radio_m:
                data = IncidenciaPublicaSerializer(inc, context={'request': request}).data
                data['distancia_metros'] = round(dist)
                cercanas.append(data)

        cercanas.sort(key=lambda x: x['distancia_metros'])
        return Response({'total': len(cercanas), 'alertas': cercanas})


# ==================== API MUNICIPAL (DOM Y DIRECCIÓN DE TRÁNSITO) ====================

class IncidenciaMunicipalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    HU-03: Gestión exclusiva para funcionarios municipales (is_staff=True).
    """
    serializer_class = IncidenciaMunicipalSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        procesar_expiracion_temporal()
        return Incidencia.objects.select_related('clasificacion', 'usuario').prefetch_related(
            'historial', 'historial__funcionario'
        ).order_by('-fecha_creacion')

    @action(detail=True, methods=['post', 'patch'])
    def cambiar_estado(self, request, pk=None):
        incidencia = self.get_object()
        nuevo_estado = request.data.get('estado')
        observacion = request.data.get('observacion', '').strip()

        estados_validos = [c[0] for c in Incidencia.ESTADO_CHOICES]
        if nuevo_estado not in estados_validos:
            return Response(
                {'detail': f'Estado inválido. Opciones: {estados_validos}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incidencia.estado_actual = nuevo_estado
        incidencia.save(update_fields=['estado_actual'])

        HistorialEstado.objects.create(
            incidencia=incidencia,
            estado=nuevo_estado,
            observacion=observacion or f'Estado actualizado a {nuevo_estado} por funcionario municipal.',
            funcionario=request.user,
        )

        serializer = self.get_serializer(incidencia)
        return Response(serializer.data)