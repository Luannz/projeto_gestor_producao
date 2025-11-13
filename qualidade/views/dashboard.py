# qualidade/views/dashboard.py
"""
Views para dashboard/telão de produção
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date, datetime

from ..models import Ficha


@login_required
def telas(request):
    """Tela para exibição em telão como um dashboard da produção"""
    # Busca a data selecionada ou usar hoje
    data_selecionada = request.GET.get('data')
    modo = request.GET.get('modo', 'lista')
    
    if data_selecionada:
        try:
            data_obj = datetime.strptime(data_selecionada, '%Y-%m-%d').date()
        except:
            data_obj = date.today()
    else:
        data_obj = date.today()
    
    # Buscar fichas do dia
    fichas = Ficha.objects.filter(
        data=data_obj,
        excluido=False
    ).select_related('operador').prefetch_related('registros__parte')
    
    # Agrupar por nome da ficha
    dados_telao = {}
    
    for ficha in fichas:
        nome_ficha = ficha.nome_ficha
        operador_nome = ficha.operador.get_full_name() or ficha.operador.username
        
        if nome_ficha not in dados_telao:
            dados_telao[nome_ficha] = {
                'nome': nome_ficha,
                'operador': operador_nome,
                'partes': {},
                'total': 0
            }
        
        # Buscar registros
        for registro in ficha.registros.all():
            parte_nome = registro.parte.nome
            total_parte = registro.total()
            
            if parte_nome not in dados_telao[nome_ficha]['partes']:
                dados_telao[nome_ficha]['partes'][parte_nome] = 0
            
            dados_telao[nome_ficha]['partes'][parte_nome] += total_parte
            dados_telao[nome_ficha]['total'] += total_parte
    
    # Calcular total geral do dia
    total_dia = sum(item['total'] for item in dados_telao.values())
    
    context = {
        'dados_telao': dados_telao,
        'data_selecionada': data_obj,
        'total_dia': total_dia,
        'data_hoje': date.today(),
        'modo': modo,
    }
    return render(request, 'qualidade/telas.html', context)