from datetime import datetime
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
