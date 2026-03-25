from django.db import models
from django.contrib.auth.models import User


class NomeOperador(models.Model):
    """Modelo para os nomes dos operadores"""
    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)  # Para ordenar a exibição
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='operadores_excluidos')

    class Meta:
        verbose_name = 'Nome do Operador'
        verbose_name_plural = 'Nomes dos Operadores'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class ParteCalcado(models.Model):
    """Modelo para as partes do calçado (Língua, Sola, Reforço, etc)"""
    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)  # Para ordenar a exibição
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='partes_excluidas')

    class Meta:
        verbose_name = 'Parte do Calçado'
        verbose_name_plural = 'Partes do Calçado'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class Ficha(models.Model):
    """Modelo para a ficha de produção"""
    PERFIL_CHOICES = [
        ('operador', 'Operador'),
        ('qualidade', 'Qualidade'),
    ]

    setor = models.CharField(max_length=25, blank=True, null=True, verbose_name="setor")
    operador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichas')
    data = models.DateField()
    nome_ficha = models.CharField(max_length=200)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='fichas_excluidas')

    class Meta:
        verbose_name = 'Ficha'
        verbose_name_plural = 'Fichas'
        ordering = ['-data', '-criada_em']

    def __str__(self):
        return f"{self.nome_ficha} - {self.data} - {self.operador.username}"
    
    def save(self, *args, **kwargs):
    # Preenche o setor automaticamente com o nome do grupo do usuário
        if not self.setor and self.operador:
            grupo = self.operador.groups.first()
            print(f"DEBUG - Operador: {self.operador.username}")
            print(f"DEBUG - Grupo encontrado: {grupo.name if grupo else 'Nenhum'}")
            self.setor = grupo.name if grupo else None
        super().save(*args, **kwargs)

    def excluir(self, usuario):
        """Marca a ficha como excluída e registra quem excluiu"""
        from django.utils import timezone
        self.excluido = True
        self.excluido_em = timezone.now()
        self.excluido_por = usuario
        self.save()
    @property
    def tipo_ficha(self):
        """Retorna o tipo da ficha"""
        return 'Ficha'



class RegistroParte(models.Model):
    """Modelo para registrar as quantidades de cada parte na ficha"""
    ficha = models.ForeignKey(Ficha, on_delete=models.CASCADE, related_name='registros')
    parte = models.ForeignKey(ParteCalcado, on_delete=models.CASCADE)
    quantidades = models.JSONField(default=list)  # Lista de quantidades [12, 32, 22, 65, 16]

    class Meta:
        verbose_name = 'Registro de Parte'
        verbose_name_plural = 'Registros de Partes'
        unique_together = ['ficha', 'parte']

    def __str__(self):
        return f"{self.ficha.nome_ficha} - {self.parte.nome}"

    def total(self):
        """Retorna o total das quantidades"""
        return sum(self.quantidades) if self.quantidades else 0

    def adicionar_quantidade(self, quantidade):
        """Adiciona uma nova quantidade à lista"""
        if not self.quantidades:
            self.quantidades = []
        self.quantidades.append(quantidade)
        self.save()


class PerfilUsuario(models.Model):
    """Extensão do modelo User para adicionar perfil"""
    TIPO_PERFIL = [
        ('operador', 'Operador'),
        ('qualidade', 'Qualidade'),
        ('loja', 'Loja'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo = models.CharField(max_length=20, choices=TIPO_PERFIL, default='operador')

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f"{self.user.username} - {self.get_tipo_display()}"
    

## ---MODELS DO INVENTÁRIO DA INJETORA--- ##

class Cor(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cores_criadas')
    excluido_por = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='cores_excluidas')

    def __str__(self):
        return self.nome

class ModeloCalcado(models.Model):
    """Modelo de calçado para inventário"""
    nome = models.CharField(max_length=100,unique=True, verbose_name="Nome do Modelo")
    ativo = models.BooleanField(default=True)
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='modelos_criados')
    excluido_por = models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='modelos_excluidas')
    cores = models.ManyToManyField(Cor, related_name='modelos')
    
    class Meta:
        verbose_name = 'Modelo de Calçado'
        verbose_name_plural = 'Modelos de Calçado'
        ordering = ['nome']
    
    def __str__(self):
        return self.nome

