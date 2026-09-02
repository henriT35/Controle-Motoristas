from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from apps.clients.models import Client
from apps.operations.models import CTe, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from .importer import import_ssw_delivery_file

HEADERS = [
    '1','ROMANEIO','DATA EMISSAO','HORA EMISSAO','SITUACAO','PLACA','PLACA CARRETA','MOTORISTA','CPF DO MOTORISTA','SEGURADORA','AUTORIZACAO','VALIDADE','CTRC','TIPO DE FRETE','NOME REMETENTE','NOME DESTINATARIO','CNPJ PAGADOR','NOME PAGADOR','CIDADE PAGADOR','CIDADE_ENTREGA','CEP ENTREGA','LOCAL DE ENTREGA','BAIRRO','SETOR DEST','COD OCORR ROM','DESC OCORR ROM','DATA OCORR ROM','HORA OCORR ROM','COD OCORR CTRC','DESC OCORR CTRC','DATA OCORR CTRC','HORA OCORR CTRC','FRETE CTRC ORIGEM','FRETE CTRC','PESO CALCULO','QTDE VOL','VLR MERC','COD MERC','SERIE NF','NUMERO NF','NRO_PEDIDO','CONFERENTE','AJUDANTE','AJUDANTE_2','AJUDANTE_3','EMITIDO POR','PREV ENTREGA CTRC'
]


def make_row(
    ctrc='GRU000100-1',
    manifest='BEL999999-1',
    emission='10/08/2026',
    situation='BAIXADO',
    cte_code='1',
    cte_desc='ENTREGUE',
    cte_date='10/08/2026',
    cte_time='12:00',
    rom_code='34',
    rom_desc='MERCADORIA EM CONFERENCIA NO CLIENTE',
    rom_date='10/08/2026',
    rom_time='11:00',
    destination='CLIENTE TESTE',
    payer='CLIENTE TESTE',
    payer_cnpj='12.345.678/0001-90',
    driver='MOTORISTA TESTE',
    cpf='12345678901',
):
    values = {h: '' for h in HEADERS}
    values.update({
        '1':'2','ROMANEIO':manifest,'DATA EMISSAO':emission,'HORA EMISSAO':'10:00:00','SITUACAO':situation,
        'PLACA':'ABC1D23','MOTORISTA':driver,'CPF DO MOTORISTA':cpf,'CTRC':ctrc,'TIPO DE FRETE':'FOB A PRAZO',
        'NOME REMETENTE':'REMETENTE TESTE','NOME DESTINATARIO':destination,'CNPJ PAGADOR':payer_cnpj,'NOME PAGADOR':payer,
        'CIDADE PAGADOR':'BELEM/PA','CIDADE_ENTREGA':'BELEM/PA','CEP ENTREGA':'66000000','LOCAL DE ENTREGA':'AV TESTE, 100','BAIRRO':'MARCO',
        'COD OCORR ROM':rom_code,'DESC OCORR ROM':rom_desc,'DATA OCORR ROM':rom_date,'HORA OCORR ROM':rom_time,
        'COD OCORR CTRC':cte_code,'DESC OCORR CTRC':cte_desc,'DATA OCORR CTRC':cte_date,'HORA OCORR CTRC':cte_time,
        'FRETE CTRC':'100,50','PESO CALCULO':'200,000','QTDE VOL':'2','VLR MERC':'1000,00','SERIE NF':'001','NUMERO NF':'12345','PREV ENTREGA CTRC':cte_date or emission
    })
    return ';'.join(values[h] for h in HEADERS)


def write_file(path, rows, period='01/08/26 A 31/08/26'):
    content = f'0;RELACAO DE ROMANEIOS E CTRCS DE ENTREGA NO PERIODO: {period};EMPRESA TESTE\n'
    content += ';'.join(HEADERS) + '\n' + '\n'.join(rows) + '\n'
    Path(path).write_text(content, encoding='latin-1')


