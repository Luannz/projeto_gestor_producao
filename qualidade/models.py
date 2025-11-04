from django.db import models
from django.contrib.auth.models import User


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

    operador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichas')
    data = models.DateField()
    nome_ficha = models.CharField(max_length=200)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    excluido = models.BooleanField(default=False)
    excluido_em = models.DateTimeField(null=True, blank=True)
    excluido_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fichas_excluidas'
    )

    class Meta:
        verbose_name = 'Ficha'
        verbose_name_plural = 'Fichas'
        ordering = ['-data', '-criada_em']

    def __str__(self):
        return f"{self.nome_ficha} - {self.data} - {self.operador.username}"

    def excluir(self, usuario):
        """Marca a ficha como excluída e registra quem excluiu"""
        from django.utils import timezone
        self.excluido = True
        self.excluido_em = timezone.now()
        self.excluido_por = usuario
        self.save()



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
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    tipo = models.CharField(max_length=20, choices=TIPO_PERFIL, default='operador')

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f"{self.user.username} - {self.get_tipo_display()}"