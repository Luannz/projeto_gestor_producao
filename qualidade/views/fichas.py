# qualidade/views/fichas.py
"""
Views relacionadas ao CRUD de fichas
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import date
from django.db.models import Sum, F, Q

from ..models import Ficha, ParteCalcado, NomeOperador, FichaInventario, ItemInventario


@login_required
def home(request):
    perfil = request.user.perfil
    hoje = timezone.now().date()
    data_filtro = request.GET.get('data')

    # Grupo do usuário
    is_qualidade = request.user.groups.filter(name='Qualidade').exists()
    grupo_usuario = request.user.groups.first()
    grupo_nome = grupo_usuario.name if grupo_usuario else None

    # ----- 1. DEFINIÇÃO DO QUERYSET BASE (FICHAS NORMAIS) -----
    fichas_queryset = Ficha.objects.filter(excluido=False).select_related(
        'operador'
    ).prefetch_related('registros').order_by('-criada_em')

    # ----- 2. APLICAR REGRAS DE VISIBILIDADE E DATA -----
    if is_qualidade:
        # Se for Qualidade: 
        # - Se ele selecionou uma data no calendário, filtra por ela.
        # - Se não selecionou nada, mostra TODAS (sem filtro de data).
        if data_filtro:
            fichas_queryset = fichas_queryset.filter(data=data_filtro)
    else:
        # Se NÃO for qualidade (Operadores, etc):
        # - Forçamos uma data: ou a selecionada ou HOJE.
        data_para_filtrar = data_filtro if data_filtro else hoje
        fichas_queryset = fichas_queryset.filter(data=data_para_filtrar)

        # - Restrição de dono: só vê o que ele mesmo criou
        if grupo_nome == "Injetora":
            fichas_queryset = Ficha.objects.none()
        else:
            fichas_queryset = fichas_queryset.filter(operador=request.user)
            
            # Filtro opcional por setor
            if grupo_nome and perfil.tipo == 'operador':
                fichas_queryset = fichas_queryset.filter(setor=grupo_nome)
    # 3. Paginação (Usando a variável correta: fichas_queryset)
    paginator = Paginator(fichas_queryset, 12)
    page_number = request.GET.get("page")
    fichas_paginadas = paginator.get_page(page_number)

    # ----- FICHAS DE INVENTÁRIO -----
    if grupo_nome in ["Injetora", "Qualidade"]:
        if perfil.tipo == "operador":
            fichas_inventario = FichaInventario.objects.filter(
                operador=request.user,excluido=False
            ).order_by("-atualizada_em", "-data")
        else:
            fichas_inventario = FichaInventario.objects.filter(
                excluido=False
            ).order_by("-atualizada_em", "-data")
    else:
        fichas_inventario = None  # não mostra inventário
    #--Filtro de Data--#    
    if data_filtro:
        if fichas_inventario is not None:
            fichas_inventario = fichas_inventario.filter(data=data_filtro)


    # --- CÁLCULO DO TOTAL GERAL ---
    total_avulsos_geral = 0
    total_pares_geral = 0
    total_pares_absoluto = 0
    
    if fichas_inventario:
        itens = ItemInventario.objects.filter(ficha__in=fichas_inventario)
        # 1. Total de Pares Formados 
        total_pares_geral = sum(item.total_pares for item in itens)

        # 2. ttotal de pes Avulsos (soma das diferenças entre E e D em cada item)
        # Se tem 10E e 8D, tem 2 avulsos. Se tem 5E e 10D, tem 5 avulsos.
        total_avulsos_geral = sum(abs(item.quantidade_pe_esquerdo - item.quantidade_pe_direito) for item in itens)

        # 3. O grande total (todos os pés físicos / 2)
        # Isso conta quantos pares existem no total do inventario, mesmo que sejam pares avulsos
        soma_todos_os_pes = sum((item.quantidade_pe_esquerdo + item.quantidade_pe_direito) for item in itens)
        total_pares_absoluto = soma_todos_os_pes / 2

    context = {
        "perfil": perfil,
        "grupo_usuario": grupo_nome,
        "fichas": fichas_paginadas,
        "fichas_inventario": fichas_inventario,
        "total_pares_geral": total_pares_geral,
        "total_avulsos_geral": total_avulsos_geral,
        "total_pares_absoluto": total_pares_absoluto,
        "is_qualidade": is_qualidade,
        "data_atual": data_filtro if data_filtro else (None if is_qualidade else hoje),
        "data_hoje": hoje,
    }

    return render(request, "qualidade/home.html", context)


@login_required
def criar_ficha(request):

    # Apenas operadores podem criar ficha
    if request.user.perfil.tipo != 'operador':
        messages.error(request, 'Apenas operadores podem criar fichas')
        return redirect('home')

    # --- SE FOR INJETORA ---
    if request.user.groups.filter(name='Injetora').exists():

        if request.method == 'POST':
            nome_ficha = request.POST.get('nome_ficha')
            data = request.POST.get('data')

            if nome_ficha and data:
                ficha_inventario = FichaInventario.objects.create(
                    operador=request.user,
                    nome_ficha=nome_ficha,
                    data=data,
                    setor="INJETORA"
                )

                messages.success(request, "Ficha criada com sucesso!")
                return redirect('visualizar_ficha_inventario', ficha_id=ficha_inventario.id)

            messages.error(request, "Preencha todos os campos.")

        return render(request, 'qualidade/criar_ficha_inventario.html', {
            'data_hoje': date.today(),
        })

    # --- OUTROS SETORES ---
    nomes_operador = NomeOperador.objects.filter(
        ativo=True, excluido=False
    ).order_by('nome')

    if request.method == 'POST':
        data = request.POST.get('data')
        nome_ficha = request.POST.get('nome_ficha')
        
        if data and nome_ficha:
            ficha = Ficha.objects.create(
                operador=request.user,
                data=data,
                nome_ficha=nome_ficha,
            )
            messages.success(request, 'Ficha criada com sucesso!')
            return redirect('editar_ficha', ficha_id=ficha.id)
        else:
            messages.error(request, 'Preencha todos os campos.')

    return render(request, 'qualidade/criar_ficha.html', {
        'data_hoje': date.today(),
        'nomes_operador': nomes_operador,
    })



@login_required
@ensure_csrf_cookie
def editar_ficha(request, ficha_id):
    """Editar ficha existente"""
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Verificar permissão
    if request.user.perfil.tipo == 'operador' and ficha.operador != request.user:
        messages.error(request, 'Você não tem permissão para editar esta ficha')
        return redirect('home')
    
    # Buscar todas as partes ativas E NÃO EXCLUÍDAS
    partes_disponiveis = ParteCalcado.objects.filter(ativo=True, excluido=False).order_by('nome' ,'ordem')
    
    # Buscar registros existentes desta ficha
    registros_existentes = ficha.registros.all().select_related('parte')
    
    # IDs das partes já adicionadas
    partes_adicionadas_ids = list(registros_existentes.values_list('parte_id', flat=True))
    
    # Preparar dados dos registros
    registros = {}
    for registro in registros_existentes:
        registros[registro.parte.id] = {
            'registro': registro,
            'quantidades': registro.quantidades or [],
            'parte_nome': registro.parte.nome
        }
    
    context = {
        'ficha': ficha,
        'partes_disponiveis': partes_disponiveis,
        'registros': registros,
        'registros_existentes': registros_existentes,
        'partes_adicionadas_ids': partes_adicionadas_ids,
        'pode_editar': request.user.perfil.tipo == 'operador' and ficha.operador == request.user,
    }
    return render(request, 'qualidade/editar_ficha.html', context)


@login_required
def visualizar_ficha(request, ficha_id):
    """Visualizar ficha (apenas leitura)"""
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Buscar todos os registros
    registros = ficha.registros.all().select_related('parte')
    
    # Calcular total geral
    total_geral = sum(registro.total() for registro in registros)
    
    context = {
        'ficha': ficha,
        'registros': registros,
        'total_geral': total_geral,
    }
    return render(request, 'qualidade/visualizar_ficha.html', context)


@login_required
def excluir_ficha(request, ficha_id):
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem excluir fichas')
        return redirect('home')

    if request.method == 'POST':
        ficha = get_object_or_404(Ficha, id=ficha_id, excluido=False)

        ficha.excluido = True
        ficha.excluido_em = timezone.now()
        ficha.excluido_por = request.user
        ficha.save()
        messages.success(request, f'Ficha de inventário "{ficha.nome_ficha}" movida para a lixeira!')
    return redirect('home')


@login_required
def lixeira_fichas(request):
    """Lixeira de fichas (Ficha e FichaInventario)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira')
        return redirect('home')

    if request.method == 'POST':
        acao = request.POST.get('acao')
        ficha_id = request.POST.get('ficha_id')
        tipo = request.POST.get('tipo')

        try:
            if tipo == 'Inventario':
                ficha = FichaInventario.objects.get(id=ficha_id, excluido=True)
            else:
                ficha = Ficha.objects.get(id=ficha_id, excluido=True)

            if acao == 'restaurar':
                ficha.excluido = False
                ficha.excluido_em = None
                ficha.excluido_por = None
                ficha.save()
                messages.success(request, f'{ficha.tipo_ficha} "{ficha.nome_ficha}" restaurada com sucesso!')

            elif acao == 'excluir_permanente':
                nome = ficha.nome_ficha
                ficha.delete()
                messages.success(request, f'{ficha.tipo_ficha} "{nome}" excluída permanentemente!')

        except (Ficha.DoesNotExist, FichaInventario.DoesNotExist):
            messages.error(request, 'Ficha não encontrada na lixeira')

        return redirect('lixeira_fichas')

    # GET → listar fichas excluídas
    fichas_excluidas = list(Ficha.objects.filter(excluido=True)) + list(
        FichaInventario.objects.filter(excluido=True)
    )

    # Ordenar pela data de exclusão (mais recente primeiro)
    fichas_excluidas.sort(key=lambda f: f.excluido_em or 0, reverse=True)

    context = {
        'fichas': fichas_excluidas,
    }
    return render(request, 'qualidade/lixeira_fichas.html', context)