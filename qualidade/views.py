from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Max
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils import timezone
from django.core.cache import cache
from datetime import date
from .models import Ficha, ParteCalcado, RegistroParte, PerfilUsuario, NomeOperador
from django.db import models
import json
import hashlib
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from io import BytesIO
from django.contrib.auth.models import User
from datetime import datetime
from datetime import date
import locale




def login_view(request):
    """Página de login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha incorretos')
    
    return render(request, 'qualidade/login.html')


def logout_view(request):
    """Logout"""
    logout(request)
    return redirect('login')


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
    
    context = {
        'fichas': fichas,
        'perfil': perfil,
        'data_hoje': date.today(),
    }
    return render(request, 'qualidade/home.html', context)


@login_required
def lixeira_partes(request):
    """Lixeira de partes (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        parte_id = request.POST.get('parte_id')
        
        if acao == 'restaurar':
            try:
                parte = ParteCalcado.objects.get(id=parte_id, excluido=True)
                parte.excluido = False
                parte.excluido_em = None
                parte.save()
                messages.success(request, f'Parte "{parte.nome}" restaurada com sucesso!')
            except ParteCalcado.DoesNotExist:
                messages.error(request, 'Parte não encontrada na lixeira')
        
        elif acao == 'excluir_permanente':
            try:
                parte = ParteCalcado.objects.get(id=parte_id, excluido=True)
                nome_parte = parte.nome
                parte.delete()
                messages.success(request, f'Parte "{nome_parte}" excluída permanentemente!')
            except ParteCalcado.DoesNotExist:
                messages.error(request, 'Parte não encontrada na lixeira')
        
        return redirect('lixeira_partes')
    
    # Listar apenas partes EXCLUÍDAS
    partes_excluidas = ParteCalcado.objects.filter(excluido=True).order_by('-excluido_em')
    
    context = {
        'partes': partes_excluidas,
    }
    return render(request, 'qualidade/lixeira_partes.html', context)


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
def gerenciar_operadores(request):
    """Gerenciar operadores (apenas qualidade)"""
    # Verificar se é usuário da qualidade
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerenciar operadores')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'criar':
            nome = request.POST.get('nome')
            if nome:
                # Verificar se já existe (incluindo excluídos)
                if NomeOperador.objects.filter(nome__iexact=nome).exists():
                    messages.error(request, f'O operador "{nome}" já existe')
                else:
                    # Pegar a maior ordem atual e adicionar 1
                    max_ordem = NomeOperador.objects.all().aggregate(models.Max('ordem'))['ordem__max'] or 0
                    NomeOperador.objects.create(nome=nome, ordem=max_ordem + 1)
                    messages.success(request, f'Operador "{nome}" criado com sucesso!')
            else:
                messages.error(request, 'Digite o nome do operador')
        
        elif acao == 'mover_lixeira':
            operador_id = request.POST.get('operador_id')
            try:
                operador = NomeOperador.objects.get(id=operador_id, excluido=False)
                operador.excluido = True
                operador.excluido_em = timezone.now()
                operador.save()
                messages.success(request, f'Parte "{operador.nome}" movida para a lixeira!')
            except NomeOperador.DoesNotExist:
                messages.error(request, 'Operador não encontrado')
        
        elif acao == 'ativar_desativar':
            operador_id = request.POST.get('operador_id')
            try:
                operador = NomeOperador.objects.get(id=operador_id, excluido=False)
                operador.ativo = not operador.ativo
                operador.save()
                status = 'ativo' if operador.ativo else 'desativado'
                messages.success(request, f'Operador "{operador.nome}" {status}!')
            except NomeOperador.DoesNotExist:
                messages.error(request, 'Operador não encontrada')
        
        return redirect('gerenciar_operadores')
    
    # Listar apenas partes NÃO EXCLUÍDAS
    operadores = NomeOperador.objects.filter(excluido=False).order_by('ordem', 'nome')
    
    context = {
        'operadores': operadores,
    }
    return render(request, 'qualidade/gerenciar_operadores.html', context)


@login_required
def lixeira_operadores(request):
    """Lixeira de nomes de operadores (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        operador_id = request.POST.get('operador_id')
        
        if acao == 'restaurar':
            try:
                operador = NomeOperador.objects.get(id=operador_id, excluido=True)
                operador.excluido = False
                operador.excluido_em = None
                operador.save()
                messages.success(request, f'Registro do nome "{operador.nome}" restaurado com sucesso!')
            except NomeOperador.DoesNotExist:
                messages.error(request, 'Nome do operador não encontrada na lixeira')
        
        elif acao == 'excluir_permanente':
            try:
                operador = NomeOperador.objects.get(id=operador_id, excluido=True)
                nome_operador = operador.nome
                operador.delete()
                messages.success(request, f'Registro do nome "{nome_operador}" excluído permanentemente!')
            except NomeOperador.DoesNotExist:
                messages.error(request, 'Nome do operador não encontrada na lixeira')
        
        return redirect('lixeira_operadores')
    
    # Listar apenas partes EXCLUÍDAS
    operadores_excluidos = NomeOperador.objects.filter(excluido=True).order_by('-excluido_em')
    
    context = {
        'operadores': operadores_excluidos,
    }
    return render(request, 'qualidade/lixeira_operadores.html', context)



@login_required
def gerenciar_partes(request):
    """Gerenciar partes do calçado (apenas qualidade)"""
    # Verificar se é usuário da qualidade
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerenciar partes')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'criar':
            nome = request.POST.get('nome')
            if nome:
                # Verificar se já existe (incluindo excluídas)
                if ParteCalcado.objects.filter(nome__iexact=nome).exists():
                    messages.error(request, f'A parte "{nome}" já existe')
                else:
                    # Pegar a maior ordem atual e adicionar 1
                    max_ordem = ParteCalcado.objects.all().aggregate(models.Max('ordem'))['ordem__max'] or 0
                    ParteCalcado.objects.create(nome=nome, ordem=max_ordem + 1)
                    messages.success(request, f'Parte "{nome}" criada com sucesso!')
            else:
                messages.error(request, 'Digite o nome da parte')
        
        elif acao == 'mover_lixeira':
            parte_id = request.POST.get('parte_id')
            try:
                parte = ParteCalcado.objects.get(id=parte_id, excluido=False)
                parte.excluido = True
                parte.excluido_em = timezone.now()
                parte.save()
                messages.success(request, f'Parte "{parte.nome}" movida para a lixeira!')
            except ParteCalcado.DoesNotExist:
                messages.error(request, 'Parte não encontrada')
        
        elif acao == 'ativar_desativar':
            parte_id = request.POST.get('parte_id')
            try:
                parte = ParteCalcado.objects.get(id=parte_id, excluido=False)
                parte.ativo = not parte.ativo
                parte.save()
                status = 'ativada' if parte.ativo else 'desativada'
                messages.success(request, f'Parte "{parte.nome}" {status}!')
            except ParteCalcado.DoesNotExist:
                messages.error(request, 'Parte não encontrada')
        
        return redirect('gerenciar_partes')
    
    # Listar apenas partes NÃO EXCLUÍDAS
    partes = ParteCalcado.objects.filter(excluido=False).order_by('ordem', 'nome')
    
    context = {
        'partes': partes,
    }
    return render(request, 'qualidade/gerenciar_partes.html', context)


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
def adicionar_parte_ficha(request, ficha_id):
    """API para adicionar uma parte à ficha via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Verificar permissão
    if request.user.perfil.tipo == 'operador' and ficha.operador != request.user:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    try:
        data = json.loads(request.body)
        parte_id = data.get('parte_id')
        
        if not parte_id:
            return JsonResponse({'error': 'ID da parte não fornecido'}, status=400)
        
        parte = get_object_or_404(ParteCalcado, id=parte_id, ativo=True, excluido=False)
        
        # Verificar se já existe
        if RegistroParte.objects.filter(ficha=ficha, parte=parte).exists():
            return JsonResponse({'error': 'Esta parte já foi adicionada'}, status=400)
        
        # Criar registro
        registro = RegistroParte.objects.create(
            ficha=ficha,
            parte=parte,
            quantidades=[]
        )
        
        return JsonResponse({
            'success': True,
            'parte_id': parte.id,
            'parte_nome': parte.nome
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def remover_parte_ficha(request, ficha_id, parte_id):
    """API para remover uma parte da ficha via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Verificar permissão
    if request.user.perfil.tipo == 'operador' and ficha.operador != request.user:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    try:
        registro = RegistroParte.objects.get(ficha=ficha, parte_id=parte_id)
        parte_nome = registro.parte.nome
        registro.delete()
        
        return JsonResponse({
            'success': True,
            'parte_nome': parte_nome
        })
    
    except RegistroParte.DoesNotExist:
        return JsonResponse({'error': 'Parte não encontrada nesta ficha'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def adicionar_quantidade(request, ficha_id, parte_id):
    """API para adicionar quantidade via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    parte = get_object_or_404(ParteCalcado, id=parte_id)
    
    # Verificar permissão
    if request.user.perfil.tipo == 'operador' and ficha.operador != request.user:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    try:
        data = json.loads(request.body)
        quantidade = int(data.get('quantidade', 0))
        
        if quantidade <= 0:
            return JsonResponse({'error': 'Quantidade deve ser maior que zero'}, status=400)
        
        # Buscar ou criar registro
        registro, created = RegistroParte.objects.get_or_create(
            ficha=ficha,
            parte=parte,
            defaults={'quantidades': []}
        )
        
        # Adicionar quantidade
        registro.adicionar_quantidade(quantidade)
        
        return JsonResponse({
            'success': True,
            'quantidades': registro.quantidades,
            'total': registro.total()
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def remover_quantidade(request, ficha_id, parte_id):
    """API para remover última quantidade via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    ficha = get_object_or_404(Ficha, id=ficha_id)
    
    # Verificar permissão
    if request.user.perfil.tipo == 'operador' and ficha.operador != request.user:
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    
    try:
        registro = RegistroParte.objects.get(ficha=ficha, parte_id=parte_id)
        
        if registro.quantidades:
            registro.quantidades.pop()
            registro.save()
        
        return JsonResponse({
            'success': True,
            'quantidades': registro.quantidades,
            'total': registro.total()
        })
    
    except RegistroParte.DoesNotExist:
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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
    nomes_fichas = (Ficha.objects.filter(excluido=False).order_by('nome_ficha').values_list('nome_ficha', flat=True).distinct())
    
    # Inicializar dados
    dados_relatorio = None
    total_geral = 0  # ✅ adicionamos aqui para somar tudo

    # Se houver filtros aplicados, processar
    if data_inicio and data_fim:
        # Converter strings para datas
        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Buscar fichas no período
        fichas = Ficha.objects.filter(
            data__gte=data_inicio_obj,
            data__lte=data_fim_obj,
            excluido=False
        )
        
        # Aplicar filtro de nome_ficha se selecionado
        if nome_ficha:
            fichas = fichas.filter(nome_ficha=nome_ficha)

        # Filtrar por operador se selecionado
        if operador_id:
            fichas = fichas.filter(operador_id=operador_id)
        
        # Agrupar dados por operador
        dados_por_operador = {}
        
        for ficha in fichas:
            operador_nome = ficha.operador.get_full_name() or ficha.operador.username
            
            if operador_nome not in dados_por_operador:
                dados_por_operador[operador_nome] = {
                    'operador': ficha.operador,
                    'partes': {},
                    'fichas': []
                }
            
            if ficha.nome_ficha not in dados_por_operador[operador_nome]['fichas']:
                dados_por_operador[operador_nome]['fichas'].append(ficha.nome_ficha)

            # Buscar registros da ficha
            registros = ficha.registros.all().select_related('parte')
            
            # Filtrar por parte se selecionado
            if parte_id:
                registros = registros.filter(parte_id=parte_id)
            
            for registro in registros:
                parte_nome = registro.parte.nome
                
                if parte_nome not in dados_por_operador[operador_nome]['partes']:
                    dados_por_operador[operador_nome]['partes'][parte_nome] = 0
                
                # Soma por parte e soma geral
                valor = registro.total()
                dados_por_operador[operador_nome]['partes'][parte_nome] += valor
                total_geral += valor  # ✅ acumulando total geral aqui
        
        dados_relatorio = dados_por_operador
    
    # Monta o contexto completo
    context = {
        'partes': partes,
        'operadores': operadores,
        'nomes_fichas': nomes_fichas,
        'dados_relatorio': dados_relatorio,
        'total_geral': total_geral,  # ✅ agora o template só exibe
        'data_inicio': data_inicio_obj if data_inicio and data_fim else None,
        'data_fim': data_fim_obj if data_inicio and data_fim else None,
        'parte_id': parte_id,
        'operador_id': operador_id,
        'nome_ficha': nome_ficha,
    }
    return render(request, 'qualidade/relatorios.html', context)


@login_required
def gerar_relatorio_periodo(request):
    """Gerar relatório PDF de período"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerar relatórios')
        return redirect('home')
    
    # Buscar parâmetros (MESMOS da view relatorios)
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    parte_id = request.GET.get('parte_id')
    operador_id = request.GET.get('operador_id')
    nome_ficha = request.GET.get('nome_ficha')
    
    if not data_inicio or not data_fim:
        messages.error(request, 'Selecione o período')
        return redirect('relatorios')
    
    # Converter strings para datas (tratando dois formatos possíveis)
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_ALL, '')

    def parse_data(data_str):
        formatos = [
            '%Y-%m-%d',            # formato padrão do input date
            '%d de %B de %Y',      # formato completo (ex: "2 de novembro de 2025")
            '%d de %b de %Y',      # formato abreviado (ex: "2 de nov de 2025")
            '%d/%m/%Y',            # formato numérico comum
        ]
        for formato in formatos:
            try:
                return datetime.strptime(data_str, formato).date()
            except ValueError:
                continue
        raise ValueError(f"Formato de data inválido: {data_str}")

    data_inicio_obj = parse_data(data_inicio)
    data_fim_obj = parse_data(data_fim)

    
    # Buscar fichas no período (IGUAL à view relatorios)
    fichas = Ficha.objects.filter(
        data__gte=data_inicio_obj,
        data__lte=data_fim_obj,
        excluido=False
    )
    
    # Aplicar filtro de nome_ficha se selecionado (IGUAL)
    if nome_ficha:
        fichas = fichas.filter(nome_ficha=nome_ficha)
    
    # Filtrar por operador se selecionado (IGUAL)
    if operador_id:
        fichas = fichas.filter(operador_id=operador_id)
    
    # Agrupar dados por operador (IGUAL à view relatorios)
    dados_por_operador = {}
    total_geral = 0
    
    for ficha in fichas:
        operador_nome = ficha.operador.get_full_name() or ficha.operador.username
        
        if operador_nome not in dados_por_operador:
            dados_por_operador[operador_nome] = {
                'operador': ficha.operador,
                'partes': {},
                'fichas': []
            }
        
        if ficha.nome_ficha not in dados_por_operador[operador_nome]['fichas']:
            dados_por_operador[operador_nome]['fichas'].append(ficha.nome_ficha)
        
        # Buscar registros da ficha
        registros = ficha.registros.all().select_related('parte')
        
        # Filtrar por parte se selecionado
        if parte_id:
            registros = registros.filter(parte_id=parte_id)
        
        for registro in registros:
            parte_nome = registro.parte.nome
            
            if parte_nome not in dados_por_operador[operador_nome]['partes']:
                dados_por_operador[operador_nome]['partes'][parte_nome] = 0
            
            # Soma por parte e soma geral
            valor = registro.total()
            dados_por_operador[operador_nome]['partes'][parte_nome] += valor
            total_geral += valor
    
    # ====== AGORA GERAR O PDF ======
    
    # Criar PDF em paisagem
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Título
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 50, "Relatório de Produção por Período")
    
    # Período
    p.setFont("Helvetica", 12)
    periodo_texto = f"Período: {data_inicio_obj.strftime('%d/%m/%Y')} a {data_fim_obj.strftime('%d/%m/%Y')}"
    p.drawString(50, height - 75, periodo_texto)
    
    # Filtros aplicados
    y = height - 95
    p.setFont("Helvetica", 10)
    
    if operador_id:
        try:
            operador = User.objects.get(id=operador_id)
            operador_nome_filtro = operador.get_full_name() or operador.username
            p.drawString(50, y, f"Operador: {operador_nome_filtro}")
            y -= 15
        except:
            pass
    
    if parte_id:
        try:
            parte = ParteCalcado.objects.get(id=parte_id)
            p.drawString(50, y, f"Parte: {parte.nome}")
            y -= 15
        except:
            pass
    
    if nome_ficha:
        p.drawString(50, y, f"Nome da Ficha: {nome_ficha}")
        y -= 15
    
    # Linha separadora
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 30
    
    # Dados por operador
    for operador_nome, dados in sorted(dados_por_operador.items()):
        # Verificar se precisa de nova página
        if y < 150:
            p.showPage()
            y = height - 50
        
        # Nome do operador
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"👤 {operador_nome}")
        y -= 25
        
        # Fichas do operador
        if dados['fichas']:
            p.setFont("Helvetica-Oblique", 10)
            fichas_texto = "Fichas: " + ", ".join(dados['fichas'][:3])
            if len(dados['fichas']) > 3:
                fichas_texto += f" (+{len(dados['fichas']) - 3} mais)"
            p.drawString(70, y, fichas_texto)
            y -= 20
        
        # Tabela de partes
        p.setFont("Helvetica", 11)
        
        if dados['partes']:
            for parte_nome, total in sorted(dados['partes'].items()):
                if y < 50:
                    p.showPage()
                    y = height - 50
                
                p.drawString(70, y, f"• {parte_nome}")
                p.drawRightString(width - 100, y, str(total))
                y -= 18
            
            # Total do operador
            total_operador = sum(dados['partes'].values())
            y -= 5
            p.setFont("Helvetica-Bold", 12)
            p.drawString(70, y, "TOTAL:")
            p.drawRightString(width - 100, y, str(total_operador))
            y -= 35
        else:
            p.setFont("Helvetica-Oblique", 10)
            p.drawString(70, y, "Nenhuma produção no período")
            y -= 30
    
    # Total geral
    if y < 80:
        p.showPage()
        y = height - 50
    
    y -= 10
    p.line(50, y, width - 50, y)
    y -= 30
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "TOTAL GERAL:")
    p.drawRightString(width - 100, y, str(total_geral))
    
    # Rodapé
    p.setFont("Helvetica", 8)
    p.drawString(50, 30, f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
    p.drawRightString(width - 50, 30, f"Usuário: {request.user.username}")
    
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    
    # Nome do arquivo
    nome_arquivo = f'relatorio_{data_inicio_obj.strftime("%Y%m%d")}_{data_fim_obj.strftime("%Y%m%d")}'
    if operador_id:
        nome_arquivo += f'_operador{operador_id}'
    if nome_ficha:
        nome_arquivo += f'_{nome_ficha[:20]}'
    nome_arquivo += '.pdf'
    
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    
    return response


@login_required
def gerar_relatorio(request, ficha_id):
    """Gerar relatório PDF"""
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