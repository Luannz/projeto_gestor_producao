# qualidade/views/inventario.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from datetime import date
from django.db import models
from django.core.paginator import Paginator
from django.db.models import F
from django.urls import reverse


from ..models import (
    FichaInventario, ItemInventario, ModeloCalcado, 
    Cor, TamanhoModelo , LogMovimentacaoV2
)


@login_required
def criar_ficha_inventario(request):
    """Criar nova ficha de inventário (apenas INJETORA)"""
    # Verificar se é operador do setor INJETORA
    if request.user.perfil.tipo != 'operador':
        messages.error(request, 'Apenas operadores podem criar fichas')
        return redirect('home')
    
    if not request.user.groups.filter(name='INJETORA').exists():
        messages.error(request, 'Esta funcionalidade é exclusiva do setor INJETORA')
        return redirect('home')
    
    modelos = ModeloCalcado.objects.filter(ativo=True, excluido=False).order_by('nome')
    
    if request.method == 'POST':
        nome_ficha = request.POST.get('nome_ficha')
        data = request.POST.get('data')
        
        if nome_ficha and data:
            ficha = FichaInventario.objects.create(
                operador=request.user,
                data=data,
                nome_ficha=nome_ficha
            )
            messages.success(request, 'Ficha de inventário criada com sucesso!')
            return redirect('editar_ficha_inventario', ficha_id=ficha.id)
        else:
            messages.error(request, 'Preencha todos os campos')
    
    context = {
        'data_hoje': date.today(),
        'modelos': modelos,
    }
    return render(request, 'qualidade/criar_ficha_inventario.html', context)


