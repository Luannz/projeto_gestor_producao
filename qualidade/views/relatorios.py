# qualidade/views/relatorios.py
"""
Views de relatórios e geração de PDFs
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from datetime import datetime, timedelta
from django.utils import timezone 
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from django.core.paginator import Paginator

from ..models import Ficha, ParteCalcado, FichaInventario, LogMovimentacaoV2, RegistroParte, Cor, ItemInventario


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
    todos_usuarios = User.objects.filter(groups__name='Corte').distinct().order_by('first_name') # só usuarios do grupo corte
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
    
    # Captura de filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo_acao = request.GET.get('acao')
    cor_id = request.GET.get('cor_id')

    # Lógica de cores (Itens atuais + Itens que já passaram pelos logs)
    ids_cores_na_ficha = ItemInventario.objects.filter(ficha=ficha).values_list('cor_id', flat=True).distinct()
    ids_cores_nos_logs = LogMovimentacaoV2.objects.filter(ficha=ficha, item__isnull=False).values_list('item__cor_id', flat=True).distinct()
    todos_ids_cores = set(list(ids_cores_na_ficha) + list(ids_cores_nos_logs))
    cores_disponiveis = Cor.objects.filter(id__in=todos_ids_cores).order_by('nome')
    
    # Base da Query
    movimentacoes = LogMovimentacaoV2.objects.filter(ficha=ficha)

    # Aplicação de filtros de Data
    if data_inicio and data_fim:
        movimentacoes = movimentacoes.filter(criado_em__date__gte=data_inicio, criado_em__date__lte=data_fim)
    else:
        uma_semana_atras = timezone.now().date() - timedelta(days=7)
        movimentacoes = movimentacoes.filter(criado_em__date__gte=uma_semana_atras)

    # Filtro de Ação
    if tipo_acao:
        if tipo_acao == 'excluido':
            movimentacoes = movimentacoes.filter(item__isnull=True)
        else:
            movimentacoes = movimentacoes.filter(acao=tipo_acao)

    # Filtro de Cor
    if cor_id:
        cor_obj = Cor.objects.filter(id=cor_id).first()
        nome_cor = cor_obj.nome if cor_obj else ""
        movimentacoes = movimentacoes.filter(
            Q(item__cor_id=cor_id) | Q(identificacao_item__icontains=f" - {nome_cor} ")
        )

    # Execução da Query com select_related para performance
    movimentacoes_queryset = movimentacoes.select_related(
        'item', 'item__modelo', 'item__cor', 'item__tamanho', 'operador'
    ).order_by('-criado_em')

    # --- PROCESSAMENTO ---
    # Chamada da função auxiliar para agrupar pés em pares
    lista_final = processar_movimentacoes_para_pares(movimentacoes_queryset)
    resumo_totais = {}

    for log in movimentacoes_queryset: # Usamos o queryset original para pegar valores brutos
        chave = f"{log.identificacao_item}_{log.acao}"
        
        if chave not in resumo_totais:
            resumo_totais[chave] = {
                'item': log.identificacao_item,
                'acao': log.acao,
                'pd': 0,
                'pe': 0
            }
        
        if log.lado == 'PD':
            resumo_totais[chave]['pd'] += log.quantidade_movimentada
        else:
            resumo_totais[chave]['pe'] += log.quantidade_movimentada

    # Agora calculamos os pares sobre o total acumulado
    lista_resumo_final = []
    for chave, dados in resumo_totais.items():
        pd = dados['pd']
        pe = dados['pe']
        
        pares = min(pd, pe)
        sobra = abs(pd - pe)
        lado_sobra = 'PD' if pd > pe else 'PE'
        
        lista_resumo_final.append({
            'item': dados['item'],
            'acao': dados['acao'],
            'total_pares': pares,
            'total_sobra': sobra,
            'lado_sobra': lado_sobra
        })

    # Paginação
    paginator = Paginator(lista_final, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'qualidade/relatorio_inventario.html', {
        'resumo': lista_resumo_final,
        'ficha': ficha,
        'movimentacoes': page_obj,
        'cores': cores_disponiveis,
        'cor_selecionada': cor_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'acao_selecionada': tipo_acao,
    })


# Já que a lógica atual do sistema é baseada em pé esquerdo e pé direito separados, essa função ´ra pra
# analisar os logs de movimentação e identificar quando dois registros (um de cada lado) 
# correspondem a um mesmo movimento de par. Ela agrupa esses registros e calcula quantos pares 
# completos existem, se há sobras de algum lado, e marca os objetos para que o template possa exibir essas 
# informações, ela é complexa
def processar_movimentacoes_para_pares(queryset):
    """
    Agrupa logs de movimentação individuais (pés) em unidades de 'Pares' 
    quando detecta ações simultâneas de lados opostos para o mesmo item.
    
    Esta função adiciona atributos dinâmicos aos objetos:
    - exibir_como_par (bool)
    - qtd_pares_total (int)
    - qtd_sobra (int)
    - lado_sobra (str)
    """
    lista_final = []
    skip_ids = set()
    logs = list(queryset)
    
    for i in range(len(logs)):
        log_atual = logs[i]
        if log_atual.id in skip_ids:
            continue
            
        par_encontrado = None
        # Busca nos próximos 10 registros (janela de tempo próxima)
        for j in range(i + 1, min(i + 11, len(logs))):
            proximo_log = logs[j]
            
            diff_tempo = (log_atual.criado_em - proximo_log.criado_em).total_seconds()
            
            # Critérios para agrupar: mesmo item, mesma ação, lado oposto e tempo < 2s
            if (abs(diff_tempo) < 2 and 
                log_atual.item_id == proximo_log.item_id and 
                log_atual.acao == proximo_log.acao and
                log_atual.lado != proximo_log.lado):
                par_encontrado = proximo_log
                break
        
        if par_encontrado:
            # Calcula quantos pares completos existem e se há sobra de algum lado
            qtd_pe = log_atual.quantidade_movimentada if log_atual.lado == 'PE' else par_encontrado.quantidade_movimentada
            qtd_pd = log_atual.quantidade_movimentada if log_atual.lado == 'PD' else par_encontrado.quantidade_movimentada
            
            log_atual.exibir_como_par = True
            log_atual.qtd_pares_total = min(qtd_pe, qtd_pd)
            log_atual.qtd_sobra = abs(qtd_pe - qtd_pd)
            log_atual.lado_sobra = 'PE' if qtd_pe > qtd_pd else 'PD'
            
            skip_ids.add(par_encontrado.id)
        else:
            log_atual.exibir_como_par = False
            
        lista_final.append(log_atual)
    
    return lista_final