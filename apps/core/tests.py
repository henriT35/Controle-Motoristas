from datetime import date, datetime
from unittest.mock import patch
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
from apps.operations.models import CTe, Manifest, DeliveryMovement, DeliveryOccurrence
from apps.proofs.models import RetainedProof
from .models import SystemSettings
from .services import calculate_driver_metrics, is_delivery_completed, parse_period


class DeliveryAndScoreTests(TestCase):
    def setUp(self):
        self.driver=Driver.objects.create(name="Motorista Teste",cpf="11111111111")
        self.client=Client.objects.create(name="Cliente Teste",cnpj="123")
        self.addr=ClientAddress.objects.create(client=self.client,street="Rua A",district="Marco",postal_code="66000000",city="Belem",state="PA",normalized_address="RUA A MARCO")
        self.vehicle=Vehicle.objects.create(plate="ABC1D23")
        self.manifest=Manifest.objects.create(number="ROM001",date=date(2026,8,10),driver=self.driver,vehicle=self.vehicle,status="BAIXADO")
        self.cte=CTe.objects.create(ctrc="GRU000001",client=self.client,freight_value=Decimal("100"),weight_kg=Decimal("1000"))
        self.movement=DeliveryMovement.objects.create(cte=self.cte,manifest=self.manifest,driver=self.driver,vehicle=self.vehicle,client=self.client,address=self.addr,movement_date=date(2026,8,10),status="BAIXADO",weight_kg=Decimal("1000"))
        DeliveryOccurrence.objects.create(
            cte=self.cte, movement=self.movement, code="85", description="SAIDA PARA ENTREGA",
            occurred_at=timezone.make_aware(datetime(2026,8,10,8,0)), source="SSW_ROMANEIO",
        )
        SystemSettings.load()

    def test_entregue_comes_from_occurrence(self):
        self.assertFalse(is_delivery_completed(self.cte))
        DeliveryOccurrence.objects.create(cte=self.cte,movement=self.movement,code="1",description="ENTREGUE",occurred_at=timezone.make_aware(datetime(2026,8,10,12,0)))
        self.assertTrue(is_delivery_completed(self.cte))

    def test_rom34_plus_later_delivery_keeps_success_and_counts_retention(self):
        DeliveryOccurrence.objects.create(
            cte=self.cte, movement=self.movement, code="34",
            description="MERCADORIA EM CONFERENCIA NO CLIENTE",
            occurred_at=timezone.make_aware(datetime(2026,8,10,11,0)), source="SSW_ROMANEIO",
        )
        DeliveryOccurrence.objects.create(
            cte=self.cte, movement=self.movement, code="1", description="ENTREGUE",
            occurred_at=timezone.make_aware(datetime(2026,8,10,12,0)), source="SSW_CTRC",
        )
        RetainedProof.objects.create(
            cte=self.cte,client=self.client,address=self.addr,original_driver=self.driver,
            original_manifest=self.manifest,retained_at=timezone.make_aware(datetime(2026,8,10,11,0)),
            recovered_at=timezone.make_aware(datetime(2026,8,10,12,0)),
            status=RetainedProof.Status.RECOVERED,freight_value=Decimal("100"),
        )
        metric=calculate_driver_metrics(date(2026,8,1),date(2026,8,31))[0]
        self.assertEqual(metric.success_rate, Decimal("100.00"))
        self.assertEqual(metric.retained, 1)
        self.assertEqual(metric.retention_rate, Decimal("100.00"))


class SettingsPermissionTests(TestCase):
    def test_anonymous_cannot_open_settings(self):
        response=self.client.get(reverse("settings"))
        self.assertEqual(response.status_code,302)

    def test_non_staff_cannot_open_settings(self):
        user=get_user_model().objects.create_user("analista",password="x")
        self.client.force_login(user)
        response=self.client.get(reverse("settings"))
        self.assertEqual(response.status_code,302)

class BrazilianFormattingTests(TestCase):
    def test_compact_brl_format_for_dashboard_kpis(self):
        from apps.core.templatetags.format_br import brl, brl_compact
        self.assertEqual(brl_compact(Decimal("3024818.23")), "R$ 3,02 mi")
        self.assertEqual(brl_compact(Decimal("426815.19")), "R$ 426,8 mil")
        self.assertEqual(brl(Decimal("3024818.23")), "R$ 3.024.818,23")


class PeriodParsingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 1))
    def test_30d_is_rolling_window_not_current_month(self, _today):
        request = self.factory.get("/dashboard/", {"period": "30d"})
        start, end, _label, mode = parse_period(request, "month")
        self.assertEqual((start, end, mode), (date(2026, 8, 3), date(2026, 9, 1), "30d"))

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 1))
    def test_week_starts_on_monday_and_ends_today(self, _today):
        request = self.factory.get("/dashboard/", {"period": "week"})
        start, end, _label, mode = parse_period(request, "month")
        self.assertEqual((start, end, mode), (date(2026, 8, 31), date(2026, 9, 1), "week"))

class NavigationStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("nav-qa", password="x")
        self.client.force_login(self.user)

    def test_sidebar_restores_last_root_querystring(self):
        response = self.client.get(reverse("deliveries"), {
            "start": "2026-08-01", "end": "2026-09-01", "q": "FEDERAL BUS", "page": "3"
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("drivers"), {"period": "90d"})
        self.assertEqual(response.status_code, 200)
        saved = response.context["nav_urls"]["deliveries"]
        self.assertIn("q=FEDERAL+BUS", saved)
        self.assertIn("page=3", saved)
        self.assertIn("start=2026-08-01", saved)