@login_required
@ensure_csrf_cookie
def editar_ficha_inventario(request, ficha_id):
    ficha = get_object_or_404(FichaInventario, id=ficha_id)

    # Permissão
    pode_editar = request.user.perfil.tipo == "operador"
    if not pode_editar:
        messages.error(request, "Você não tem permissão para editar esta ficha")
        return redirect("home")

    # -------------------------
    # POST → cria item
    # -------------------------
    if request.method == "POST":
        modelo_id = request.POST.get("modelo_id")
        cor_id = request.POST.get("cor_id")
        tamanho_id = request.POST.get("tamanho_id")
        quantidade_pe_direito = request.POST.get("quantidade_pe_direito", 0)
        quantidade_pe_esquerdo = request.POST.get("quantidade_pe_esquerdo", 0)

        try:
            quantidade_pe_direito = int(quantidade_pe_direito)
            quantidade_pe_esquerdo = int(quantidade_pe_esquerdo)

            if quantidade_pe_direito < 0 or quantidade_pe_esquerdo < 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "Quantidade inválida. Use apenas números positivos.")
            return redirect("editar_ficha_inventario", ficha_id=ficha_id)

        ja_existe = ItemInventario.objects.filter(
            ficha_id=ficha_id,
            modelo_id=modelo_id,
            cor_id=cor_id,
            tamanho_id=tamanho_id,
        ).exists()

        if ja_existe:
            messages.error(
                request,
                "Este item já existe na ficha! Escolha outro modelo/cor/tamanho."
            )
            return redirect("editar_ficha_inventario", ficha_id=ficha_id)

        modelo = get_object_or_404(ModeloCalcado, id=modelo_id)
        cor = get_object_or_404(Cor, id=cor_id)
        tamanho = get_object_or_404(TamanhoModelo, id=tamanho_id)

        item = ItemInventario.objects.create(
            ficha=ficha,
            modelo=modelo,
            cor=cor,
            tamanho=tamanho,
            quantidade_pe_direito=quantidade_pe_direito,
            quantidade_pe_esquerdo=quantidade_pe_esquerdo,
        )

        # REGISTRO NO HISTÓRICO
        # Registra a entrada do Pé Direito
        if quantidade_pe_direito > 0:
            LogMovimentacaoV2.objects.create(
                ficha=item.ficha,
                item=item,
                operador=request.user,
                acao='adicionar',
                lado='PD',
                quantidade_movimentada=quantidade_pe_direito,
                saldo_momento=quantidade_pe_direito # Saldo inicial
            )
        
        # Registra a entrada do Pé Esquerdo
        if quantidade_pe_esquerdo > 0:
            LogMovimentacaoV2.objects.create(
                ficha=item.ficha,
                item=item,
                operador=request.user,
                acao='adicionar',
                lado='PE',
                quantidade_movimentada=quantidade_pe_esquerdo,
                saldo_momento=quantidade_pe_esquerdo # Saldo inicial
            )

        messages.success(
            request,
            f"Item adicionado: {quantidade_pe_esquerdo} PE e {quantidade_pe_direito} PD"
        )

        return redirect("editar_ficha_inventario", ficha_id=ficha_id)

    # -------------------------
    # GET → carrega dados com FILTROS
    # -------------------------
    modelos = ModeloCalcado.objects.filter(excluido=False)

    # Todos os itens da ficha (antes de filtrar)
    itens_totais = ficha.itens.all().select_related("modelo", "cor", "tamanho")
    
    # Itens que serão filtrados
    itens = itens_totais

    # ======================
    # FILTROS (via GET)
    # ======================
    modelo_id = request.GET.get('modelo')
    cor_id = request.GET.get('cor')
    numero = request.GET.get('numero')

    if modelo_id:
        itens = itens.filter(modelo_id=modelo_id)

    if cor_id:
        itens = itens.filter(cor_id=cor_id)

    if numero:
        itens = itens.filter(tamanho__numero=numero)

    # ======================
    # STATS (sobre itens filtrados)
    # ======================
    total_itens = itens.count()
    total_pares = sum(
        min(item.quantidade_pe_direito, item.quantidade_pe_esquerdo)
        for item in itens
    )

    # ======================
    # OPÇÕES PARA OS FILTROS (baseado nos filtros já aplicados)
    # ======================
    
    # Modelos: sempre mostra os que existem na ficha
    modelos_na_ficha = ModeloCalcado.objects.filter(
        id__in=itens_totais.values_list('modelo_id', flat=True).distinct()
    ).order_by('nome')
    
    # Cores: se modelo foi selecionado, mostra apenas cores desse modelo
    if modelo_id:
        cores_na_ficha = Cor.objects.filter(
            id__in=itens_totais.filter(modelo_id=modelo_id).values_list('cor_id', flat=True).distinct()
        ).order_by('nome')
    else:
        cores_na_ficha = Cor.objects.filter(
            id__in=itens_totais.values_list('cor_id', flat=True).distinct()
        ).order_by('nome')
    
    # Números: ajusta baseado nos filtros de modelo e cor
    itens_para_numeros = itens_totais
    if modelo_id:
        itens_para_numeros = itens_para_numeros.filter(modelo_id=modelo_id)
    if cor_id:
        itens_para_numeros = itens_para_numeros.filter(cor_id=cor_id)
    
    # Pega números únicos (sem repetir)
    numeros_na_ficha = (
        itens_para_numeros
        .values_list('tamanho__numero', flat=True)
        .distinct()
        .order_by('tamanho__numero')
    )

    # ======================
    # PAGINAÇÃO
    # ======================
    paginator = Paginator(itens, 15)
    page_number = request.GET.get("page")
    itens_paginados = paginator.get_page(page_number)

    context = {
        "ficha": ficha,
        "modelos": modelos,  # Para o formulário de adicionar
        "itens": itens,      # Queryset filtrado
        "itens_paginados": itens_paginados,
        "pode_editar": pode_editar,
        
        # Filtros selecionados
        'modelo_selecionado': modelo_id,
        'cor_selecionada': cor_id,
        'numero_selecionado': numero,
        
        # Opções para os filtros
        'modelos_filtro': modelos_na_ficha,
        'cores_filtro': cores_na_ficha,
        'numeros_filtro': numeros_na_ficha,
        
        # Stats
        'total_itens': total_itens,
        'total_pares': total_pares,
    }

    return render(request, "qualidade/editar_ficha_inventario.html", context)


