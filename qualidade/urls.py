from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('partes/', views.gerenciar_partes, name='gerenciar_partes'),
    path('partes/lixeira/', views.lixeira_partes, name='lixeira_partes'),
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
]