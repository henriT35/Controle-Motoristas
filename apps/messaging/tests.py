from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class WhatsAppPairingPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="wa-admin", password="teste", is_staff=True)
        self.client.force_login(self.admin)

    def test_pairing_page_is_dedicated_to_qr_generation(self):
        response = self.client.get(reverse("whatsapp_pairing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerar QR Code")
        self.assertContains(response, "data-whatsapp-qr-img")
        self.assertContains(response, "Aparelhos conectados")

    def test_whatsapp_center_links_to_pairing_page(self):
        response = self.client.get(reverse("whatsapp_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("whatsapp_pairing"))

from django.test import SimpleTestCase, override_settings
from apps.drivers.models import Driver
from apps.messaging.models import WhatsAppMessage
from apps.messaging.services import whatsapp_phone_candidates


class BrazilianPhoneNormalizationTests(SimpleTestCase):
    def test_para_mobile_with_ninth_digit_produces_legacy_candidate(self):
        self.assertEqual(
            whatsapp_phone_candidates("91 9 8765-4321"),
            ["5591987654321", "559187654321"],
        )

    def test_para_legacy_number_produces_ninth_digit_candidate(self):
        self.assertEqual(
            whatsapp_phone_candidates("91 8765-4321"),
            ["559187654321", "5591987654321"],
        )


@override_settings(PANEL_PUBLIC_BASE_URL="http://203.0.113.10")
class WhatsAppBulkAllDriversTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="bulk-admin", password="teste", is_staff=True)
        self.client.force_login(self.admin)
        self.driver = Driver.objects.create(
            name="Motorista Sem Rota",
            cpf="999.999.999-90",
            whatsapp_phone="91987654321",
            whatsapp_enabled=True,
        )

    def test_bulk_all_registered_queues_driver_even_without_route(self):
        response = self.client.post(reverse("whatsapp_send_all_registered"), {"date": "2026-09-02"})
        self.assertEqual(response.status_code, 302)
        msg = WhatsAppMessage.objects.get(driver=self.driver)
        self.assertEqual(msg.status, WhatsAppMessage.Status.PENDING)
        self.assertIn("Painel Motoristas", msg.body)
