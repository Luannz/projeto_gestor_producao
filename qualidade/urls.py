from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('telas/', views.telas, name= 'telas'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('relatorios/gerar-pdf/', views.gerar_relatorio_periodo, name='gerar_relatorio_periodo'),
    path('partes/', views.gerenciar_partes, name='gerenciar_partes'),
    path('partes/lixeira/', views.lixeira_partes, name='lixeira_partes'),
    path('operadores/', views.gerenciar_operadores, name='gerenciar_operadores'),
    path('operadores/lixeira/', views.lixeira_operadores, name='lixeira_operadores'),
    path('fichas/lixeira/', views.lixeira_fichas, name='lixeira_fichas'),
    path('ficha/criar/', views.criar_ficha, name='criar_ficha'),
    path('ficha/<int:ficha_id>/editar/', views.editar_ficha, name='editar_ficha'),
    path('ficha/<int:ficha_id>/excluir/', views.excluir_ficha, name='excluir_ficha'),
    path('ficha/<int:ficha_id>/visualizar/', views.visualizar_ficha, name='visualizar_ficha'),
    path('ficha/<int:ficha_id>/relatorio/', views.gerar_relatorio, name='gerar_relatorio'),
    path('ficha/<int:ficha_id>/adicionar-parte/', views.adicionar_parte_ficha, name='adicionar_parte_ficha'),
    path('ficha/<int:ficha_id>/remover-parte/<int:parte_id>/', views.remover_parte_ficha, name='remover_parte_ficha'),
    path('ficha/<int:ficha_id>/parte/<int:parte_id>/adicionar/', views.adicionar_quantidade, name='adicionar_quantidade'),
    path('ficha/<int:ficha_id>/parte/<int:parte_id>/remover/', views.remover_quantidade, name='remover_quantidade'),
    # URLs de Inventário (INJETORA)
    path('inventario/criar/', views.inventario.criar_ficha_inventario, name='criar_ficha_inventario'),
    path('inventario/<int:ficha_id>/editar/', views.editar_ficha_inventario, name='editar_ficha_inventario'),
    path('inventario/<int:ficha_id>/visualizar/', views.inventario.visualizar_ficha_inventario, name='visualizar_ficha_inventario'),
    path('inventario/lixeira/', views.lixeira_modelos, name='lixeira_modelos'),
    path('inventario/cores/', views.gerenciar_cores, name='gerenciar_cores'),
    path('inventario/<int:ficha_id>/excluir/',views.excluir_ficha_inventario,name='excluir_ficha_inventario'),
    path('inventario/cores/lixeira/', views.lixeira_cores, name='lixeira_cores'),
    path("inventario/item/<int:item_id>/remover/", views.remover_item_inventario, name="remover_item_inventario"),
    path("inventario/item/<int:item_id>/atualizar/", views.atualizar_quantidade_item, name="atualizar_quantidade_item"),
    path("inventario/<int:ficha_id>/relatorio/",views.gerar_relatorio_ficha_inventario,name="gerar_relatorio_ficha_inventario",),
    path("inventario/<int:ficha_id>/historico/",views.historico_inventario,name="relatorio_inventario"),
    # APIs para inventário
    path('api/get_cores/<int:id_modelo>/', views.get_cores, name='api_cores'),
    path('api/get_tamanhos/<int:id_cor>/', views.get_tamanhos, name='api_tamanhos'),
    # Gerenciamento de modelos (apenas qualidade)
    path('modelos/', views.inventario.gerenciar_modelos, name='gerenciar_modelos'),
]
