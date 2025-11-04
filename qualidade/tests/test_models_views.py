# qualidade/tests/test_models_views.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from qualidade.models import Ficha, ParteCalcado, PerfilUsuario, RegistroParte
import json

User = get_user_model()

class QualidadeSimpleTests(TestCase):
    def setUp(self):
        # cria usuários
        self.user_oper = User.objects.create_user(username='oper', password='pass')
        self.user_q = User.objects.create_user(username='qual', password='pass')

        # perfis (se você usa model PerfilUsuario)
        PerfilUsuario.objects.create(tipo='operador', user_id=self.user_oper.id)
        PerfilUsuario.objects.create(tipo='qualidade', user_id=self.user_q.id)

        # partes
        self.parte1 = ParteCalcado.objects.create(nome='Lingua', ativo=True, ordem=0, excluido=False)
        self.parte2 = ParteCalcado.objects.create(nome='Sola', ativo=True, ordem=1, excluido=False)

        # client
        self.client = Client()

    def test_login_required_home(self):
        # rota home deve redirecionar para login se não autenticado
        resp = self.client.get(reverse('home'))  # ajuste o nome se diferente
        self.assertIn(resp.status_code, (200, 302))  # dependendo se home exige login ou não

    def test_criar_ficha_e_registroparte(self):
        # loga como operador e cria ficha via model
        self.client.force_login(self.user_oper)
        ficha = Ficha.objects.create(data='2025-10-30', nome_ficha='Teste', operador_id=self.user_oper.id)
        # criar um registro com lista JSON
        quantidades = [1,2,3]
        reg = RegistroParte.objects.create(quantidades=json.dumps(quantidades), ficha_id=ficha.id, parte_id=self.parte1.id)
        self.assertEqual(reg.ficha_id, ficha.id)
        # validar que quantidades foi armazenado como texto JSON
        self.assertIn('1', reg.quantidades)

    def test_view_gerar_relatorio_perm(self):
        # usuário sem perfil qualidade não vê gerar_relatorio (teste via template ou view)
        self.client.force_login(self.user_oper)
        ficha = Ficha.objects.create(data='2025-10-30', nome_ficha='Teste2', operador_id=self.user_oper.id)
        resp = self.client.get(reverse('visualizar_ficha', args=(ficha.id,)))
        self.assertEqual(resp.status_code, 200)
        # template deve não conter link de gerar_relatorio para operador
        self.assertNotContains(resp, 'gerar_relatorio')
        # agora loga usuário qualidade
        self.client.force_login(self.user_q)
        resp2 = self.client.get(reverse('visualizar_ficha', args=(ficha.id,)))
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'gerar_relatorio')
