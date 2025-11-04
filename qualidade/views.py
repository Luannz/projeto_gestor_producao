from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Max
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils import timezone
from datetime import date
from .models import Ficha, ParteCalcado, RegistroParte, PerfilUsuario
from django.db import models
import json
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO


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
                ficha.excluido_por = request.user
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
            ficha.excluir(request.user)
            messages.success(request, f'Ficha "{ficha.nome_ficha}" movida para a lixeira!')
        except Ficha.DoesNotExist:
            messages.error(request, 'Ficha não encontrada')

    return redirect('home')


@login_required
def gerenciar_partes(request):
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerenciar partes')
        return redirect('home')

    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'criar':
            nome = request.POST.get('nome')
            if nome:
                if ParteCalcado.objects.filter(nome__iexact=nome).exists():
                    messages.error(request, f'A parte "{nome}" já existe')
                else:
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
                parte.excluido_por = request.user
                parte.save()
                messages.success(request, f'Parte "{parte.nome}" movida para a lixeira!')
            except ParteCalcado.DoesNotExist:
                messages.error(request, 'Parte não encontrada')

        return redirect('gerenciar_partes')

    partes = ParteCalcado.objects.filter(excluido=False).order_by('ordem', 'nome')
    return render(request, 'qualidade/gerenciar_partes.html', {'partes': partes})


@login_required
def criar_ficha(request):
    """Criar nova ficha"""
    # Verificar se é operador
    if request.user.perfil.tipo != 'operador':
        messages.error(request, 'Apenas operadores podem criar fichas')
        return redirect('home')

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

    # Buscar todas as partes ativas
    partes_disponiveis = ParteCalcado.objects.filter(ativo=True).order_by('ordem', 'nome')

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

        parte = get_object_or_404(ParteCalcado, id=parte_id, ativo=True)

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