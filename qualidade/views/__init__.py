# qualidade/views/__init__.py
"""
Importa todas as views para manter compatibilidade com urls.py
"""

from .auth import *
from .fichas import *
from .partes import *
from .operadores import *
from .api import * 
from .relatorios import *
from .dashboard import *

__all__ = [
    # Auth
    'login_view',
    'logout_view',
    
    # Fichas
    'home',
    'criar_ficha',
    'editar_ficha',
    'visualizar_ficha',
    'excluir_ficha',
    'lixeira_fichas',
    
    # Partes
    'gerenciar_partes',
    'lixeira_partes',
    
    # Operadores
    'gerenciar_operadores',
    'lixeira_operadores',
    
    # API
    'adicionar_parte_ficha',
    'remover_parte_ficha',
    'adicionar_quantidade',
    'remover_quantidade',
    
    # Relatórios
    'relatorios',
    'gerar_relatorio',
    'gerar_relatorio_periodo',
    
    # Dashboard
    'telas',
]