# qualidade/views/relatorios.py
"""
Views de relatórios e geração de PDFs
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from ..models import Ficha, ParteCalcado


@login_required
def relatorios(request):
    """Página de relatórios detalhados (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar relatórios')
        return redirect('home')
    
    # Buscar filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    parte_id = request.GET.get('parte_id')
    operador_id = request.GET.get('operador_id')
    nome_ficha = request.GET.get('nome_ficha')
    
    # Buscar todas as partes e operadores para os filtros
    partes = ParteCalcado.objects.filter(ativo=True, excluido=False).order_by('nome')
    operadores = User.objects.filter(perfil__tipo='operador').order_by('username')
    nomes_fichas = (
        Ficha.objects.filter(excluido=False)
        .order_by('nome_ficha')
        .values_list('nome_ficha', flat=True)
        .distinct()
    )
    
    # Inicializar dados
    dados_relatorio = None
    total_geral = 0

    # Se houver filtros aplicados, processar
    if data_inicio and data_fim:
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        fichas = Ficha.objects.filter(
            data__gte=data_inicio_obj,
            data__lte=data_fim_obj,
            excluido=False
        )
        
        if nome_ficha:
            fichas = fichas.filter(nome_ficha=nome_ficha)

        if operador_id:
            fichas = fichas.filter(operador_id=operador_id)
        
        # Agrupar dados por operador
        dados_por_operador = {}
        
        for ficha in fichas:
            operador_nome = ficha.operador.get_full_name() or ficha.operador.username
            
            if operador_nome not in dados_por_operador:
                dados_por_operador[operador_nome] = {
                    'fichas': {},  # nome da ficha -> partes
                    'totais_partes': {}  # total geral por parte do operador
                }

            registros = ficha.registros.all().select_related('parte')
            if parte_id:
                registros = registros.filter(parte_id=parte_id)

            for registro in registros:
                parte_nome = registro.parte.nome
                valor = registro.total()

                # --- Dentro da ficha específica ---
                if ficha.nome_ficha not in dados_por_operador[operador_nome]['fichas']:
                    dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha] = {}
                if parte_nome not in dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha]:
                    dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha][parte_nome] = 0
                dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha][parte_nome] += valor

                # --- Totais por parte (somando tudo do operador) ---
                if parte_nome not in dados_por_operador[operador_nome]['totais_partes']:
                    dados_por_operador[operador_nome]['totais_partes'][parte_nome] = 0
                dados_por_operador[operador_nome]['totais_partes'][parte_nome] += valor

                # --- Total geral ---
                total_geral += valor

        dados_relatorio = dados_por_operador

    context = {
        'dados_relatorio': dados_relatorio,
        'total_geral': total_geral,
        'data_inicio': data_inicio_obj if data_inicio and data_fim else None,
        'data_fim': data_fim_obj if data_inicio and data_fim else None,
        'partes': partes,
        'operadores': operadores,
        'nomes_fichas': nomes_fichas,
    }
    
    return render(request, 'qualidade/relatorios.html', context)


@login_required
def gerar_relatorio(request, ficha_id):
    """Gerar relatório PDF de uma ficha específica"""
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Criar PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Título
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, f"Relatório - {ficha.nome_ficha}")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 70, f"Data: {ficha.data.strftime('%d/%m/%Y')}")
    p.drawString(50, height - 90, f"Operador: {ficha.operador.get_full_name() or ficha.operador.username}")
    
    # Tabela
    y = height - 130
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Parte")
    p.drawString(200, y, "Quantidades")
    p.drawString(450, y, "Total")
    
    y -= 20
    p.setFont("Helvetica", 10)
    
    for registro in ficha.registros.all():
        if y < 50:  # Nova página se necessário
            p.showPage()
            y = height - 50
        
        p.drawString(50, y, registro.parte.nome)
        quantidades_str = ', '.join(map(str, registro.quantidades))
        p.drawString(200, y, quantidades_str[:40])  # Limitar tamanho
        p.drawString(450, y, str(registro.total()))
        y -= 20
    
    # Total geral
    y -= 10
    p.setFont("Helvetica-Bold", 12)
    total_geral = sum(r.total() for r in ficha.registros.all())
    p.drawString(50, y, f"TOTAL GERAL: {total_geral}")
    
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{ficha.id}.pdf"'
    
    return response


