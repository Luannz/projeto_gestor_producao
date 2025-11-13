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

from ..models import Ficha, ParteCalcado, NomeOperador


@login_required
def home(request):
    """Página inicial - lista de fichas"""
    user = request.user
    
    # Verificar se usuário tem perfil
    try:
        perfil = user.perfil
    except:
        messages.error(request, 'Seu usuário não possui perfil definido. Contate o administrador.')
        return redirect('logout')
    
    # Filtrar fichas NÃO EXCLUÍDAS baseado no perfil
    if perfil.tipo == 'operador':
        fichas = Ficha.objects.filter(operador=user, excluido=False)
    else:  # qualidade
        fichas = Ficha.objects.filter(excluido=False)
    
    # Filtro por data
    data_filtro = request.GET.get('data')
    if data_filtro:
        fichas = fichas.filter(data=data_filtro)

    paginator = Paginator(fichas.order_by('-data', '-id', '-criada_em'), 21)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'fichas': page_obj,
        'perfil': perfil,
        'data_hoje': date.today(),
    }
    return render(request, 'qualidade/home.html', context)


@login_required
def criar_ficha(request):
    """Criar nova ficha"""
    # Verificar se é operador
    if request.user.perfil.tipo != 'operador':
        messages.error(request, 'Apenas operadores podem criar fichas')
        return redirect('home')
    
    nomes_operador = NomeOperador.objects.filter(ativo=True, excluido=False).order_by('ordem', 'nome')

    if request.method == 'POST':
        data = request.POST.get('data')
        nome_ficha = request.POST.get('nome_ficha')
        
        if data and nome_ficha:
            ficha = Ficha.objects.create(
                operador=request.user,
                data=data,
                nome_ficha=nome_ficha
            )
            messages.success(request, 'Ficha criada com sucesso!')
            return redirect('editar_ficha', ficha_id=ficha.id)
        else:
            messages.error(request, 'Preencha todos os campos')
    
    context = {
        'data_hoje': date.today(),
        'nomes_operador': nomes_operador,
    }
    return render(request, 'qualidade/criar_ficha.html', context)


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
    partes_disponiveis = ParteCalcado.objects.filter(ativo=True, excluido=False).order_by('ordem', 'nome')
    
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
    """Mover ficha para lixeira (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem excluir fichas')
        return redirect('home')
    
    if request.method == 'POST':
        try:
            ficha = Ficha.objects.get(id=ficha_id, excluido=False)
            ficha.excluido = True
            ficha.excluido_em = timezone.now()
            ficha.excluido_por = request.user
            ficha.save()
            messages.success(request, f'Ficha "{ficha.nome_ficha}" movida para a lixeira!')
        except Ficha.DoesNotExist:
            messages.error(request, 'Ficha não encontrada')
    
    return redirect('home')


@login_required
def lixeira_fichas(request):
    """Lixeira de fichas (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        ficha_id = request.POST.get('ficha_id')
        
        if acao == 'restaurar':
            try:
                ficha = Ficha.objects.get(id=ficha_id, excluido=True)
                ficha.excluido = False
                ficha.excluido_em = None
                ficha.excluido_por = None
                ficha.save()
                messages.success(request, f'Ficha "{ficha.nome_ficha}" restaurada com sucesso!')
            except Ficha.DoesNotExist:
                messages.error(request, 'Ficha não encontrada na lixeira')
        
        elif acao == 'excluir_permanente':
            try:
                ficha = Ficha.objects.get(id=ficha_id, excluido=True)
                nome_ficha = ficha.nome_ficha
                ficha.delete()
                messages.success(request, f'Ficha "{nome_ficha}" excluída permanentemente!')
            except Ficha.DoesNotExist:
                messages.error(request, 'Ficha não encontrada na lixeira')
        
        return redirect('lixeira_fichas')
    
    # Listar apenas fichas EXCLUÍDAS
    fichas_excluidas = Ficha.objects.filter(excluido=True).order_by('-excluido_em')
    
    context = {
        'fichas': fichas_excluidas,
    }
    return render(request, 'qualidade/lixeira_fichas.html', context)