@login_required
def remover_item_inventario(request, item_id):
    if request.method != "POST":
        return redirect("home")

    # 1. Tenta pegar o item. Se der 404 aqui, é porque ele já foi removido (seu erro atual)
    item = get_object_or_404(ItemInventario, id=item_id)
    ficha_id = item.ficha.id

    # Permissão
    if request.user.perfil.tipo != "operador":
        messages.error(request, "Você não tem permissão para excluir itens.")
        return redirect("editar_ficha_inventario", ficha_id=ficha_id)

    # 2. Prepara a descrição ANTES de deletar
    info_item = f"{item.modelo.nome} - {item.cor.nome} (Nº {item.tamanho.numero})"
    qtd_pd = item.quantidade_pe_direito
    qtd_pe = item.quantidade_pe_esquerdo

    # 3. Cria os Logs (Eles vão sobreviver ao delete pelo SET_NULL)
    if qtd_pd > 0:
        LogMovimentacaoV2.objects.create(
            ficha=item.ficha,
            item=item,
            identificacao_item=info_item,
            operador=request.user,
            acao='subtrair',
            lado='PD',
            quantidade_movimentada=qtd_pd,
            saldo_momento=0
        )
    
    if qtd_pe > 0:
        LogMovimentacaoV2.objects.create(
            ficha=item.ficha,
            item=item,
            identificacao_item=info_item,
            operador=request.user,
            acao='subtrair',
            lado='PE',
            quantidade_movimentada=qtd_pe,
            saldo_momento=0
        )

    # 4. DELEÇÃO SEGURA: Usamos o QuerySet para evitar o erro de 'id is None'
    ItemInventario.objects.filter(id=item_id).delete()

    messages.success(request, f"Item {info_item} removido com sucesso!")
    return redirect("editar_ficha_inventario", ficha_id=ficha_id)

@login_required
def atualizar_quantidade_item(request, item_id):
    if request.method != "POST":
        return redirect("home")

    item = get_object_or_404(ItemInventario, id=item_id)

    # Permissão
    if request.user.perfil.tipo != "operador":
        messages.error(request, "Você não tem permissão para alterar quantidades.")
        return redirect("editar_ficha_inventario", ficha_id=item.ficha.id)

    acao = request.POST.get("acao")
    lado = request.POST.get("lado")
    valor = request.POST.get("valor")

    # Validação do valor
    try:
        valor = int(valor)
        if valor < 0:
            raise ValueError()
    except:
        messages.error(request, "Quantidade inválida.")
        return redirect("editar_ficha_inventario", ficha_id=item.ficha.id)

    # Seleciona o campo correto
    if lado == "PD":
        campo = "quantidade_pe_direito"
        nome_lado = "Pé Direito"
    elif lado == "PE":
        campo = "quantidade_pe_esquerdo"
        nome_lado = "Pé Esquerdo"
    else:
        messages.error(request, "Lado inválido.")
        return redirect("editar_ficha_inventario", ficha_id=item.ficha.id)

    # Pega o valor atual APENAS para validar (não usa para salvar)
    quantidade_atual = getattr(item, campo)

    if acao == "adicionar":
        # Usa F() para somar direto no banco
        if lado == "PD":
            item.quantidade_pe_direito = F('quantidade_pe_direito') + valor
        else:
            item.quantidade_pe_esquerdo = F('quantidade_pe_esquerdo') + valor
            
        mensagem = f"{valor} unidade(s) adicionada(s) ao {nome_lado}!"

    elif acao == "subtrair":
        # Verifica se a subtração vai deixar negativo ANTES de mandar pro banco
        if quantidade_atual - valor < 0:
            messages.error(request, "A quantidade não pode ficar negativa.")
            return redirect("editar_ficha_inventario", ficha_id=item.ficha.id)

        # Se passou na validação, usamos F() para subtrair
        if lado == "PD":
            item.quantidade_pe_direito = F('quantidade_pe_direito') - valor
        else:
            item.quantidade_pe_esquerdo = F('quantidade_pe_esquerdo') - valor
            
        mensagem = f"{valor} unidade(s) removida(s) do {nome_lado}!"

    else:
        messages.error(request, "Ação inválida.")
        return redirect("editar_ficha_inventario", ficha_id=item.ficha.id)

    item.save()

    # 1. Captura os filtros que vieram do formulário
    f_modelo = request.POST.get("f_modelo", "")
    f_cor = request.POST.get("f_cor", "")
    f_numero = request.POST.get("f_numero", "")

    # 2. Monta a URL de retorno com os parâmetros
    url = reverse("editar_ficha_inventario", kwargs={"ficha_id": item.ficha.id})
    
    query_params = []
    if f_modelo: query_params.append(f"modelo={f_modelo}")
    if f_cor: query_params.append(f"cor={f_cor}")
    if f_numero: query_params.append(f"numero={f_numero}")
    
    if query_params:
        url = f"{url}?{'&'.join(query_params)}"

    item.refresh_from_db() 

    LogMovimentacaoV2.objects.create(
        ficha=item.ficha,
        item=item,
        operador=request.user,
        acao=acao, # 'adicionar' ou 'subtrair'
        lado=lado, # 'PE' ou 'PD'
        quantidade_movimentada=valor,
        saldo_momento=item.quantidade_pe_esquerdo + item.quantidade_pe_direito
    )

    messages.success(request, mensagem)
    return redirect(url)


