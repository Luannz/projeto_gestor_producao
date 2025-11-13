# qualidade/views/operadores.py
"""
Views de gerenciamento de operadores
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import models

from ..models import NomeOperador


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