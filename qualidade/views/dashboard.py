# qualidade/views/dashboard.py
"""
Views para dashboard/telão de produção
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date, datetime

from ..models import Ficha, ItemInventario, LogMovimentacaoV2
from django.db.models import Sum, F, Q
from django.db.models import Sum, F, Case, When, IntegerField
from django.db.models.functions import Least, Abs


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



@login_required
def telas_inventario(request):
    data_str = request.GET.get('data')
    modo = request.GET.get('modo', 'grafico')
    
    if data_str:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    else:
        data_obj = date.today()

    # --- 1. TOP ESTOQUE (O que mais tem hoje) ---
    # Agrupamos por modelo e somamos PD + PE
    estoque_por_modelo = ItemInventario.objects.values('modelo__nome').annotate(
        pares_formados=Sum(Least(F('quantidade_pe_direito'), F('quantidade_pe_esquerdo'))),
        total_avulsos=Sum(Abs(F('quantidade_pe_direito') - F('quantidade_pe_esquerdo')))
    ).order_by('-pares_formados')[:10]


    # 2 ranking avulsos
    ranking_avulsos = ItemInventario.objects.values('modelo__nome').annotate(
        sobra=Sum(Abs(F('quantidade_pe_direito') - F('quantidade_pe_esquerdo')))
    ).filter(sobra__gt=0).order_by('-sobra')[:5]

    # --- 3. SAÍDAS  ---
    saidas_do_dia = LogMovimentacaoV2.objects.filter(
        criado_em__date=data_obj,
        acao='subtrair'
    ).values('identificacao_item').annotate(
        total=Sum('quantidade_movimentada')
    ).order_by('-total')[:10]

    # --- 3. CÁLCULO DE AVULSOS (Diferença entre PD e PE) ---
    # Itens onde a quantidade de um pé é diferente do outro
    itens_avulsos = ItemInventario.objects.filter(
        ~Q(quantidade_pe_direito=F('quantidade_pe_esquerdo'))
    )
    
    # Podemos somar a diferença absoluta para saber quantos "pés" estão sem par
    total_avulsos = 0
    for item in itens_avulsos:
        total_avulsos += abs(item.quantidade_pe_direito - item.quantidade_pe_esquerdo)

    context = {
        'top_estoque': list(estoque_por_modelo),
        'top_saidas': list(saidas_do_dia),
        'total_avulsos': total_avulsos,
        'data_selecionada': data_obj,
        'data_hoje': date.today(),
        'modo': modo,
        'ranking_avulsos': list(ranking_avulsos),
    }
    return render(request, 'qualidade/telas_inventario.html', context)