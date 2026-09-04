from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.core.models import SystemSettings
from apps.drivers.models import Driver
from apps.operations.models import CTe, Manifest
from .models import ProofRecoverySubmission, RetainedProof


class RecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("admin2", email="a@b.c", password="x")
        self.driver = Driver.objects.create(name="Motorista", cpf="22222222222")
        self.client_obj = Client.objects.create(name="Cliente")
        self.addr = ClientAddress.objects.create(
            client=self.client_obj, street="Rua", district="Marco", city="Belem",
            normalized_address="RUA MARCO"
        )
        retention_day = timezone.localdate() - timedelta(days=20)
        self.manifest = Manifest.objects.create(number="R002", date=retention_day, driver=self.driver)
        self.cte = CTe.objects.create(ctrc="CTE2", client=self.client_obj)
        self.proof = RetainedProof.objects.create(
            cte=self.cte, client=self.client_obj, address=self.addr,
            original_driver=self.driver, original_manifest=self.manifest,
            retained_at=timezone.make_aware(datetime.combine(retention_day, datetime.min.time()).replace(hour=10)),
        )
        self.client.force_login(self.user)
        settings = SystemSettings.load()
        settings.critical_days = 15
        settings.save(update_fields=["critical_days"])

    def test_manual_recovery_persists(self):
        recovery_day = timezone.localdate() - timedelta(days=1)
        response = self.client.post(
            reverse("proof_recover", args=[self.proof.pk]),
            {"recovery_driver": self.driver.pk, "recovered_at": recovery_day.isoformat(), "note": "OK"},
        )
        self.assertEqual(response.status_code, 302)
        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, RetainedProof.Status.RECOVERED)
        self.assertEqual(self.proof.recovery_driver, self.driver)
        self.assertEqual(self.proof.confirmed_by, self.user)
        self.assertEqual(self.proof.note, "OK")

    def test_recovery_before_retention_is_rejected(self):
        invalid_day = self.proof.retained_at.date() - timedelta(days=1)
        self.client.post(
            reverse("proof_recover", args=[self.proof.pk]),
            {"recovery_driver": self.driver.pk, "recovered_at": invalid_day.isoformat()},
        )
        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, RetainedProof.Status.WAITING)
        self.assertIsNone(self.proof.recovered_at)

    def test_future_recovery_is_rejected(self):
        future_day = timezone.localdate() + timedelta(days=1)
        self.client.post(
            reverse("proof_recover", args=[self.proof.pk]),
            {"recovery_driver": self.driver.pk, "recovered_at": future_day.isoformat()},
        )
        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, RetainedProof.Status.WAITING)
        self.assertIsNone(self.proof.recovered_at)

    def test_critical_rule_is_strictly_greater_than_configured_days(self):
        today = timezone.localdate()
        self.proof.retained_at = timezone.make_aware(
            datetime.combine(today - timedelta(days=15), datetime.min.time()).replace(hour=10)
        )
        self.proof.save(update_fields=["retained_at"])
        self.assertFalse(self.proof.is_critical)
        self.proof.retained_at = timezone.make_aware(
            datetime.combine(today - timedelta(days=16), datetime.min.time()).replace(hour=10)
        )
        self.proof.save(update_fields=["retained_at"])
        self.assertTrue(self.proof.is_critical)

    def test_canceled_proof_cannot_be_recovered_directly(self):
        self.proof.status = RetainedProof.Status.CANCELED
        self.proof.save(update_fields=["status"])
        response = self.client.post(
            reverse("proof_recover", args=[self.proof.pk]),
            {"recovery_driver": self.driver.pk, "recovered_at": timezone.localdate().isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, RetainedProof.Status.CANCELED)
        self.assertIsNone(self.proof.recovered_at)



class ProofFilterTests(RecoveryTests):
    def test_evidence_filter_yes_and_no_are_complements(self):
        second_cte = CTe.objects.create(ctrc="CTE3", client=self.client_obj)
        second = RetainedProof.objects.create(
            cte=second_cte, client=self.client_obj, address=self.addr,
            original_driver=self.driver, original_manifest=self.manifest,
            retained_at=self.proof.retained_at,
        )
        ProofRecoverySubmission.objects.create(
            proof=self.proof, driver=self.driver, recovered_at=timezone.now(),
            evidence="proof_recovery/teste.jpg",
        )
        yes = self.client.get(reverse("proofs"), {"evidence": "yes"})
        no = self.client.get(reverse("proofs"), {"evidence": "no"})
        yes_ids = {p.pk for p in yes.context["page_obj"].object_list}
        no_ids = {p.pk for p in no.context["page_obj"].object_list}
        self.assertIn(self.proof.pk, yes_ids)
        self.assertNotIn(second.pk, yes_ids)
        self.assertIn(second.pk, no_ids)
        self.assertNotIn(self.proof.pk, no_ids)


class RetainedProofCurrentStateV092Tests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista Estado SSW", cpf="77777777777")
        self.client_obj = Client.objects.create(name="Cliente Estado SSW")
        self.addr = ClientAddress.objects.create(
            client=self.client_obj, street="Rua Estado", district="Centro", city="Belem",
            normalized_address="RUA ESTADO CENTRO BELEM",
        )
        self.day = timezone.localdate() - timedelta(days=30)
        self.manifest = Manifest.objects.create(number="ROM-STATE-1", date=self.day, driver=self.driver)

    def _proof(self, ctrc, current_status, retained_hour=12):
        cte = CTe.objects.create(ctrc=ctrc, client=self.client_obj, current_status=current_status)
        retained_at = timezone.make_aware(datetime.combine(self.day, datetime.min.time()).replace(hour=retained_hour))
        return RetainedProof.objects.create(
            cte=cte, client=self.client_obj, address=self.addr, original_driver=self.driver,
            original_manifest=self.manifest, retained_at=retained_at, status=RetainedProof.Status.WAITING,
        )

    def test_bnu046259_regression_current_delivered_resolves_even_if_retention_time_was_inferred(self):
        from .services import reconcile_retained_proofs
        proof = self._proof("BNU046259-4", "ENTREGUE", retained_hour=12)
        result = reconcile_retained_proofs(apply=True)
        proof.refresh_from_db()
        self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)
        self.assertEqual(proof.resolution_source, "SSW")
        self.assertIsNone(proof.recovery_driver)
        self.assertGreaterEqual(result.get("resolved_ssw", 0), 1)

    def test_cwb055520_regression_rom34_origin_plus_current_delivered_resolves_without_bonus_driver(self):
        from .services import reconcile_retained_proofs
        proof = self._proof("CWB055520-7", "ENTREGUE")
        reconcile_retained_proofs(apply=True)
        proof.refresh_from_db()
        self.assertEqual(proof.status, RetainedProof.Status.RECOVERED)
        self.assertIsNone(proof.recovery_driver_id)
        self.assertIsNone(proof.confirmed_by_id)

    def test_ambiguous_current_status_tracks_automatically_instead_of_staying_actionable(self):
        from .services import reconcile_retained_proofs
        for code in ("60 - DOCUMENTOS", "53 - AVARIA", "91 - INDENIZACAO"):
            proof = self._proof("CTE-" + code[:2], code)
        reconcile_retained_proofs(apply=True)
        self.assertEqual(
            RetainedProof.objects.filter(status=RetainedProof.Status.TRACKING).count(), 3
        )
        self.assertFalse(RetainedProof.objects.filter(status=RetainedProof.Status.TRACKING, recovery_driver__isnull=False).exists())
