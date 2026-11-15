from rest_framework import serializers
from .models import Usuario, ClasificacionRiesgo, Incidencia, HistorialEstado


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'rut', 'email', 'foto', 'is_staff']
        read_only_fields = ['id', 'is_staff']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta:
        model = Usuario
        fields = ['username', 'rut', 'email', 'password', 'foto']

    def create(self, validated_data):
        foto = validated_data.pop('foto', None)
        user = Usuario.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            rut=validated_data['rut'],
        )
        if foto:
            user.foto = foto
            user.save()
        return user


class ClasificacionRiesgoSerializer(serializers.ModelSerializer):
    unidad_responsable = serializers.ReadOnlyField()

    class Meta:
        model = ClasificacionRiesgo
        fields = [
            'id', 'tipo', 'nombre_evento', 'nivel_riesgo',
            'riesgo_climatico', 'duracion_horas', 'unidad_responsable'
        ]


class HistorialEstadoSerializer(serializers.ModelSerializer):
    funcionario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialEstado
        fields = ['id', 'estado', 'fecha', 'observacion', 'funcionario_nombre']

    def get_funcionario_nombre(self, obj):
        return obj.funcionario.username if obj.funcionario else 'Sistema / Ciudadano'


class IncidenciaPublicaSerializer(serializers.ModelSerializer):
    """
    Serializer público para el mapa ciudadano.
    Cumple Ley 19.628: omite identidad, RUT y correo del denunciante.
    """
    clasificacion_detalle = ClasificacionRiesgoSerializer(source='clasificacion', read_only=True)
    fecha_expiracion = serializers.DateTimeField(source='fecha_expiracion_ttl', read_only=True)

    class Meta:
        model = Incidencia
        fields = [
            'id', 'clasificacion', 'clasificacion_detalle',
            'latitud', 'longitud', 'fotografia',
            'estado_actual', 'fecha_creacion', 'fecha_expiracion'
        ]
        read_only_fields = ['estado_actual', 'fecha_creacion']


class IncidenciaMunicipalSerializer(serializers.ModelSerializer):
    """
    Serializer exclusivo para funcionarios municipales (DOM / Tránsito).
    Incluye datos de auditoría (Ley 19.628) e historial completo de estados.
    """
    clasificacion_detalle = ClasificacionRiesgoSerializer(source='clasificacion', read_only=True)
    historial = HistorialEstadoSerializer(many=True, read_only=True)
    denunciante_auditoria = serializers.SerializerMethodField()
    fecha_expiracion = serializers.DateTimeField(source='fecha_expiracion_ttl', read_only=True)

    class Meta:
        model = Incidencia
        fields = [
            'id', 'clasificacion', 'clasificacion_detalle',
            'latitud', 'longitud', 'fotografia',
            'estado_actual', 'fecha_creacion', 'fecha_expiracion',
            'denunciante_auditoria', 'historial'
        ]

    def get_denunciante_auditoria(self, obj):
        return {
            'id': obj.usuario.id,
            'username': obj.usuario.username,
            'rut': obj.usuario.rut,
            'email': obj.usuario.email,
        }