from django.contrib import admin
from .models import Ficha, RegistroParte, PerfilUsuario


# Removemos ParteCalcado do admin, agora é gerenciado pela interface da qualidade

class RegistroParteInline(admin.TabularInline):
    model = RegistroParte
    extra = 0
    readonly_fields = ['total']

    def total(self, obj):
        return obj.total()

    total.short_description = 'Total'


@admin.register(Ficha)
class FichaAdmin(admin.ModelAdmin):
    list_display = ['nome_ficha', 'data', 'operador', 'criada_em']
    list_filter = ['data', 'operador']
    search_fields = ['nome_ficha', 'operador__username']
    date_hierarchy = 'data'
    inlines = [RegistroParteInline]
    readonly_fields = ['criada_em', 'atualizada_em']


@admin.register(RegistroParte)
class RegistroParteAdmin(admin.ModelAdmin):
    list_display = ['ficha', 'parte', 'total', 'quantidades']
    list_filter = ['parte', 'ficha__data']
    search_fields = ['ficha__nome_ficha', 'parte__nome']

    def total(self, obj):
        return obj.total()

    total.short_description = 'Total'


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ['user', 'tipo']
    list_filter = ['tipo']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']