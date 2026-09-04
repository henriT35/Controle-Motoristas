from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import random
import shutil
import threading

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client
from apps.drivers.models import Driver
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from apps.ssw.import_lock import ImportBusyError, SSWImportLock
from apps.ssw.importer import import_ssw_delivery_file
from apps.ssw.models import ImportRun
from apps.ssw.services import month_chunks, queue_import
from apps.ssw.tests import HEADERS, make_row, write_file


class ImportIdempotencyExtremeTests(TestCase):
    def test_same_file_ten_times_does_not_multiply_business_entities(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.sswweb"
            write_file(path, [make_row(ctrc="TEN-1", manifest="TEN-M-1")])
            first_counts = None
            for idx in range(10):
                _run, stats = import_ssw_delivery_file(path)
                counts = (
                    CTe.objects.count(), Driver.objects.count(), Client.objects.count(),
                    Manifest.objects.count(), DeliveryMovement.objects.count(),
                    DeliveryOccurrence.objects.count(), RetainedProof.objects.count(),
                )
                if idx == 0:
                    first_counts = counts
                    self.assertEqual(stats.new, 1)
                else:
                    self.assertEqual(stats.new, 0)
                    self.assertEqual(counts, first_counts)
            self.assertEqual(ImportRun.objects.count(), 10)

    def test_same_content_renamed_does_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "relatorio.sswweb"
            renamed = Path(tmp) / "copia_123.sswweb"
            write_file(original, [make_row(ctrc="REN-1", manifest="REN-M-1")])
            shutil.copy2(original, renamed)
            import_ssw_delivery_file(original)
            before = (CTe.objects.count(), DeliveryOccurrence.objects.count(), RetainedProof.objects.count())
            import_ssw_delivery_file(renamed)
            self.assertEqual(
                (CTe.objects.count(), DeliveryOccurrence.objects.count(), RetainedProof.objects.count()),
                before,
            )

    def test_shuffled_rows_do_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "ordered.sswweb"
            shuffled = Path(tmp) / "shuffled.sswweb"
            rows = [
                make_row(ctrc=f"ORD-{i}", manifest=f"ORD-M-{i}", payer_cnpj=f"12.345.678/0001-{10+i:02d}")
                for i in range(1, 5)
            ]
            write_file(original, rows)
            shuffled_rows = list(rows)
            random.Random(123).shuffle(shuffled_rows)
            write_file(shuffled, shuffled_rows)
            import_ssw_delivery_file(original)
            before = (CTe.objects.count(), Manifest.objects.count(), DeliveryMovement.objects.count(), DeliveryOccurrence.objects.count())
            import_ssw_delivery_file(shuffled)
            self.assertEqual((CTe.objects.count(), Manifest.objects.count(), DeliveryMovement.objects.count(), DeliveryOccurrence.objects.count()), before)

    def test_duplicate_rows_inside_one_file_are_collapsed_by_business_keys(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "dups.sswweb"
            row = make_row(ctrc="DUP-1", manifest="DUP-M-1")
            write_file(path, [row, row, row, row, row])
            import_ssw_delivery_file(path)
            self.assertEqual(CTe.objects.filter(ctrc="DUP-1").count(), 1)
            self.assertEqual(Manifest.objects.filter(number="DUP-M-1").count(), 1)
            self.assertEqual(DeliveryMovement.objects.filter(cte__ctrc="DUP-1").count(), 1)
            self.assertEqual(RetainedProof.objects.filter(cte__ctrc="DUP-1").count(), 1)
            # A linha traz 2 ocorrências diferentes (ROM/CTRC), não cinco cópias de cada.
            self.assertEqual(DeliveryOccurrence.objects.filter(cte__ctrc="DUP-1").count(), 2)

    def test_occurrence_identity_ignores_cosmetic_description_variation(self):
        with TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.sswweb"
            b = Path(tmp) / "b.sswweb"
            write_file(a, [make_row(ctrc="OCC-1", manifest="OCC-M-1", rom_code="", rom_desc="", rom_date="", cte_desc="ENTREGUE")])
            write_file(b, [make_row(ctrc="OCC-1", manifest="OCC-M-1", rom_code="", rom_desc="", rom_date="", cte_desc="  Entregue!!!  ")])
            import_ssw_delivery_file(a)
            import_ssw_delivery_file(b)
            self.assertEqual(DeliveryOccurrence.objects.filter(cte__ctrc="OCC-1").count(), 1)

    def test_manual_recovery_survives_reimport(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ret.sswweb"
            write_file(path, [make_row(ctrc="REC-1", manifest="REC-M-1")])
            import_ssw_delivery_file(path)
            proof = RetainedProof.objects.get(cte__ctrc="REC-1")
            recovery_driver = Driver.objects.create(name="RECUPERADOR", cpf="99999999999")
            proof.status = RetainedProof.Status.RECOVERED
            proof.recovery_driver = recovery_driver
            proof.recovered_at = timezone.now()
            proof.note = "RECUPERADO QA"
            proof.save(update_fields=["status", "recovery_driver", "recovered_at", "note"])
            import_ssw_delivery_file(path)
            proof.refresh_from_db()
            self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)
            self.assertEqual(proof.recovery_driver, recovery_driver)
            self.assertEqual(proof.note, "RECUPERADO QA")
            self.assertIsNotNone(proof.recovered_at)

    def test_same_cnpj_with_completely_changed_name_reuses_client(self):
        with TemporaryDirectory() as tmp:
            a = Path(tmp) / "client-a.sswweb"
            b = Path(tmp) / "client-b.sswweb"
            cnpj = "83.456.789/0001-10"
            write_file(a, [make_row(ctrc="CN-1", manifest="CN-M-1", destination="EMPRESA ABC LTDA", payer="EMPRESA ABC LTDA", payer_cnpj=cnpj)])
            write_file(b, [make_row(ctrc="CN-2", manifest="CN-M-2", destination="EMPRESA ABC TRANSPORTES LTDA", payer="EMPRESA ABC TRANSPORTES LTDA", payer_cnpj=cnpj)])
            import_ssw_delivery_file(a)
            import_ssw_delivery_file(b)
            self.assertEqual(Client.objects.filter(cnpj=cnpj).count(), 1)

    def test_invalid_numeric_row_is_traceable_and_not_silently_zeroed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-number.sswweb"
            good = make_row(ctrc="VAL-GOOD", manifest="VAL-M-GOOD")
            values = {h: "" for h in HEADERS}
            bad_parts = make_row(ctrc="VAL-BAD", manifest="VAL-M-BAD").split(";")
            values = dict(zip(HEADERS, bad_parts))
            values["FRETE CTRC"] = "VALOR-INVALIDO"
            bad = ";".join(values[h] for h in HEADERS)
            write_file(path, [good, bad])
            run, stats = import_ssw_delivery_file(path)
            self.assertEqual(stats.errors, 1)
            self.assertEqual(stats.ignored, 1)
            self.assertTrue(CTe.objects.filter(ctrc="VAL-GOOD").exists())
            self.assertFalse(CTe.objects.filter(ctrc="VAL-BAD").exists())
            self.assertEqual(run.status, ImportRun.Status.WARNING)
            self.assertTrue(run.steps.filter(name="Validação de linhas", status="WARNING").exists())


class OrchestrationExtremeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="qa-orchestrator", password="x")

    @override_settings(SSW_ROBOT_ENABLED=False)
    def test_duplicate_active_period_reuses_same_import_run(self):
        a = queue_import(date(2026, 8, 1), date(2026, 8, 31), kind=ImportRun.Kind.HISTORY, requested_by=self.user)
        b = queue_import(date(2026, 8, 1), date(2026, 8, 31), kind=ImportRun.Kind.HISTORY, requested_by=self.user)
        self.assertEqual(a, b)
        self.assertEqual(ImportRun.objects.count(), 1)

    @override_settings(SSW_ROBOT_ENABLED=False)
    def test_year_to_august_is_split_without_gap_and_each_window_max_31_days(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("ssw_imports"), {
            "start_date": "2026-01-01", "end_date": "2026-08-31", "kind": "HISTORY"
        })
        self.assertEqual(response.status_code, 302)
        runs = list(ImportRun.objects.order_by("start_date"))
        self.assertEqual(len(runs), 8)
        self.assertEqual(runs[0].start_date, date(2026, 1, 1))
        self.assertEqual(runs[-1].end_date, date(2026, 8, 31))
        for prev, current in zip(runs, runs[1:]):
            self.assertEqual(prev.end_date.toordinal() + 1, current.start_date.toordinal())
        for run in runs:
            self.assertLessEqual((run.end_date - run.start_date).days + 1, 31)

    def test_invalid_empty_ssw_upload_creates_error_history_instead_of_traceback(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile("empty.sswweb", b"", content_type="text/plain")
        response = self.client.post(reverse("ssw_imports"), {"ssw_files": upload})
        self.assertEqual(response.status_code, 302)
        run = ImportRun.objects.order_by("-created_at").first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, ImportRun.Status.ERROR)
        self.assertEqual(run.error_count, 1)


class PeriodChunkPureTests(SimpleTestCase):
    def test_leap_year_february(self):
        chunks = list(month_chunks(date(2024, 2, 1), date(2024, 3, 3)))
        self.assertEqual(chunks, [
            (date(2024, 2, 1), date(2024, 2, 29)),
            (date(2024, 3, 1), date(2024, 3, 3)),
        ])

    def test_reverse_dates_are_normalized(self):
        chunks = list(month_chunks(date(2026, 8, 31), date(2026, 8, 1)))
        self.assertEqual(chunks, [(date(2026, 8, 1), date(2026, 8, 31))])


class ImportLockTests(SimpleTestCase):
    def test_second_process_context_cannot_acquire_same_lock_while_first_holds_it(self):
        with TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp)):
            first = SSWImportLock(timeout=0.2)
            first.acquire()
            errors = []

            def contender():
                try:
                    SSWImportLock(timeout=0.15, poll_interval=0.05).acquire()
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=contender)
            thread.start()
            thread.join(timeout=2)
            first.release()
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ImportBusyError)