@login_required
def gerar_relatorio_periodo(request):
    """Gerar relatório PDF de período (MESMA ESTRUTURA da view relatorios)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerar relatórios')
        return redirect('home')
    
    # Buscar parâmetros (IGUAIS à view relatorios)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    parte_id = request.GET.get('parte_id')
    operador_id = request.GET.get('operador_id')
    nome_ficha = request.GET.get('nome_ficha')
    
    if not data_inicio or not data_fim:
        messages.error(request, 'Selecione o período')
        return redirect('relatorios')
    
    # Converter strings para datas
    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()

    # Buscar fichas no período (IGUAL à view relatorios)
    fichas = Ficha.objects.filter(
        data__gte=data_inicio_obj,
        data__lte=data_fim_obj,
        excluido=False
    )
    
    if nome_ficha:
        fichas = fichas.filter(nome_ficha=nome_ficha)
    if operador_id:
        fichas = fichas.filter(operador_id=operador_id)

    # Agrupar dados por operador (IGUAL à view relatorios)
    dados_por_operador = {}
    total_geral = 0
    
    for ficha in fichas:
        operador_nome = ficha.operador.get_full_name() or ficha.operador.username
        
        if operador_nome not in dados_por_operador:
            dados_por_operador[operador_nome] = {
                'fichas': {},  # nome da ficha -> partes
                'totais_partes': {}  # total geral por parte do operador
            }

        registros = ficha.registros.all().select_related('parte')
        if parte_id:
            registros = registros.filter(parte_id=parte_id)

        for registro in registros:
            parte_nome = registro.parte.nome
            valor = registro.total()

            # Dentro da ficha específica
            if ficha.nome_ficha not in dados_por_operador[operador_nome]['fichas']:
                dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha] = {}
            if parte_nome not in dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha]:
                dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha][parte_nome] = 0
            dados_por_operador[operador_nome]['fichas'][ficha.nome_ficha][parte_nome] += valor

            # Totais por parte (somando tudo do operador)
            if parte_nome not in dados_por_operador[operador_nome]['totais_partes']:
                dados_por_operador[operador_nome]['totais_partes'][parte_nome] = 0
            dados_por_operador[operador_nome]['totais_partes'][parte_nome] += valor

            # Total geral
            total_geral += valor

    # === GERAR O PDF COM A MESMA ESTRUTURA ===
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Cabeçalho
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, "Relatório de Produção por Período")
    
    p.setFont("Helvetica", 11)
    periodo_texto = f"Período: {data_inicio_obj.strftime('%d/%m/%Y')} a {data_fim_obj.strftime('%d/%m/%Y')}"
    p.drawString(50, height - 75, periodo_texto)
    
    # Filtros aplicados
    y = height - 95
    p.setFont("Helvetica", 9)
    
    if operador_id:
        operador = User.objects.filter(id=operador_id).first()
        if operador:
            p.drawString(50, y, f"Filtro: Operador {operador.get_full_name() or operador.username}")
            y -= 12
    
    if parte_id:
        parte = ParteCalcado.objects.filter(id=parte_id).first()
        if parte:
            p.drawString(50, y, f"Filtro: Parte {parte.nome}")
            y -= 12
    
    if nome_ficha:
        p.drawString(50, y, f"Filtro: Ficha {nome_ficha}")
        y -= 12
    
    p.line(50, y, width - 50, y)
    y -= 25
    
    # === DADOS POR OPERADOR ===
    for operador_nome, dados in sorted(dados_por_operador.items()):
        # Verificar espaço
        if y < 200:
            p.showPage()
            y = height - 50
        
        # Nome do Operador
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"👤 {operador_nome}")
        y -= 25
        
        # === FICHAS DO OPERADOR ===
        for nome_ficha_key, partes_ficha in sorted(dados['fichas'].items()):
            if y < 100:
                p.showPage()
                y = height - 50
            
            # Nome da Ficha
            p.setFont("Helvetica-Bold", 11)
            p.drawString(70, y, f"📋 Nome: {nome_ficha_key}")
            y -= 18
            
            # Cabeçalho da tabela de partes
            p.setFont("Helvetica-Bold", 9)
            p.drawString(90, y, "Peças")
            p.drawRightString(width - 100, y, "Quantidade de Pares")
            y -= 2
            p.line(90, y, width - 100, y)
            y -= 12
            
            # Partes da ficha
            p.setFont("Helvetica", 9)
            for parte_nome, quantidade in sorted(partes_ficha.items()):
                if y < 50:
                    p.showPage()
                    y = height - 50
                
                p.drawString(90, y, parte_nome)
                p.drawRightString(width - 100, y, str(quantidade))
                y -= 14
            
            y -= 8  # Espaço entre fichas
        
        # === TOTAIS DO OPERADOR (por parte) ===
        if dados['totais_partes']:
            if y < 120:
                p.showPage()
                y = height - 50
            
            y -= 10
            p.line(70, y, width - 100, y)
            y -= 15
            
            p.setFont("Helvetica-Bold", 11)
            p.drawString(70, y, "Totais do Perfil:")
            y -= 18
            
            # Cabeçalho
            p.setFont("Helvetica-Bold", 9)
            p.drawString(90, y, "Parte")
            p.drawRightString(width - 100, y, "Total")
            y -= 2
            p.line(90, y, width - 100, y)
            y -= 12
            
            # Totais por parte
            p.setFont("Helvetica", 9)
            for parte_nome, total_parte in sorted(dados['totais_partes'].items()):
                if y < 50:
                    p.showPage()
                    y = height - 50
                
                p.drawString(90, y, parte_nome)
                p.drawRightString(width - 100, y, str(total_parte))
                y -= 14
        
        y -= 20  # Espaço entre operadores
    
    # === TOTAL GERAL ===
    if y < 80:
        p.showPage()
        y = height - 50
    
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 30
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "TOTAL GERAL:")
    p.drawRightString(width - 100, y, str(total_geral))
    
    y -= 10
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2, y, "peças produzidas no período")
    
    # Rodapé
    p.setFont("Helvetica", 8)
    p.drawString(50, 30, f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
    p.drawRightString(width - 50, 30, f"Usuário: {request.user.username}")
    
    p.save()
    buffer.seek(0)
    
    # Resposta HTTP
    response = HttpResponse(buffer, content_type='application/pdf')
    
    # Nome do arquivo
    nome_arquivo = f'relatorio_{data_inicio_obj.strftime("%Y%m%d")}_{data_fim_obj.strftime("%Y%m%d")}'
    if operador_id:
        nome_arquivo += f'_op{operador_id}'
    if nome_ficha:
        nome_ficha_limpo = nome_ficha.replace(' ', '_')[:15]
        nome_arquivo += f'_{nome_ficha_limpo}'
    nome_arquivo += '.pdf'
    
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response