from datetime import datetime, timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import ProofRecoverySubmission, RetainedProof
from .models import Driver, DriverPortalAccess, Vehicle


class DriverPortalSecurityTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.driver = Driver.objects.create(name="Motorista Portal", cpf="44444444444")
        self.other_driver = Driver.objects.create(name="Outro Motorista", cpf="55555555555")
        self.vehicle = Vehicle.objects.create(plate="POR1A23")
        self.client_obj = Client.objects.create(name="Cliente Portal", cnpj="PORTAL")
        self.address = ClientAddress.objects.create(
            client=self.client_obj,
            street="Rua Portal 10",
            district="Marco",
            city="Belem",
            state="PA",
            postal_code="66000000",
            normalized_address="RUA PORTAL 10 MARCO BELEM PA",
        )
        self.manifest = Manifest.objects.create(
            number="ROM-PORTAL",
            date=self.today,
            driver=self.driver,
            vehicle=self.vehicle,
            status="PENDENTE",
        )
        self.route_cte = CTe.objects.create(ctrc="CTE-ROTA", client=self.client_obj)
        self.movement = DeliveryMovement.objects.create(
            cte=self.route_cte,
            manifest=self.manifest,
            driver=self.driver,
            vehicle=self.vehicle,
            client=self.client_obj,
            address=self.address,
            movement_date=self.today,
            status="PENDENTE",
        )
        DeliveryOccurrence.objects.create(
            cte=self.route_cte,
            movement=self.movement,
            code="85",
            description="SAIDA PARA ENTREGA",
            occurred_at=timezone.now(),
            source="SSW_ROMANEIO",
        )
        self.access = DriverPortalAccess.objects.create(driver=self.driver)

    def _proof(self, ctrc="CTE-PROOF", *, client=None, address=None, origin=None):
        client = client or self.client_obj
        address = address or self.address
        origin = origin or self.other_driver
        cte = CTe.objects.create(ctrc=ctrc, client=client)
        return RetainedProof.objects.create(
            cte=cte,
            client=client,
            address=address,
            original_driver=origin,
            retained_at=timezone.now(),
            status=RetainedProof.Status.WAITING,
        )

    def test_valid_token_opens_only_its_driver_portal_and_revoked_token_fails(self):
        response = self.client.get(reverse("driver_portal", args=[self.access.token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["driver"], self.driver)

        self.access.active = False
        self.access.save(update_fields=["active"])
        response = self.client.get(reverse("driver_portal", args=[self.access.token]))
        self.assertEqual(response.status_code, 404)

    def test_driver_can_submit_only_proof_that_is_an_opportunity_on_own_route(self):
        proof = self._proof()
        evidence = SimpleUploadedFile("comprovante.jpg", b"fake-jpeg-content", content_type="image/jpeg")
        response = self.client.post(
            reverse("driver_portal_submit_proof", args=[self.access.token, proof.pk]),
            {"note": "Resgatado na rota", "evidence": evidence},
        )
        self.assertEqual(response.status_code, 302)
        proof.refresh_from_db()
        self.assertEqual(proof.status, RetainedProof.Status.AWAITING_VALIDATION)
        submission = ProofRecoverySubmission.objects.get(proof=proof)
        self.assertEqual(submission.driver, self.driver)
        self.assertEqual(submission.source, ProofRecoverySubmission.Source.DRIVER_PORTAL)
        self.assertEqual(submission.status, ProofRecoverySubmission.Status.PENDING)

        unrelated_client = Client.objects.create(name="Cliente Distante", cnpj="DISTANTE")
        unrelated_address = ClientAddress.objects.create(
            client=unrelated_client,
            street="Outra Rua",
            district="Outro Bairro",
            city="Ananindeua",
            state="PA",
            normalized_address="OUTRA RUA OUTRO BAIRRO ANANINDEUA PA",
        )
        unrelated = self._proof("CTE-UNRELATED", client=unrelated_client, address=unrelated_address)
        evidence2 = SimpleUploadedFile("outro.jpg", b"fake", content_type="image/jpeg")
        denied = self.client.post(
            reverse("driver_portal_submit_proof", args=[self.access.token, unrelated.pk]),
            {"evidence": evidence2},
        )
        self.assertEqual(denied.status_code, 404)
        self.assertFalse(ProofRecoverySubmission.objects.filter(proof=unrelated).exists())

    def test_portal_renders_separate_camera_and_file_inputs(self):
        self._proof("CTE-CAMERA-UI")
        response = self.client.get(reverse("driver_portal", args=[self.access.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="evidence_camera"')
        self.assertContains(response, 'capture="environment"')
        self.assertContains(response, 'accept="image/*"')
        self.assertContains(response, 'name="evidence_file"')
        self.assertContains(response, 'accept="image/*,application/pdf"')

    def test_driver_camera_upload_is_accepted_as_evidence(self):
        proof = self._proof("CTE-CAMERA-UPLOAD")
        evidence = SimpleUploadedFile("foto_camera.jpg", b"fake-camera-jpeg", content_type="image/jpeg")
        response = self.client.post(
            reverse("driver_portal_submit_proof", args=[self.access.token, proof.pk]),
            {"note": "Foto tirada no celular", "evidence_camera": evidence},
        )
        self.assertEqual(response.status_code, 302)
        proof.refresh_from_db()
        self.assertEqual(proof.status, RetainedProof.Status.AWAITING_VALIDATION)
        submission = ProofRecoverySubmission.objects.get(proof=proof)
        self.assertEqual(submission.driver, self.driver)
        self.assertTrue(bool(submission.evidence))

class DriverAnalyticsEligibilityTests(TestCase):
    def test_test_driver_flag_is_persisted(self):
        driver = Driver.objects.create(name="Motorista Fictício", cpf="00000000000", is_test=True)
        self.assertTrue(driver.is_test)


class DriverEvaluationV3Tests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.proofs.models import ProofPickupOpportunity
        self.ProofPickupOpportunity = ProofPickupOpportunity
        self.reviewer = get_user_model().objects.create_superuser("coord-v3", email="coord@local", password="x")
        self.driver = Driver.objects.create(name="Motorista V3", cpf="66666666666")
        self.vehicle = Vehicle.objects.create(plate="V3A1B23")
        self.client_obj = Client.objects.create(name="Cliente V3", cnpj="V3")
        self.address = ClientAddress.objects.create(
            client=self.client_obj, street="Rua V3", district="Centro", city="Belem", state="PA",
            normalized_address="RUA V3 CENTRO BELEM PA",
        )
        self.today = timezone.localdate()

    def _movement(self, suffix="1", day=None):
        day = day or self.today
        manifest = Manifest.objects.create(number=f"ROM-V3-{suffix}", date=day, driver=self.driver, vehicle=self.vehicle)
        cte = CTe.objects.create(ctrc=f"CTE-V3-{suffix}", client=self.client_obj)
        movement = DeliveryMovement.objects.create(
            cte=cte, manifest=manifest, driver=self.driver, vehicle=self.vehicle,
            client=self.client_obj, address=self.address, movement_date=day,
        )
        return manifest, cte, movement

    def test_rom13_is_pending_until_coordinator_decides_and_same_attempt_is_idempotent(self):
        from .evaluation import sync_quality_events_for_movements
        from .models import DriverQualityEvent
        manifest, cte, movement = self._movement("ROM13")
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code="13", description="ENTREGA PREJUDICADA PELO HORARIO",
            occurred_at=timezone.now(), source="SSW_ROMANEIO",
        )
        # mesma ocorrência repetida/importada novamente não pode criar nova penalização
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code="13", description="ENTREGA PREJUDICADA PELO HORARIO",
            occurred_at=timezone.now(), source="SSW_ROMANEIO",
        )
        sync_quality_events_for_movements([movement.pk])
        sync_quality_events_for_movements([movement.pk])
        events = DriverQualityEvent.objects.filter(movement=movement)
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().status, DriverQualityEvent.Status.PENDING)
        self.assertFalse(events.get().affects_quality)

    def test_new_attempt_new_rom13_can_penalize_again_after_manual_validation(self):
        from .evaluation import review_quality_event, sync_quality_events_for_movements
        from .models import DriverQualityEvent
        for suffix in ("A", "B"):
            manifest, cte, movement = self._movement(suffix)
            DeliveryOccurrence.objects.create(
                cte=cte, movement=movement, code="13", description="ENTREGA PREJUDICADA PELO HORARIO",
                occurred_at=timezone.now(), source="SSW_ROMANEIO",
            )
        sync_quality_events_for_movements()
        events = list(DriverQualityEvent.objects.filter(driver=self.driver).order_by("pk"))
        self.assertEqual(len(events), 2)
        for event in events:
            review_quality_event(
                event, status=DriverQualityEvent.Status.DRIVER_RESPONSIBLE,
                reviewer=self.reviewer, visible_reason="Responsabilidade confirmada pela coordenação.",
            )
        self.assertEqual(
            DriverQualityEvent.objects.filter(driver=self.driver, status=DriverQualityEvent.Status.DRIVER_RESPONSIBLE).count(), 2
        )

    def test_responsibility_requires_visible_reason(self):
        from .evaluation import review_quality_event, sync_quality_events_for_movements
        from .models import DriverQualityEvent
        manifest, cte, movement = self._movement("REASON")
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code="13", description="ENTREGA PREJUDICADA PELO HORARIO",
            occurred_at=timezone.now(), source="SSW_ROMANEIO",
        )
        sync_quality_events_for_movements([movement.pk])
        event = DriverQualityEvent.objects.get(movement=movement)
        with self.assertRaises(ValueError):
            review_quality_event(event, status=DriverQualityEvent.Status.DRIVER_RESPONSIBLE, reviewer=self.reviewer)

    def test_regularity_counts_exact_only_and_gold_is_neutral(self):
        from .evaluation import regularity_summary
        from apps.proofs.models import RetainedProof
        manifest, cte, movement = self._movement("REG")
        proof = RetainedProof.objects.create(
            cte=cte, client=self.client_obj, address=self.address, original_driver=self.driver,
            original_manifest=manifest, retained_at=timezone.now(), status=RetainedProof.Status.WAITING,
        )
        yesterday = self.today - timedelta(days=1)
        exact = self.ProofPickupOpportunity.objects.create(
            proof=proof, driver=self.driver, manifest=manifest, operation_date=yesterday,
            kind=self.ProofPickupOpportunity.Kind.EXACT, status=self.ProofPickupOpportunity.Status.MISSED,
        )
        # Outro comprovante para respeitar a chave única por proof/manifest/data/kind.
        cte2 = CTe.objects.create(ctrc="CTE-V3-GOLD", client=self.client_obj)
        proof2 = RetainedProof.objects.create(
            cte=cte2, client=self.client_obj, address=self.address, original_driver=self.driver,
            original_manifest=manifest, retained_at=timezone.now(), status=RetainedProof.Status.WAITING,
        )
        self.ProofPickupOpportunity.objects.create(
            proof=proof2, driver=self.driver, manifest=manifest, operation_date=yesterday,
            kind=self.ProofPickupOpportunity.Kind.GOLD, status=self.ProofPickupOpportunity.Status.EXPIRED_NEUTRAL,
        )
        summary = regularity_summary(self.driver.pk, yesterday, self.today)
        self.assertEqual(summary["required"], 1)
        self.assertEqual(summary["missed"], 1)
        self.assertEqual(summary["score"], Decimal("0.0"))