## VIEWS DE GERENCIAMENTO SÓ PRA QUALIDADE ##
@login_required
def gerenciar_modelos(request):
    """Gerenciar modelos de calçados (apenas qualidade)"""
    
    # Verificar permissão
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem gerenciar modelos.')
        return redirect('home')

    # --------------------
    # POST - Processamento de ações
    # --------------------
    if request.method == 'POST':
        acao = request.POST.get('acao')

        # 1) CRIAR NOVO MODELO
        if acao == 'adicionar_modelo':
            nome_modelo = request.POST.get('nome_modelo', '').strip()
            cores_ids = request.POST.getlist('cores')  # <<< cores do select múltiplo
            tamanhos = request.POST.getlist('tamanhos')

            # Validação
            if not nome_modelo or not cores_ids or not tamanhos:
                messages.error(request, 'Preencha nome, cores e tamanhos.')
                return redirect('gerenciar_modelos')

            # Verificar duplicação de nome
            modelo_existente = ModeloCalcado.objects.filter(nome__iexact=nome_modelo).first()

            if modelo_existente:
                if modelo_existente.excluido:
                    messages.error(
                        request,
                        f'Já existe um modelo chamado "{nome_modelo}" na lixeira. '
                        'Exclua-o permanentemente ou restaure-o.'
                    )
                else:
                    messages.error(
                        request,
                        f'O modelo "{nome_modelo}" já existe.'
                    )
                return redirect('gerenciar_modelos')

            # Criar modelo
            modelo = ModeloCalcado.objects.create(
                nome=nome_modelo,
                criado_por=request.user
            )

            # Adicionar cores selecionadas ao modelo (ManyToMany)
            modelo.cores.set(cores_ids)

            # Criar combinações (cor x tamanho)
            for numero in tamanhos:
                for cor_id in cores_ids:
                    TamanhoModelo.objects.get_or_create(
                        modelo=modelo,
                        cor_id=cor_id,
                        numero=numero
                    )

            messages.success(request, f'Modelo "{nome_modelo}" criado com sucesso!')
            return redirect('gerenciar_modelos')


        # 2) ADICIONAR COR A UM MODELO EXISTENTE (suporta nome_cor ou select cores/cores[])
        elif acao == 'adicionar_cor':
            modelo_id = request.POST.get('modelo_id')
            if not modelo_id:
                messages.error(request, 'Modelo não informado.')
                return redirect('gerenciar_modelos')

            modelo = get_object_or_404(ModeloCalcado, id=modelo_id, excluido=False)

            # 1) Caso 1: veio um campo de texto com nome_cor (adicionar uma cor por nome)
            nome_cor = request.POST.get('nome_cor', '').strip()
            # 2) Caso 2: veio um select com uma ou mais cores já existentes (ids)
            cores_ids = request.POST.getlist('cores') or request.POST.getlist('cores[]')

            # Se nem nome_cor nem cores_ids foram enviados -> erro
            if not nome_cor and not cores_ids:
                messages.error(request, 'Informe o nome da cor ou selecione uma cor.')
                return redirect('gerenciar_modelos')

            cores_para_adicionar = []

            # Se veio nome_cor: buscar (case-insensitive) ou criar
            if nome_cor:
                cor_obj = Cor.objects.filter(nome__iexact=nome_cor, excluido=False).first()
                if not cor_obj:
                    cor_obj = Cor.objects.create(nome=nome_cor, criado_por=request.user)
                cores_para_adicionar.append(cor_obj)

            # Se vieram ids: converter para objetos Cor válidos (ignorando já excluídos)
            if cores_ids:
                # filtra somente as cores válidas
                cores_qs = Cor.objects.filter(pk__in=cores_ids, excluido=False)
                # adiciona cada objeto à lista (evita duplicatas)
                for c in cores_qs:
                    if c not in cores_para_adicionar:
                        cores_para_adicionar.append(c)

            # Agora processa cada cor (adicionar ao modelo e criar tamanhos)
            if not cores_para_adicionar:
                messages.error(request, 'Nenhuma cor válida selecionada.')
                return redirect('gerenciar_modelos')

            added = []
            already = []
            for cor in cores_para_adicionar:
                if modelo.cores.filter(id=cor.id).exists():
                    already.append(cor.nome)
                    continue

                modelo.cores.add(cor)
                added.append(cor.nome)

                # Criar tamanhos existentes para a nova cor (evita duplicatas)
                tamanhos_existentes = (
                    TamanhoModelo.objects.filter(modelo=modelo, excluido=False)
                    .values_list('numero', flat=True)
                    .distinct()
                )
                for numero in tamanhos_existentes:
                    obj, created = TamanhoModelo.objects.get_or_create(
                        modelo=modelo,
                        cor=cor,
                        numero=numero,
                        defaults={"ativo": True, "excluido": False}
                    )

                    if not created and obj.excluido:
                        obj.excluido = False
                        obj.ativo = True
                        obj.save()

                    

            # Mensagens amigáveis
            if added:
                messages.success(request, f'Cores adicionadas ao modelo: {", ".join(added)}.')
            if already:
                messages.warning(request, f'Já estavam vinculadas: {", ".join(already)}.')

            return redirect('gerenciar_modelos')



        # 3) ADICIONAR TAMANHOS A UM MODELO EXISTENTE
        elif acao == 'adicionar_tamanho':
            modelo_id = request.POST.get('modelo_id')

            if not modelo_id:
                messages.error(request, "Modelo não informado.")
                return redirect('gerenciar_modelos')

            modelo = get_object_or_404(ModeloCalcado, id=modelo_id, excluido=False)

            # lista de tamanhos enviados pelos checkboxes
            tamanhos_sel = request.POST.getlist('tamanhos[]') or request.POST.getlist('tamanhos')

            if not tamanhos_sel:
                messages.error(request, "Selecione ao menos um tamanho.")
                return redirect('gerenciar_modelos')

            # converter para int (evita erros e garante ordenação)
            tamanhos_limpos = []
            for t in tamanhos_sel:
                try:
                    tamanhos_limpos.append(int(t))
                except ValueError:
                    pass  # ignora qualquer coisa inválida

            if not tamanhos_limpos:
                messages.error(request, "Nenhum tamanho válido enviado.")
                return redirect('gerenciar_modelos')

            tamanhos_limpos = sorted(set(tamanhos_limpos))  # remove duplicatas e ordena

            # todas as cores vinculadas ao modelo
            cores = modelo.cores.filter(excluido=False)

            if not cores.exists():
                messages.error(request, "O modelo não possui cores. Adicione cores antes de adicionar tamanhos.")
                return redirect('gerenciar_modelos')

            adicionados = []
            ja_existiam = []

            # gerar combinações (cor × tamanho)
            for numero in tamanhos_limpos:
                for cor in cores:
                    obj, created = TamanhoModelo.objects.get_or_create(
                        modelo=modelo,
                        cor=cor,
                        numero=numero
                    )
                    if created:
                        adicionados.append(f"{numero} ({cor.nome})")
                    else:
                        ja_existiam.append(f"{numero} ({cor.nome})")

            # mensagens
            if adicionados:
                messages.success(
                    request,
                    'Tamanhos adicionados.'
                )

            if ja_existiam:
                messages.warning(
                    request,
                    "Já existiam: " + ", ".join(ja_existiam)
                )

            return redirect('gerenciar_modelos')



        # 4) MOVER MODELO PARA LIXEIRA
        elif acao == 'mover_lixeira':
            modelo_id = request.POST.get('modelo_id')
            
            try:
                with transaction.atomic():
                    modelo = ModeloCalcado.objects.get(id=modelo_id, excluido=False)
                    modelo.excluido = True
                    modelo.excluido_em = timezone.now()
                    modelo.excluido_por = request.user
                    modelo.save()

                    modelo.tamanhos.update(
                        excluido=True,
                        ativo=False
                    )
                messages.success(request, f'Modelo "{modelo.nome}" movido para a lixeira!')
            except ModeloCalcado.DoesNotExist:
                messages.error(request, 'Modelo não encontrado.')
            
            return redirect('gerenciar_modelos')

    # --------------------
    # GET - Exibir página
    # --------------------

    # Buscar modelos ativos
    modelos = (
        ModeloCalcado.objects.filter(excluido=False)
        .prefetch_related('cores', 'tamanhos')
        .order_by('nome')
    )
    # Verificar duplicação de nome (incluindo excluídos)
    cores_disponiveis = Cor.objects.filter(excluido=False, ativo=True).order_by('nome')

    # Definir faixas de tamanhos
    tamanhos_infantil_completo = list(range(26, 37))  # 26 até 36
    tamanhos_adulto_completo = list(range(34, 46))    # 34 até 45

    # Processar cada modelo para calcular tamanhos disponíveis
    for modelo in modelos:
        # Contar tamanhos distintos
        modelo.tamanho_count = (
            modelo.tamanhos.filter(excluido=False)
            .values('numero')
            .distinct()
            .count()
        )
        
        # Pegar tamanhos que o modelo JÁ possui
        tamanhos_existentes = set(
            modelo.tamanhos.filter(excluido=False)
            .values_list('numero', flat=True)
            .distinct()
        )
        
        # Calcular tamanhos disponíveis para adicionar (que NÃO existem ainda)
        modelo.tamanhos_infantil_disponiveis = [
            str(t) for t in tamanhos_infantil_completo 
            if str(t) not in tamanhos_existentes
        ]
        modelo.tamanhos_unicos = (
            modelo.tamanhos.filter(excluido=False)
            .values_list('numero', flat=True)
            .distinct()
            .order_by('numero')
        )
        modelo.tamanhos_adulto_disponiveis = [
            str(t) for t in tamanhos_adulto_completo 
            if str(t) not in tamanhos_existentes
        ]

    context = {
        'modelos': modelos,
        'cores': cores_disponiveis,
        'tamanhos_infantil': tamanhos_infantil_completo,
        'tamanhos_adulto': tamanhos_adulto_completo,
    }
    
    return render(request, 'qualidade/gerenciar_modelos.html', context)



