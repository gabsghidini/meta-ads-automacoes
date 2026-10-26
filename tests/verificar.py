"""Testes com dados ficticios, sem Meta ou WhatsApp. Use --render para PNG."""
import contextlib
import datetime
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('relatorio-diario', 'relatorio-semanal', 'saldo')

if len(sys.argv) < 2 or sys.argv[1] not in FOLDERS:
    failed = False
    for folder in FOLDERS:
        print(f'\n{folder}', flush=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('META_', 'EVOLUTION_', 'WHATSAPP_', 'RELATORIO_'))}
        result = subprocess.run([sys.executable, __file__, folder] + (['--render'] if '--render' in sys.argv else []), env=env)
        failed = failed or result.returncode != 0
    sys.exit(1 if failed else 0)

FOLDER = sys.argv[1]
RENDER = '--render' in sys.argv
sys.path.insert(0, str(ROOT / FOLDER))
check = importlib.import_module('check')


class AutomacaoTests(unittest.TestCase):
    def setUp(self):
        network = patch('urllib.request.urlopen', side_effect=AssertionError('Rede bloqueada nos testes'))
        network.start()
        self.addCleanup(network.stop)

    def test_configuracao_limpa(self):
        self.assertFalse(check.TOKEN)
        self.assertFalse(check.cfg.get('WHATSAPP_INSTANCE'))
        self.assertEqual(check.resolve_recipient('', '', ''), [])

    def test_env_local_e_aspas(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / '.env'
            file.write_text('# exemplo\nCHAVE="valor ficticio"\nVAZIO=\n')
            self.assertEqual(check.parse_env_file(file), {'CHAVE': 'valor ficticio', 'VAZIO': ''})

    def test_descoberta_deduplica_e_ignora(self):
        def paginate(node, params=None):
            if node == 'me/adaccounts':
                return [{'id': 'act_111', 'name': 'Conta ficticia', 'currency': 'BRL'}, {'id': '111'}, {'id': 'act_222'}]
            return []
        with patch.object(check, 'paginate', side_effect=paginate), patch.object(check, 'BUSINESS_ID', 'demo'), patch.object(check, 'IGNORE', {'222'}):
            accounts, source = check.discover_accounts()
        self.assertEqual([a['id'] for a in accounts], ['111'])

    @unittest.skipIf(FOLDER == 'saldo', 'apenas relatorios')
    def test_coleta_e_render_com_dados_ficticios(self):
        meta = importlib.import_module('meta')
        render = importlib.import_module('render')
        today = datetime.date(2026, 10, 23)
        rows = []
        for i in range(1, 15):
            rows.append({'campaign_id': 'demo', 'campaign_name': 'Campanha ficticia', 'objective': 'OUTCOME_LEADS', 'date_start': (today - datetime.timedelta(days=i)).isoformat(), 'spend': '20', 'impressions': '1000', 'clicks': '40', 'actions': [{'action_type': 'onsite_conversion.lead_grouped', 'value': '4'}]})
        contas = [{'id': '111', 'name': 'Cliente <Exemplo>', 'currency': 'BRL'}]
        with patch.object(meta, 'contas', return_value=(contas, 'teste')), patch.object(meta, 'insights', return_value=rows), patch.object(meta, 'metas_de_otimizacao', return_value={'demo': ('LEAD_GENERATION', None, None)}):
            if FOLDER == 'relatorio-diario':
                data = meta.coleta(hoje=today)
                self.assertEqual(data['contas'][0]['ontem']['resultado'], 4)
                renderer = render.renderiza
            else:
                weekly = importlib.import_module('semanal')
                data = weekly.coleta_semanal(hoje=today)
                self.assertEqual(data['contas'][0]['atual']['resultado'], 28)
                self.assertEqual(data['contas'][0]['delta_custo'], 0)
                renderer = weekly.renderiza_semanal
        with tempfile.TemporaryDirectory() as temp:
            with contextlib.ExitStack() as stack:
                if not RENDER:
                    stack.enter_context(patch.object(render, '_screenshots'))
                pages, ctx = renderer(data, pasta=temp)
            self.assertEqual(len(pages), 2)
            for page in pages:
                html = Path(page['png']).with_suffix('.html').read_text()
                self.assertIn('Cliente &lt;Exemplo&gt;', html)
                self.assertNotIn('{{', html)
                if RENDER:
                    self.assertEqual(Path(page['png']).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    @unittest.skipIf(FOLDER == 'saldo', 'apenas relatorios')
    def test_dry_run_falhando_nao_envia_alerta(self):
        entry = importlib.import_module('main' if FOLDER == 'relatorio-diario' else 'semanal')
        whatsapp = importlib.import_module('whatsapp')
        meta = importlib.import_module('meta')
        target = patch.object(meta, 'coleta', side_effect=RuntimeError('falha ficticia')) if FOLDER == 'relatorio-diario' else patch.object(entry, 'coleta_semanal', side_effect=RuntimeError('falha ficticia'))
        with patch.object(check, 'TOKEN', 'token-ficticio'), patch.object(sys, 'argv', ['script', '--dry-run']), patch.object(entry.time, 'sleep'), target, patch.object(whatsapp, 'avisa_falha') as alert, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(entry.main(), 1)
            alert.assert_not_called()

    @unittest.skipIf(FOLDER == 'saldo', 'apenas relatorios')
    def test_envio_exige_configuracao(self):
        whatsapp = importlib.import_module('whatsapp')
        with self.assertRaises(RuntimeError):
            whatsapp.envia_relatorio([])

    @unittest.skipUnless(FOLDER == 'saldo', 'apenas saldo')
    def test_limites_saldo(self):
        base = {'error': None, 'currency': 'BRL', 'funding': 'prepago', 'status': 1, 'balance': 0}
        self.assertEqual(check.tier({**base, 'avail': 0}), 'urgente')
        self.assertEqual(check.tier({**base, 'avail': 1000}), 'atencao')
        self.assertEqual(check.tier({**base, 'avail': 5000}), 'ok')
        self.assertEqual(check.tier({**base, 'error': 'sem acesso'}), 'urgente')

    @unittest.skipUnless(FOLDER == 'saldo', 'apenas saldo')
    def test_saldo_salva_sem_whatsapp(self):
        def graph(node, params=None):
            if node == 'me':
                return {'id': 'demo', 'name': 'Usuario ficticio'}
            return {'account_status': 1, 'balance': '5000', 'amount_spent': '10000', 'currency': 'BRL', 'funding_source_details': {'type': '20', 'display_string': 'Saldo disponivel (R$ 50,00)'}}
        with tempfile.TemporaryDirectory() as temp, patch.object(check, 'DIR', temp), patch.object(check, 'TOKEN', 'token-ficticio'), patch.object(check, 'NO_WHATSAPP', True), patch.object(check, 'AS_JSON', True), patch.object(check, 'graph', side_effect=graph), patch.object(check, 'token_days_left', return_value=None), patch.object(check, 'discover_accounts', return_value=([{'id': '111', 'name': 'Conta ficticia', 'currency': 'BRL'}], 'teste')), patch.object(check, 'send_whatsapp') as send, contextlib.redirect_stdout(io.StringIO()) as output:
            check.main()
            result = json.loads(output.getvalue())
            self.assertEqual(result['summary']['ok'], 1)
            self.assertEqual(result['accounts'][0]['balance'], 50)
            self.assertIn('Conta ficticia', (Path(temp) / 'reports/report.md').read_text())
            send.assert_not_called()


unittest.main(argv=[sys.argv[0]], verbosity=2)
