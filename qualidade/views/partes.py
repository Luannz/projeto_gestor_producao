# qualidade/views/partes.py
"""
Views de gerenciamento de partes do calçado
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import models

from ..models import ParteCalcado


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