class TamanhoModelo(models.Model):
    """Tamanhos disponíveis para cada modelo e cor"""
    modelo = models.ForeignKey(ModeloCalcado, on_delete=models.CASCADE, related_name='tamanhos')
    cor = models.ForeignKey(Cor, on_delete=models.CASCADE, related_name='tamanhos')
    numero = models.CharField(max_length=10, verbose_name="Número/Tamanho")
    ativo = models.BooleanField(default=True)
    excluido = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Tamanho do Modelo'
        verbose_name_plural = 'Tamanhos dos Modelos'
        ordering = ['numero']
        unique_together = ['modelo', 'cor', 'numero']
    
    def __str__(self):
        return f"{self.modelo.nome} - {self.cor.nome} - {self.numero}"


class FichaInventario(models.Model):
    """Ficha de inventário para setor INJETORA"""
    operador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichas_inventario')
    data = models.DateField()
    nome_ficha = models.CharField(max_length=200)
    setor = models.CharField(max_length=50, default='Injetora')
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='fichas_inventario_excluidas')
    
    class Meta:
        verbose_name = 'Ficha de Inventário'
        verbose_name_plural = 'Fichas de Inventário'
        ordering = ['-data', '-criada_em']
    
    def __str__(self):
        return f"{self.nome_ficha} - {self.data} - {self.operador.username}"
    
    def save(self, *args, **kwargs):
        if not self.setor and self.operador:
            grupo = self.operador.groups.first()
            self.setor = grupo.name if grupo else 'Injetora'
        super().save(*args, **kwargs)

    def model_name(self):
        return self._meta.model_name
    @property
    def tipo_ficha(self):
        """Retorna o tipo da ficha"""
        return 'Inventario'


class ItemInventario(models.Model):
    """Item individual do inventário"""
    ficha = models.ForeignKey(FichaInventario, on_delete=models.CASCADE, related_name='itens')
    modelo = models.ForeignKey(ModeloCalcado, on_delete=models.CASCADE)
    cor = models.ForeignKey(Cor, on_delete=models.CASCADE)
    tamanho = models.ForeignKey(TamanhoModelo, on_delete=models.CASCADE)
    quantidade_pe_direito = models.IntegerField(default=0, verbose_name="Quantidade Pé Direito")
    quantidade_pe_esquerdo = models.IntegerField(default=0, verbose_name="Quantidade Pé Esquerdo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Item de Inventário'
        verbose_name_plural = 'Itens de Inventário'
        ordering = ['modelo__nome', 'cor__nome', 'tamanho__numero']
        unique_together = ['ficha', 'modelo', 'cor', 'tamanho']
    
    def __str__(self):
        return f"{self.modelo.nome} - {self.cor.nome} - Nº{self.tamanho.numero} - {self.quantidade} pares"
    
    @property
    def total_pares(self):
        """Retorna a quantidade de pares formados (o mínimo entre os dois lados)"""
        return min(self.quantidade_pe_direito, self.quantidade_pe_esquerdo)

    @property
    def total_pes(self):
        """Retorna o total de pés individuais (caso precise para inventário bruto)"""
        return self.quantidade_pe_direito + self.quantidade_pe_esquerdo
    
    @property
    def pes_avulsos(self):
        """Retorna a diferença (sobra) de pés entre os lados"""
        return abs(self.quantidade_pe_direito - self.quantidade_pe_esquerdo)

    @property
    def tem_sobra(self):
        """Verifica se existe desfalque de pares"""
        return self.quantidade_pe_direito != self.quantidade_pe_esquerdo
    @property
    def lado_sobrando(self):
        """Identifica qual pé está em maior quantidade"""
        if self.quantidade_pe_direito > self.quantidade_pe_esquerdo:
            return "Direito"
        elif self.quantidade_pe_esquerdo > self.quantidade_pe_direito:
            return "Esquerdo"
        return None
    

class LogMovimentacaoV2(models.Model):
    ACOES = (('adicionar', 'Adicionado'), ('subtrair', 'Removido'))
    LADOS = (('PD', 'Pé Direito'), ('PE', 'Pé Esquerdo'))

    item = models.ForeignKey(ItemInventario, on_delete=models.SET_NULL, null=True, related_name='logs')
    ficha = models.ForeignKey(FichaInventario, on_delete=models.CASCADE, related_name='movimentacoes', null=True)
    
    identificacao_item = models.CharField(max_length=255, blank=True, null=True)

    operador = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    acao = models.CharField(max_length=10, choices=ACOES)
    lado = models.CharField(max_length=2, choices=LADOS)
    quantidade_movimentada = models.IntegerField()
    saldo_momento = models.IntegerField(help_text="Saldo total do item após a ação")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']   