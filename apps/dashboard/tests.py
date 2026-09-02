from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver, Vehicle
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof


class DashboardEvolutionRegressionTests(TestCase):
    """Regressões da série Evolução Operacional (v0.3.0.5)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("dashboard-qa", password="x")
        self.client.force_login(self.user)
        self.driver = Driver.objects.create(name="Motorista QA", cpf="99999999999")
        self.vehicle = Vehicle.objects.create(plate="QAA1A11")
        self.customer = Client.objects.create(name="Cliente QA", cnpj="999")
        self.address = ClientAddress.objects.create(
            client=self.customer,
            street="Rua QA",
            district="Centro",
            city="Belem",
            state="PA",
            normalized_address="RUA QA CENTRO BELEM PA",
        )

    def _movement(self, suffix, manifest_day, route_day):
        manifest = Manifest.objects.create(
            number=f"ROM-{suffix}", date=manifest_day, driver=self.driver,
            vehicle=self.vehicle, status="BAIXADO",
        )
        cte = CTe.objects.create(
            ctrc=f"CTE-{suffix}", client=self.customer,
            freight_value=Decimal("100"), weight_kg=Decimal("100"),
        )
        movement = DeliveryMovement.objects.create(
            cte=cte, manifest=manifest, driver=self.driver, vehicle=self.vehicle,
            client=self.customer, address=self.address, movement_date=manifest_day,
            status="BAIXADO", weight_kg=Decimal("100"),
        )
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code="85", description="SAIDA PARA ENTREGA",
            occurred_at=timezone.make_aware(datetime.combine(route_day, datetime.min.time()).replace(hour=8)),
            source="SSW_ROMANEIO",
        )
        return manifest, cte, movement

    @patch("apps.dashboard.views.refresh_today_opportunities", return_value=set())
    def test_current_in_progress_routes_do_not_become_historical_pendencies(self, _refresh):
        # Uma retenção histórica sem DATA OCORR foi importada em 01/09 pelo fallback antigo.
        # A rota real saiu em 31/08, portanto o gráfico deve atribuí-la a 31/08.
        manifest, cte, movement = self._movement("RET", date(2026, 8, 30), date(2026, 8, 31))
        imported_at = timezone.make_aware(datetime(2026, 9, 1, 10, 0))
        proof = RetainedProof.objects.create(
            cte=cte, client=self.customer, address=self.address,
            original_driver=self.driver, original_manifest=manifest,
            retained_at=imported_at, freight_value=Decimal("100"),
            status=RetainedProof.Status.WAITING,
        )
        RetainedProof.objects.filter(pk=proof.pk).update(created_at=imported_at)
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code="34",
            description="MERCADORIA EM CONFERENCIA NO CLIENTE", occurred_at=None, source="SSW_ROMANEIO",
        )

        # Rotas ainda em andamento em 01/09 não são "novas pendências documentais".
        for idx in range(3):
            self._movement(f"OPEN-{idx}", date(2026, 8, 31), date(2026, 9, 1))

        response = self.client.get(
            reverse("dashboard"),
            {"start": "2026-08-31", "end": "2026-09-01"},
        )
        self.assertEqual(response.status_code, 200)
        evolution = response.context["evolution"]
        self.assertEqual(evolution["labels"], ["31/08", "01/09"])
        self.assertEqual(evolution["retencoes"], [1, 0])
        self.assertEqual(evolution["pendencias"], [1, 0])

    @patch("apps.dashboard.views.refresh_today_opportunities", return_value=set())
    def test_empty_sunday_is_omitted_but_sunday_with_activity_is_kept(self, _refresh):
        # 30/08/2026 = domingo; com operação apenas na segunda, o domingo some.
        self._movement("MON", date(2026, 8, 30), date(2026, 8, 31))
        response = self.client.get(
            reverse("dashboard"), {"start": "2026-08-30", "end": "2026-08-31"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["evolution"]["labels"], ["31/08"])

        # Qualquer atividade real no domingo recoloca o dia no eixo.
        self._movement("SUN", date(2026, 8, 29), date(2026, 8, 30))
        response = self.client.get(
            reverse("dashboard"), {"start": "2026-08-30", "end": "2026-08-31"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["evolution"]["labels"], ["30/08", "31/08"])

    @patch("apps.dashboard.views.refresh_today_opportunities", return_value=set())
    def test_later_delivery_does_not_move_old_route_into_later_operational_day(self, _refresh):
        manifest, cte, movement = self._movement("LATE", date(2026, 8, 30), date(2026, 8, 31))
        DeliveryOccurrence.objects.create(
            cte=cte, movement=None, code="1", description="ENTREGUE",
            occurred_at=timezone.make_aware(datetime(2026, 9, 1, 14, 0)), source="SSW_CTRC",
        )
        response = self.client.get(reverse("dashboard"), {"start":"2026-08-31", "end":"2026-09-01"})
        self.assertEqual(response.status_code, 200)
        evolution = response.context["evolution"]
        self.assertEqual(evolution["labels"], ["31/08", "01/09"])
        self.assertEqual(evolution["entregas"], [0, 0])
