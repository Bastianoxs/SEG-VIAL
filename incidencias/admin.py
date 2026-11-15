from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, ClasificacionRiesgo, Incidencia, HistorialEstado


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'rut', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'rut', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Ciudadanos', {'fields': ('rut', 'foto')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos Ciudadanos', {'fields': ('rut', 'email', 'foto')}),
    )


@admin.register(ClasificacionRiesgo)
class ClasificacionRiesgoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_evento', 'tipo', 'nivel_riesgo',
        'riesgo_climatico', 'duracion_horas', 'unidad_responsable'
    )
    list_filter = ('tipo', 'nivel_riesgo', 'riesgo_climatico')
    search_fields = ('nombre_evento',)


class HistorialEstadoInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    readonly_fields = ('fecha',)


@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'clasificacion', 'usuario',
        'latitud', 'longitud', 'estado_actual', 'fecha_creacion'
    )
    list_filter = (
        'estado_actual', 'clasificacion__tipo',
        'clasificacion__nivel_riesgo', 'fecha_creacion'
    )
    search_fields = ('clasificacion__nombre_evento', 'usuario__username', 'usuario__rut')
    readonly_fields = ('fecha_creacion',)
    inlines = [HistorialEstadoInline]


@admin.register(HistorialEstado)
class HistorialEstadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'incidencia', 'estado', 'funcionario', 'fecha', 'observacion')
    list_filter = ('estado', 'fecha')
    search_fields = ('incidencia__id', 'observacion', 'funcionario__username')