@login_required
def visualizar_ficha_inventario(request, ficha_id):
    ficha = get_object_or_404(FichaInventario, id=ficha_id)

    # Todos os itens da ficha (antes de filtrar)
    itens_totais = ficha.itens.all().select_related('modelo', 'cor', 'tamanho')
    
    # Itens que serão filtrados
    itens = itens_totais

    # ======================
    # FILTROS (via GET)
    # ======================
    modelo_id = request.GET.get('modelo')
    cor_id = request.GET.get('cor')
    numero = request.GET.get('numero')  # Mudei de tamanho_id para numero

    if modelo_id:
        itens = itens.filter(modelo_id=modelo_id)

    if cor_id:
        itens = itens.filter(cor_id=cor_id)

    if numero:
        itens = itens.filter(tamanho__numero=numero)

    # ======================
    # STATS (sobre itens filtrados)
    # ======================
    
    # Adicionamos atributos extras em cada item para usar no template
    for item in itens:
        # O par é sempre o menor valor entre os dois
        item.pares = min(item.quantidade_pe_esquerdo, item.quantidade_pe_direito)
        
        # A sobra é a diferença
        item.sobra_esquerda = item.quantidade_pe_esquerdo - item.pares
        item.sobra_direita = item.quantidade_pe_direito - item.pares

    # O total geral de pares da ficha toda (filtrada)
    total_pares = sum(item.pares for item in itens)

    modelos_diferentes = itens.values("modelo__nome").distinct().count()

    # ======================
    # PAGINAÇÃO
    # ======================
    paginator = Paginator(itens, 15)
    page_number = request.GET.get('page')
    itens_paginados = paginator.get_page(page_number)

    # ======================
    # OPÇÕES PARA OS FILTROS (baseado nos filtros já aplicados)
    # ======================
    
    # Modelos: sempre mostra os que existem na ficha (sem filtro aplicado ainda)
    modelos_na_ficha = ModeloCalcado.objects.filter(
        id__in=itens_totais.values_list('modelo_id', flat=True).distinct()
    ).order_by('nome')
    
    # Cores: se modelo foi selecionado, mostra apenas cores desse modelo
    if modelo_id:
        cores_na_ficha = Cor.objects.filter(
            id__in=itens_totais.filter(modelo_id=modelo_id).values_list('cor_id', flat=True).distinct()
        ).order_by('nome')
    else:
        cores_na_ficha = Cor.objects.filter(
            id__in=itens_totais.values_list('cor_id', flat=True).distinct()
        ).order_by('nome')
    
    # Números: ajusta baseado nos filtros de modelo e cor
    itens_para_numeros = itens_totais
    if modelo_id:
        itens_para_numeros = itens_para_numeros.filter(modelo_id=modelo_id)
    if cor_id:
        itens_para_numeros = itens_para_numeros.filter(cor_id=cor_id)
    
    # Pega números únicos (sem repetir)
    numeros_na_ficha = (
        itens_para_numeros
        .values_list('tamanho__numero', flat=True)
        .distinct()
        .order_by('tamanho__numero')
    )

    context = {
        'ficha': ficha,
        'itens': itens,  # queryset filtrado
        'itens_paginados': itens_paginados,

        # filtros selecionados
        'modelo_selecionado': modelo_id,
        'cor_selecionada': cor_id,
        'numero_selecionado': numero,

        # dados para os selects
        'modelos': modelos_na_ficha,
        'cores': cores_na_ficha,
        'numeros': numeros_na_ficha,

        'total_pares': total_pares,
        'modelos_diferentes': modelos_diferentes,
    }

    return render(request, 'qualidade/visualizar_ficha_inventario.html', context)