class ImporterTests(TestCase):
    def test_reimport_is_idempotent_and_rom34_ctrc_delivered_auto_recovers(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'teste.sswweb'
            write_file(path, [make_row()])
            _run1, stats1 = import_ssw_delivery_file(path)
            self.assertEqual(CTe.objects.count(), 1)
            self.assertEqual(RetainedProof.objects.count(), 1)
            self.assertEqual(stats1.new, 1)
            proof = RetainedProof.objects.get()
            self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)
            self.assertEqual(proof.recovered_at.date().isoformat(), '2026-08-10')
            self.assertEqual(proof.client.cnpj, '12.345.678/0001-90')
            self.assertIsNotNone(CTe.objects.get().delivered_at)

            _run2, stats2 = import_ssw_delivery_file(path)
            self.assertEqual(CTe.objects.count(), 1)
            self.assertEqual(RetainedProof.objects.count(), 1)
            self.assertEqual(stats2.new, 0)
            proof.refresh_from_db()
            self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)

    def test_rom_occurrence_identity_is_scoped_to_attempt_and_ctrc_is_consolidated(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'multi_attempt.sswweb'
            rows = [
                make_row(
                    ctrc='MULTI-ATT', manifest='BEL-ATT-A', emission='10/08/2026',
                    rom_code='85', rom_desc='SAIDA PARA ENTREGA', rom_date='11/08/2026', rom_time='08:00',
                    cte_code='34', cte_desc='MERCADORIA EM CONFERENCIA NO CLIENTE', cte_date='11/08/2026', cte_time='12:00',
                ),
                make_row(
                    ctrc='MULTI-ATT', manifest='BEL-ATT-B', emission='11/08/2026',
                    rom_code='85', rom_desc='SAIDA PARA ENTREGA', rom_date='11/08/2026', rom_time='08:00',
                    cte_code='34', cte_desc='MERCADORIA EM CONFERENCIA NO CLIENTE', cte_date='11/08/2026', cte_time='12:00',
                ),
            ]
            write_file(path, rows)
            import_ssw_delivery_file(path)
            cte = CTe.objects.get(ctrc='MULTI-ATT')
            rom = DeliveryOccurrence.objects.filter(cte=cte, source='SSW_ROMANEIO', code='85')
            self.assertEqual(rom.count(), 2)
            self.assertEqual(len(set(rom.values_list('movement__manifest_id', flat=True))), 2)
            ctrc = DeliveryOccurrence.objects.filter(cte=cte, source='SSW_CTRC', code='34')
            self.assertEqual(ctrc.count(), 1)
            self.assertIsNone(ctrc.get().movement_id)

    def test_ctrc34_keeps_retention_open(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'retida.sswweb'
            write_file(path, [make_row(
                ctrc='RET-ATIVA',
                cte_code='34', cte_desc='MERCADORIA EM CONFERENCIA NO CLIENTE',
                cte_date='10/08/2026', cte_time='12:00',
                rom_code='34', rom_desc='MERCADORIA EM CONFERENCIA NO CLIENTE',
                rom_date='10/08/2026', rom_time='11:00',
            )])
            import_ssw_delivery_file(path)
            proof = RetainedProof.objects.get(cte__ctrc='RET-ATIVA')
            self.assertEqual(proof.status, RetainedProof.Status.WAITING)
            self.assertIsNone(proof.recovered_at)

    def test_rom34_without_date_uses_historical_manifest_not_import_time(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'retida-historica.sswweb'
            write_file(path, [make_row(
                ctrc='RET-HIST', manifest='BEL-HIST', emission='02/04/2026',
                rom_code='34', rom_desc='MERCADORIA EM CONFERENCIA NO CLIENTE',
                rom_date='', rom_time='',
                cte_code='1', cte_desc='ENTREGUE', cte_date='20/05/2026', cte_time='17:00',
            )], period='01/04/26 A 30/04/26')
            import_ssw_delivery_file(path)
            proof = RetainedProof.objects.get(cte__ctrc='RET-HIST')
            self.assertEqual(proof.retained_at.date().isoformat(), '2026-04-02')
            self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)
            self.assertEqual(proof.recovered_at.date().isoformat(), '2026-05-20')

    def test_out_of_order_import_does_not_regress_cte_current_status(self):
        """Um arquivo antigo importado depois não pode apagar uma ocorrência mais nova."""
        with TemporaryDirectory() as tmp:
            newer = Path(tmp) / 'newer.sswweb'
            older = Path(tmp) / 'older.sswweb'
            write_file(newer, [make_row(
                ctrc='CTE-ORDEM', manifest='BEL-NEW', emission='12/08/2026',
                situation='BAIXADO', cte_code='1', cte_desc='ENTREGUE', cte_date='12/08/2026',
                rom_code='85', rom_desc='SAIDA PARA ENTREGA', rom_date='12/08/2026'
            )])
            write_file(older, [make_row(
                ctrc='CTE-ORDEM', manifest='BEL-OLD', emission='10/08/2026',
                situation='PENDENTE', cte_code='85', cte_desc='SAIDA PARA ENTREGA', cte_date='10/08/2026',
                rom_code='', rom_desc='', rom_date=''
            )])
            import_ssw_delivery_file(newer)
            import_ssw_delivery_file(older)
            cte = CTe.objects.get(ctrc='CTE-ORDEM')
            self.assertEqual(cte.current_status, 'ENTREGUE')
            self.assertEqual(DeliveryOccurrence.objects.filter(cte=cte, description='ENTREGUE').count(), 1)

    def test_cte_current_status_prefers_ctrc_over_rom(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rom-vs-ctrc.sswweb'
            write_file(path, [make_row(
                ctrc='STATUS-1', emission='10/08/2026',
                rom_code='34', rom_desc='MERCADORIA EM CONFERENCIA NO CLIENTE',
                rom_date='10/08/2026', rom_time='18:00',
                cte_code='1', cte_desc='ENTREGUE', cte_date='10/08/2026', cte_time='17:00',
            )])
            import_ssw_delivery_file(path)
            self.assertEqual(CTe.objects.get(ctrc='STATUS-1').current_status, 'ENTREGUE')

    def test_same_cnpj_with_name_punctuation_variation_does_not_duplicate_client(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'clients.sswweb'
            rows = [
                make_row(ctrc='CLI-1', destination='ATACADAO S A', payer='ATACADAO S A', payer_cnpj='83.456.789/0001-10'),
                make_row(ctrc='CLI-2', manifest='BEL999998-1', destination='ATACADAO S.A.', payer='ATACADAO S.A.', payer_cnpj='83.456.789/0001-10'),
            ]
            write_file(path, rows)
            import_ssw_delivery_file(path)
            self.assertEqual(Client.objects.filter(cnpj='83.456.789/0001-10').count(), 1)

    def test_blank_cnpj_name_punctuation_variation_does_not_duplicate_client(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'clients_blank.sswweb'
            rows = [
                make_row(ctrc='CLIB-1', destination='ATACADAO S A', payer='OUTRO', payer_cnpj=''),
                make_row(ctrc='CLIB-2', manifest='BEL999997-1', destination='ATACADAO S.A.', payer='OUTRO', payer_cnpj=''),
            ]
            write_file(path, rows)
            import_ssw_delivery_file(path)
            self.assertEqual(Client.objects.filter(cnpj='').count(), 1)

    def test_older_retention_imported_later_backfills_origin_date(self):
        with TemporaryDirectory() as tmp:
            newer = Path(tmp) / 'ret_new.sswweb'
            older = Path(tmp) / 'ret_old.sswweb'
            write_file(newer, [make_row(
                ctrc='RET-1', manifest='BEL-RET-NEW', emission='15/08/2026',
                cte_code='34', cte_desc='MERCADORIA EM CONFERENCIA NO CLIENTE', cte_date='15/08/2026',
                rom_code='', rom_desc='', rom_date=''
            )])
            write_file(older, [make_row(
                ctrc='RET-1', manifest='BEL-RET-OLD', emission='10/08/2026',
                cte_code='34', cte_desc='MERCADORIA EM CONFERENCIA NO CLIENTE', cte_date='10/08/2026',
                rom_code='', rom_desc='', rom_date=''
            )])
            import_ssw_delivery_file(newer)
            import_ssw_delivery_file(older)
            proof = RetainedProof.objects.get(cte__ctrc='RET-1')
            self.assertEqual(proof.retained_at.date().isoformat(), '2026-08-10')
            self.assertEqual(proof.original_manifest.number, 'BEL-RET-OLD')

    def test_manifest_status_does_not_regress_from_baixado_to_pendente(self):
        with TemporaryDirectory() as tmp:
            newer = Path(tmp) / 'manifest_new.sswweb'
            older = Path(tmp) / 'manifest_old.sswweb'
            write_file(newer, [make_row(ctrc='M-1', manifest='BEL-M-1', situation='BAIXADO')])
            write_file(older, [make_row(ctrc='M-1', manifest='BEL-M-1', situation='PENDENTE')])
            import_ssw_delivery_file(newer)
            import_ssw_delivery_file(older)
            self.assertEqual(Manifest.objects.get(number='BEL-M-1').status, 'BAIXADO')

class ImportProgressViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(username="importador", password="Teste@123")
        self.client.force_login(self.user)

    def test_progress_endpoint_exposes_running_manual_import(self):
        from datetime import date
        from django.urls import reverse
        from django.utils import timezone
        from .models import ImportRun, ImportStep

        run = ImportRun.objects.create(
            kind=ImportRun.Kind.MANUAL,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status=ImportRun.Status.RUNNING,
            started_at=timezone.now(),
            source_file="agosto.sswweb",
            requested_by=self.user,
        )
        ImportStep.objects.create(
            run=run, name="Normalização e comparação", status="RUNNING",
            occurred_at=timezone.now(), message="Processando dados do SSW."
        )
        response = self.client.get(reverse("ssw_import_progress"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["active"])
        self.assertEqual(payload["run"]["id"], run.pk)
        self.assertEqual(payload["run"]["step"], "Normalização e comparação")

class RobotBridgeTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(username="robotuser", password="Teste@123")

    def test_task_contract_uses_option_036_bel_and_excel_s(self):
        from datetime import date
        from django.test import override_settings
        from .models import ImportRun
        from .robot_bridge import build_robot_task

        run = ImportRun.objects.create(
            kind=ImportRun.Kind.FAST,
            start_date=date(2026, 8, 16),
            end_date=date(2026, 8, 31),
            requested_by=self.user,
        )
        with TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp), SSW_ROBOT_UNIT="BEL", SSW_ROBOT_OPTION="036", SSW_ROBOT_EXCEL="S"):
            task, task_path, result_path = build_robot_task(run)
            self.assertEqual(task["unit"], "BEL")
            self.assertEqual(task["ssw_option"], "036")
            self.assertEqual(task["excel"], "S")
            self.assertEqual(task["start_date"], "2026-08-16")
            self.assertEqual(task["end_date"], "2026-08-31")
            self.assertTrue(task_path.exists())
            self.assertEqual(task["result_file"], str(result_path))

    def test_robot_import_reuses_original_import_run(self):
        from datetime import date
        from .models import ImportRun

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "robot.sswweb"
            write_file(path, [make_row(ctrc="ROBOT-1")])
            run = ImportRun.objects.create(
                kind=ImportRun.Kind.FAST,
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 31),
                status=ImportRun.Status.RUNNING,
                requested_by=self.user,
            )
            imported_run, stats = import_ssw_delivery_file(
                path,
                kind=run.kind,
                requested_by=self.user,
                existing_run=run,
                source_label="Robô SSW",
            )
            self.assertEqual(imported_run.pk, run.pk)
            self.assertEqual(ImportRun.objects.count(), 1)
            self.assertEqual(stats.new, 1)
            imported_run.refresh_from_db()
            self.assertIn(imported_run.status, {ImportRun.Status.SUCCESS, ImportRun.Status.WARNING})


class OrphanReconciliationTests(TestCase):
    """Regressões do BUG-001: nenhum ImportRun pode ficar ativo para sempre."""

    def test_dispatched_run_without_executor_times_out_and_is_finalized(self):
        from datetime import date, timedelta
        from django.test import override_settings
        from django.utils import timezone

        from .diagnostics import queue_pause_state, reconcile_orphan_runs
        from .models import ImportRun, ImportStep

        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            run = ImportRun.objects.create(
                kind=ImportRun.Kind.FAST,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 1),
                status=ImportRun.Status.DISPATCHED,
            )
            ImportStep.objects.create(
                run=run,
                name="Despacho",
                status="SUCCESS",
                occurred_at=timezone.now() - timedelta(seconds=20),
                message="Watchdog solicitado, mas executor não respondeu.",
            )

            with override_settings(
                SSW_ROBOT_DISPATCH_TIMEOUT_SECONDS=5,
                SSW_ROBOT_ORPHAN_GRACE_SECONDS=1,
            ):
                recovered = reconcile_orphan_runs(base_dir)

            run.refresh_from_db()
            self.assertIn(run.pk, recovered)
            self.assertEqual(run.status, ImportRun.Status.ERROR)
            self.assertIsNotNone(run.finished_at)
            self.assertIn("ROBOT_DISPATCH_TIMEOUT", run.message)
            self.assertTrue(queue_pause_state(base_dir).get("paused"))

    def test_running_job_with_dead_worker_pid_is_finalized(self):
        from datetime import date, timedelta
        from django.test import override_settings
        from django.utils import timezone

        from .diagnostics import (
            queue_pause_state,
            reconcile_orphan_runs,
            resolve_execution_dir,
            write_worker_state,
        )
        from .models import ImportRun
        from .robot_bridge import execution_id_for

        with TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            run = ImportRun.objects.create(
                kind=ImportRun.Kind.FAST,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 1),
                status=ImportRun.Status.RUNNING,
                started_at=timezone.now() - timedelta(minutes=5),
            )
            run_dir = resolve_execution_dir(base_dir, execution_id_for(run))
            run_dir.mkdir(parents=True, exist_ok=True)
            old_heartbeat = (timezone.now() - timedelta(minutes=2)).isoformat()
            write_worker_state(
                run_dir,
                status="RUNNING",
                stage="SSW",
                watchdog_pid=99999999,
                child_pid=99999998,
                last_heartbeat_at=old_heartbeat,
            )

            with override_settings(
                SSW_ROBOT_HEARTBEAT_SECONDS=1,
                SSW_ROBOT_HEARTBEAT_LOST_SECONDS=4,
                SSW_ROBOT_ORPHAN_GRACE_SECONDS=1,
            ):
                recovered = reconcile_orphan_runs(base_dir, grace_seconds=1)

            run.refresh_from_db()
            self.assertIn(run.pk, recovered)
            self.assertEqual(run.status, ImportRun.Status.ERROR)
            self.assertIn("WORKER_PROCESS_LOST", run.message)
            self.assertTrue(queue_pause_state(base_dir).get("paused"))
