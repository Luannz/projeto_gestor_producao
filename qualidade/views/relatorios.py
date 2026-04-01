# qualidade/views/relatorios.py
"""
Views de relatórios e geração de PDFs
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.db.models import Sum
from datetime import datetime, timedelta
from django.utils import timezone 
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from django.core.paginator import Paginator

from ..models import Ficha, ParteCalcado, FichaInventario, LogMovimentacaoV2, RegistroParte


@login_required
def relatorio_producao(request):
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Acesso negado.')
        return redirect('home')

    # 1. Captura de Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    perfil_id = request.GET.get('perfil_id')    # ID do User (quem lançou)
    nome_ficha = request.GET.get('nome_ficha')  # Nome do operador da banca
    parte_id = request.GET.get('parte_id')      # ID da Parte (Sola, etc)

    # Dados para carregar os selects do filtro
    todos_usuarios = User.objects.filter(perfil__tipo='operador').order_by('first_name')
    todas_partes = ParteCalcado.objects.filter(ativo=True, excluido=False).order_by('nome')
    # Nomes únicos de fichas cadastrados no sistema para o filtro
    nomes_fichas_unicos = Ficha.objects.filter(excluido=False).values_list('nome_ficha', flat=True).distinct().order_by('nome_ficha')

    resultados = []
    totais_por_parte = {}
    total_geral = 0

    # 2. Lógica de Busca (Só executa se houver datas)
    if data_inicio and data_fim:
        # Filtro base: Fichas no período e não excluídas
        fichas = Ficha.objects.filter(
            data__range=[data_inicio, data_fim],
            excluido=False
        )

        # Aplicar filtros opcionais
        if perfil_id:
            fichas = fichas.filter(operador_id=perfil_id)
        if nome_ficha:
            fichas = fichas.filter(nome_ficha=nome_ficha)

        # Buscar os registros de partes dessas fichas
        # Usamos prefetch_related para não travar o banco com muitas queries
        registros = RegistroParte.objects.filter(ficha__in=fichas).select_related('ficha', 'parte', 'ficha__operador')

        if parte_id:
            registros = registros.filter(parte_id=parte_id)

        # 3. Organização dos dados para o Template
        # Queremos mostrar: Data | Nome Ficha | Parte | Quantidade (Soma do JSON)
        for reg in registros:
            qtd_total_registro = reg.total() # Usa o método que já tem no model
            nome_parte = reg.parte.nome
            
            resultados.append({
                'data': reg.ficha.data,
                'perfil': reg.ficha.operador.get_full_name() or reg.ficha.operador.username,
                'nome_ficha': reg.ficha.nome_ficha,
                'parte': reg.parte.nome,
                'quantidade': qtd_total_registro
            })

            if nome_parte in totais_por_parte:
                totais_por_parte[nome_parte] += qtd_total_registro
            else:
                totais_por_parte[nome_parte] = qtd_total_registro

            total_geral += qtd_total_registro

        # Ordenar resultados por data
        resultados.sort(key=lambda x: (x['parte'], x['data']))

    
    # ---- LOGICA DE PAGINAÇÃO ------
    paginator = Paginator(resultados, 50) # 50 registros por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)


    context = {
        'page_obj': page_obj,
        'totais_por_parte': totais_por_parte,
        'total_geral': total_geral,
        'usuarios': todos_usuarios,
        'partes': todas_partes,
        'nomes_fichas': nomes_fichas_unicos,
        # Mantém os filtros nos campos após o post
        'filtros': request.GET 
    }
    
    return render(request, 'qualidade/relatorio_producao.html', context)




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
def gerar_relatorio_ficha_inventario(request, ficha_id):
    ficha = get_object_or_404(FichaInventario, id=ficha_id)
    itens = ficha.itens.select_related("modelo", "tamanho", "cor")

    total_pares_geral = 0
    total_avulsos_geral = 0

    for item in itens:
        pares = min(item.quantidade_pe_direito, item.quantidade_pe_esquerdo)
        total_pares_geral += pares
        total_avulsos_geral += abs(item.quantidade_pe_direito - item.quantidade_pe_esquerdo)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- Cabeçalho ---
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, height - 50, "Relatório de Inventário de Calçados")

    p.setFont("Helvetica", 10)
    p.drawString(40, height - 75, f"Ficha: {ficha.id} | Nome: {ficha.nome_ficha}")
    p.drawString(40, height - 90, f"Data: {ficha.data.strftime('%d/%m/%Y')} | Operador: {ficha.operador.username}")

    # --- Bloco de Totais ---
    p.rect(40, height - 145, 520, 40) 
    p.setFont("Helvetica-Bold", 12)
    p.setFillColorRGB(0, 0.4, 0)
    p.drawString(100, height - 130, f"TOTAL DE PARES: {total_pares_geral}")
    p.setFillColorRGB(0.8, 0, 0)
    p.drawString(330, height - 130, f"TOTAL DE AVULSOS: {total_avulsos_geral}")
    p.setFillColorRGB(0, 0, 0)

    # --- Cabeçalho da Tabela (Ajuste fino para a esquerda) ---
    y = height - 170
    p.setFont("Helvetica-Bold", 9)
    
    # Coordenadas X ajustadas para não "estourar" a margem 560
    col_mod = 40
    col_cor = 160
    col_tam = 360  # Recuei 10pt
    col_esq = 395  # Recuei 10pt
    col_dir = 440  # Recuei 10pt
    col_par = 485  # Recuei 10pt
    col_avu = 520  # Recuei 10pt para o texto "X Esq." caber antes do 560

    p.drawString(col_mod, y, "Modelo")
    p.drawString(col_cor, y, "Cor")
    p.drawString(col_tam, y, "Tam.")
    p.drawString(col_esq, y, "Pé Esq.")
    p.drawString(col_dir, y, "Pé Dir.")
    p.drawString(col_par, y, "Pares")
    p.drawString(col_avu, y, "Avulsos")
    
    p.line(40, y-5, 560, y-5) 
    y -= 20

    # --- Listagem de Itens ---
    p.setFont("Helvetica", 8.5)
    for item in itens:
        if y < 50:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 8.5)

        pares = min(item.quantidade_pe_direito, item.quantidade_pe_esquerdo)
        sobra_esq = item.quantidade_pe_esquerdo - pares
        sobra_dir = item.quantidade_pe_direito - pares

        p.drawString(col_mod, y, item.modelo.nome[:28]) 
        p.drawString(col_cor, y, item.cor.nome)         
        
        # Alinhamento centralizado sob os títulos
        p.drawString(col_tam + 2, y, str(item.tamanho.numero))
        p.drawString(col_esq + 8, y, str(item.quantidade_pe_esquerdo))
        p.drawString(col_dir + 8, y, str(item.quantidade_pe_direito))
        
        p.setFont("Helvetica-Bold", 8.5)
        p.drawString(col_par + 5, y, str(pares))
        p.setFont("Helvetica", 8.5)

        if sobra_esq > 0:
            p.setFillColorRGB(0.8, 0, 0)
            p.drawString(col_avu, y, f"{sobra_esq} Esq.")
            p.setFillColorRGB(0, 0, 0)
        elif sobra_dir > 0:
            p.setFillColorRGB(0.8, 0, 0)
            p.drawString(col_avu, y, f"{sobra_dir} Dir.")
            p.setFillColorRGB(0, 0, 0)
        else:
            p.drawString(col_avu, y, "-")

        y -= 16

    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ficha_{ficha.id}.pdf"'
    return response



@login_required
def gerar_pdf_producao(request):
    if request.user.perfil.tipo != 'qualidade':
        return HttpResponse('Acesso negado', status=403)

    # 1. Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    perfil_id = request.GET.get('perfil_id')
    nome_ficha = request.GET.get('nome_ficha')
    parte_id = request.GET.get('parte_id')

    if not data_inicio or not data_fim:
        return HttpResponse('Selecione um período.')

    # 2. Busca e Processamento (Lógica idêntica à view do sistema)
    fichas = Ficha.objects.filter(data__range=[data_inicio, data_fim], excluido=False)
    if perfil_id:
        fichas = fichas.filter(operador_id=perfil_id)
    if nome_ficha:
        fichas = fichas.filter(nome_ficha=nome_ficha)

    registros = RegistroParte.objects.filter(ficha__in=fichas).select_related('ficha', 'parte', 'ficha__operador')
    if parte_id:
        registros = registros.filter(parte_id=parte_id)

    # 3. Cálculo de Totais (A lógica que adicionamos agora)
    totais_por_parte = {}
    total_geral = 0
    dados_para_tabela = []

    for reg in registros:
        qtd = reg.total()
        nome_parte = reg.parte.nome
        
        # Acumula para o resumo
        totais_por_parte[nome_parte] = totais_por_parte.get(nome_parte, 0) + qtd
        total_geral += qtd
        
        # Guarda para a tabela
        dados_para_tabela.append(reg)

    # Ordenar dados da tabela por data
    dados_para_tabela.sort(key=lambda x: x.ficha.data)

    # 4. Configuração do ReportLab
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="producao_{data_inicio}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    largura, altura = A4
    y = altura - 2 * cm

    # Título e Período
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor(colors.HexColor("#111827"))
    p.drawString(2 * cm, y, "Relatório de Produção Detalhado")
    p.setFont("Helvetica", 10)
    p.setFillColor(colors.HexColor("#6b7280"))
    p.drawString(2 * cm, y - 0.6 * cm, f"Período: {data_inicio} até {data_fim}")
    
    y -= 1.8 * cm

    # --- SEÇÃO DE RESUMO (OS CARDS NO PDF) ---
    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.HexColor("#374151"))
    p.drawString(2 * cm, y, "Resumo por Parte:")
    y -= 0.6 * cm

    # Desenhar pequenos "cards" de resumo
    x_offset = 2 * cm
    for parte, total in totais_por_parte.items():
        # Desenha um retângulo sutil de fundo
        p.setStrokeColor(colors.HexColor("#e5e7eb"))
        p.setFillColor(colors.HexColor("#f9fafb"))
        p.roundRect(x_offset, y - 1 * cm, 3.5 * cm, 1.2 * cm, 4, fill=1)
        
        # Texto do Total
        p.setFillColor(colors.HexColor("#667eea"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(x_offset + 0.3 * cm, y - 0.3 * cm, str(total))
        
        # Texto da Parte
        p.setFillColor(colors.HexColor("#6b7280"))
        p.setFont("Helvetica", 7)
        p.drawString(x_offset + 0.3 * cm, y - 0.80 * cm, parte.upper())
        
        x_offset += 3.8 * cm # Move para o lado para o próximo card
        
        # Se ultrapassar a largura da página, pula linha
        if x_offset > largura - 5 * cm:
            x_offset = 2 * cm
            y -= 1.5 * cm

    y -= 1.5 * cm
    p.setStrokeColor(colors.HexColor("#e5e7eb"))
    p.line(2 * cm, y, largura - 2 * cm, y)

    # --- TABELA DE REGISTROS ---
    y -= 0.8 * cm
    p.setFont("Helvetica-Bold", 9)
    p.setFillColor(colors.HexColor("#374151"))
    p.drawString(2 * cm, y, "DATA")
    p.drawString(4.5 * cm, y, "LANÇADO POR")
    p.drawString(9 * cm, y, "OPERADOR (FICHA)")
    p.drawString(14 * cm, y, "PARTE")
    p.drawRightString(largura - 2 * cm, y, "QTD")
    
    y -= 0.3 * cm
    p.line(2 * cm, y, largura - 2 * cm, y)
    y -= 0.6 * cm

    p.setFont("Helvetica", 9)
    for reg in dados_para_tabela:
        if y < 3 * cm:
            p.showPage()
            y = altura - 2 * cm
            p.setFont("Helvetica", 9)

        qtd = reg.total()
        perfil_nome = reg.ficha.operador.get_full_name() or reg.ficha.operador.username

        p.setFillColor(colors.black)
        p.drawString(2 * cm, y, reg.ficha.data.strftime('%d/%m/%Y'))
        p.drawString(4.5 * cm, y, str(perfil_nome)[:20])
        p.setFont("Helvetica-Bold", 9)
        p.drawString(9 * cm, y, str(reg.ficha.nome_ficha)[:25])
        p.setFont("Helvetica", 9)
        p.drawString(14 * cm, y, str(reg.parte.nome)[:20])
        
        p.setFillColor(colors.HexColor("#667eea"))
        p.drawRightString(largura - 2 * cm, y, str(qtd))
        
        y -= 0.6 * cm

    # Rodapé Final
    y -= 0.5 * cm
    p.setStrokeColor(colors.HexColor("#764ba2"))
    p.line(largura - 7 * cm, y + 0.3 * cm, largura - 2 * cm, y + 0.3 * cm)
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.HexColor("#764ba2"))
    p.drawString(largura - 8 * cm, y - 0.2 * cm, "TOTAL GERAL:")
    p.drawRightString(largura - 2 * cm, y - 0.2 * cm, str(total_geral))

    p.showPage()
    p.save()
    return response


@login_required
def historico_inventario(request, ficha_id):
    ficha = get_object_or_404(FichaInventario, id=ficha_id)
    
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo_acao = request.GET.get('acao') # adicionar, subtrair ou excluido

    movimentacoes = LogMovimentacaoV2.objects.filter(ficha=ficha)

    #filtro da data
    if data_inicio and data_fim:
        movimentacoes = movimentacoes.filter(
            criado_em__date__gte=data_inicio,
            criado_em__date__lte=data_fim
        )
    else:
        # se não tiver filtro, mantém o padrao de 7 dias
        hoje = timezone.now().date()
        uma_semana_atras = hoje - timedelta(days=7)
        movimentacoes = movimentacoes.filter(criado_em__date__gte=uma_semana_atras)

    # agora o filtro de açao
    if tipo_acao:
        if tipo_acao == 'excluido':
            # Itens que foram apagados da ficha (o item_id no log virou NULL)
            movimentacoes = movimentacoes.filter(item__isnull=True)
        else:
            # Filtra exatamente pela string 'adicionar' ou 'subtrair'
            movimentacoes = movimentacoes.filter(acao=tipo_acao)

    movimentacoes = movimentacoes.select_related(
        'item', 'item__modelo', 'item__cor', 'item__tamanho', 'operador'
    ).order_by('-criado_em')

    paginator = Paginator(movimentacoes, 20)  # 20 movimentações por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'qualidade/relatorio_inventario.html', {
        'ficha': ficha,
        'movimentacoes': page_obj,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'acao_selecionada': tipo_acao,
    })