@login_required
def lixeira_modelos(request):
    """Lixeira dos modelos de calçado (apenas qualidade)."""

    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira.')
        return redirect('home')

    if request.method == 'POST':
        acao = request.POST.get('acao')
        modelo_id = request.POST.get('modelo_id')

        # 1) Restaurar da lixeira
        if acao == 'restaurar':
            try:
                with transaction.atomic():
                    modelo = ModeloCalcado.objects.get(id=modelo_id, excluido=True)

                    modelo.excluido = False
                    modelo.excluido_em = None
                    modelo.excluido_por = None
                    modelo.save()

                    modelo.tamanhos.update(
                        excluido=False,
                        ativo=True
                    )
                    messages.success(request, f'Modelo "{modelo.nome}" restaurado com sucesso!')
            except ModeloCalcado.DoesNotExist:
                messages.error(request, 'Modelo não encontrado na lixeira.')

        # 2) Excluir permanentemente
        elif acao == 'excluir_permanente':
            try:
                modelo = ModeloCalcado.objects.get(id=modelo_id, excluido=True)
                nome_modelo = modelo.nome
                modelo.delete()
                messages.success(request, f'Modelo "{nome_modelo}" excluído permanentemente!')
            except ModeloCalcado.DoesNotExist:
                messages.error(request, 'Modelo não encontrado na lixeira.')

        return redirect('lixeira_modelos')

    # Listar somente excluídos
    modelos_excluidos = ModeloCalcado.objects.filter(excluido=True).order_by('-criado_em')

    context = {
        'modelos': modelos_excluidos,
    }
    return render(request, 'qualidade/lixeira_modelos.html', context)

