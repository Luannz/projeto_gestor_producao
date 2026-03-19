# qualidade/views/api.py
"""
Endpoints AJAX/API para manipulação de dados
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

from ..models import Ficha, ParteCalcado, RegistroParte, ModeloCalcado, Cor, ItemInventario, FichaInventario, TamanhoModelo


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

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
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


## API'S DAS FICHAS DE INVENTÁRIO ##

@login_required
def api_atualizar_item(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    item = get_object_or_404(ItemInventario, id=item_id)
    quantidade = int(request.POST.get('quantidade', 0))

    if quantidade < 0:
        return JsonResponse({'success': False, 'message': 'Quantidade inválida'})

    item.quantidade = quantidade
    item.save()

    return JsonResponse({'success': True})


def get_cores(request, id_modelo):
    modelo = get_object_or_404(ModeloCalcado, id=id_modelo, excluido=False)
    
    cores = modelo.cores.filter(excluido=False).order_by('nome')

    data = [
        {"id": cor.id, "nome": cor.nome}
        for cor in cores
    ]

    return JsonResponse({"cores": data})

def get_tamanhos(request, id_cor):
    modelo_id = request.GET.get("modelo_id")

    if not modelo_id:
        return JsonResponse({"error": "modelo_id é obrigatório"}, status=400)

    tamanhos = TamanhoModelo.objects.filter(
        modelo_id=modelo_id,
        cor_id=id_cor,
        ativo=True,
        excluido=False
    ).order_by("numero")

    data = [{"id": t.id, "numero": t.numero} for t in tamanhos]

    return JsonResponse({"tamanhos": data})

