from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Usuario(AbstractUser):
    rut = models.CharField(max_length=15, unique=True)
    foto = models.ImageField(upload_to='perfiles/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.rut})"


class ClasificacionRiesgo(models.Model):
    TIPO_CHOICES = [
        ('Persistente', 'Persistente'),
        ('Temporal', 'Temporal'),
    ]
    RIESGO_CHOICES = [
        ('Motorizado', 'Motorizado'),
        ('Ciclista', 'Ciclista'),
        ('Peatonal', 'Peatonal'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='Persistente')
    nombre_evento = models.CharField(max_length=100)
    nivel_riesgo = models.CharField(max_length=20, choices=RIESGO_CHOICES, default='Motorizado')
    riesgo_climatico = models.BooleanField(default=False)
    duracion_horas = models.PositiveIntegerField(
        default=6,
        help_text="Horas de vigencia automática (TTL) cuando el evento es Temporal."
    )

    @property
    def unidad_responsable(self):
        """
        Derivación automática según EVA1:
        - Problemas de flujo, señalética o eventos temporales -> Dirección de Tránsito
        - Daños físicos de calzada/infraestructura -> Dirección de Obras Municipales (DOM)
        """
        texto = self.nombre_evento.lower()
        palabras_transito = ('semáforo', 'semaforo', 'señal', 'senal', 'tránsito', 'transito', 'corte', 'desvío', 'desvio', 'flujo', 'inund')
        if self.tipo == 'Temporal' or any(p in texto for p in palabras_transito):
            return 'Dirección de Tránsito'
        return 'Dirección de Obras Municipales (DOM)'

    def __str__(self):
        return f"{self.tipo} - {self.nombre_evento} ({self.nivel_riesgo})"


class Incidencia(models.Model):
    ESTADO_CHOICES = [
        ('Reportado', 'Reportado'),
        ('Verificado', 'Verificado'),
        ('En Reparación', 'En Reparación'),
        ('Solucionado', 'Solucionado'),
        ('Expirado', 'Expirado'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='incidencias')
    clasificacion = models.ForeignKey(ClasificacionRiesgo, on_delete=models.PROTECT, related_name='incidencias')
    latitud = models.FloatField()
    longitud = models.FloatField()
    fotografia = models.ImageField(upload_to='incidencias/')
    estado_actual = models.CharField(max_length=25, choices=ESTADO_CHOICES, default='Reportado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def fecha_expiracion_ttl(self):
        if self.clasificacion.tipo != 'Temporal':
            return None
        return self.fecha_creacion + timedelta(hours=self.clasificacion.duracion_horas)

    def __str__(self):
        return f"#{self.id} {self.clasificacion.nombre_evento} [{self.estado_actual}]"


class HistorialEstado(models.Model):
    incidencia = models.ForeignKey(Incidencia, on_delete=models.CASCADE, related_name='historial')
    estado = models.CharField(max_length=25)
    fecha = models.DateTimeField(default=timezone.now)
    observacion = models.CharField(max_length=255, blank=True, default='')
    funcionario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='gestion_estados'
    )

    class Meta:
        ordering = ['fecha']

    def __str__(self):
        return f"Incidencia #{self.incidencia_id} -> {self.estado} ({self.fecha:%d-%m-%Y %H:%M})"