@login_required
def gerenciar_cores(request):
    """Gerenciar cores do calçado (apenas qualidade)"""
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
                if Cor.objects.filter(nome__iexact=nome).exists():
                    messages.error(request, f'A cor "{nome}" já existe')
                else:
                    # Pegar a maior ordem atual e adicionar 1
                    max_ordem = Cor.objects.all().aggregate(models.Max('ordem'))['ordem__max'] or 0
                    Cor.objects.create(nome=nome, ordem=max_ordem + 1)
                    messages.success(request, f'Cor "{nome}" criada com sucesso!')
            else:
                messages.error(request, 'Digite o nome da cor')
        
        elif acao == 'mover_lixeira':
            cor_id = request.POST.get('cor_id')
            try:
                cor = Cor.objects.get(id=cor_id, excluido=False)
                cor.excluido = True
                cor.excluido_em = timezone.now()
                cor.save()
                messages.success(request, f'Cor "{cor.nome}" movida para a lixeira!')
            except Cor.DoesNotExist:
                messages.error(request, 'Cor não encontrada')
        
        elif acao == 'ativar_desativar':
            cor_id = request.POST.get('cor_id')
            try:
                cor = Cor.objects.get(id=cor_id, excluido=False)
                cor.ativo = not cor.ativo
                cor.save()
                status = 'ativada' if cor.ativo else 'desativada'
                messages.success(request, f'Cor "{cor.nome}" {status}!')
            except Cor.DoesNotExist:
                messages.error(request, 'Cor não encontrada')
        
        return redirect('gerenciar_cores')
    
    # Listar apenas partes NÃO EXCLUÍDAS
    cores = Cor.objects.filter(excluido=False).order_by('ordem', 'nome')
    
    context = {
        'cores': cores,
    }
    return render(request, 'qualidade/gerenciar_cores.html', context)   

@login_required
def lixeira_cores(request):
    """Lixeira de nomes de cores (apenas qualidade)"""
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem acessar a lixeira')
        return redirect('home')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        cor_id = request.POST.get('cor_id')
        
        if acao == 'restaurar':
            try:
                cor = Cor.objects.get(id=cor_id, excluido=True)
                cor.excluido = False
                cor.excluido_em = None
                cor.save()
                messages.success(request, f'Registro de cor "{cor.nome}" restaurada com sucesso!')
            except Cor.DoesNotExist:
                messages.error(request, 'Nome da cor não encontrada na lixeira')
        
        elif acao == 'excluir_permanente':
            try:
                cor = Cor.objects.get(id=cor_id, excluido=True)
                nome_cor = cor.nome
                cor.delete()
                messages.success(request, f'Registro de cor "{nome_cor}" excluído permanentemente!')
            except Cor.DoesNotExist:
                messages.error(request, 'Nome de cor não encontrada na lixeira')
        
        return redirect('lixeira_cores')
    
    # Listar apenas partes EXCLUÍDAS
    cores_excluidas = Cor.objects.filter(excluido=True).order_by('-excluido_em')
    
    context = {
        'cores': cores_excluidas,
    }
    return render(request, 'qualidade/lixeira_cores.html', context) 

@login_required
def excluir_ficha_inventario(request, ficha_id):
    if request.user.perfil.tipo != 'qualidade':
        messages.error(request, 'Apenas usuários da qualidade podem excluir fichas')
        return redirect('home')

    if request.method == 'POST':
        ficha = get_object_or_404(FichaInventario, id=ficha_id)

        if ficha.excluido:
            messages.warning(request, 'Esta ficha de inventário já está na lixeira')
            return redirect('home')

        ficha.excluido = True
        ficha.excluido_em = timezone.now()
        ficha.excluido_por = request.user
        ficha.save()

        messages.success(
            request,
            f'Ficha de inventário "{ficha.nome_ficha}" movida para a lixeira!'
        )

    return redirect('home')
