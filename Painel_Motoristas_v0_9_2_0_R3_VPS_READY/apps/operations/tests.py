from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.core.services import (
    manifests_for_operational_date,
    operational_date_for_manifest,
    operational_manifest_classification_map,
    operational_movements_for_period,
    planned_manifests,
    retention_stats_for_date,
)
from apps.drivers.models import Driver, Vehicle
from apps.proofs.models import RetainedProof
from .geo import build_geo_summary
from .models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from .services import build_manifest_cards, opportunities_summary


def aware(day: date, hour=8, minute=0):
    return timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute))


class OperationalRouteDateTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista Rota", cpf="11122233344")
        self.vehicle = Vehicle.objects.create(plate="ABC1D23")
        self.client_obj = Client.objects.create(name="Cliente Rota", cnpj="12.345.678/0001-90")
        self.address = ClientAddress.objects.create(
            client=self.client_obj,
            street="Av Teste 100",
            district="Marco",
            postal_code="66000000",
            city="Belem",
            state="PA",
            normalized_address="AV TESTE 100 | MARCO | 66000000 | BELEM | PA",
        )

    def make_movement(self, number, emission_day, ctrc, *, status="BAIXADO"):
        manifest = Manifest.objects.create(
            number=number, date=emission_day, driver=self.driver, vehicle=self.vehicle, status=status,
        )
        cte = CTe.objects.create(
            ctrc=ctrc, client=self.client_obj, freight_value=Decimal("100.00"), weight_kg=Decimal("100.000"),
        )
        movement = DeliveryMovement.objects.create(
            cte=cte, manifest=manifest, driver=self.driver, vehicle=self.vehicle,
            client=self.client_obj, address=self.address, movement_date=emission_day,
            status=status, weight_kg=Decimal("100.000"),
        )
        return manifest, cte, movement

    def add_rom(self, cte, movement, code, description, day=None, hour=8):
        return DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code=code, description=description,
            occurred_at=aware(day, hour) if day else None, source="SSW_ROMANEIO",
        )

    def add_exit(self, cte, movement, day):
        return self.add_rom(cte, movement, "85", "SAIDA PARA ENTREGA", day)

    def test_manifest_created_yesterday_belongs_to_exit_day(self):
        manifest, cte, movement = self.make_movement("BEL000001-1", date(2026, 8, 30), "CTE0001")
        self.add_exit(cte, movement, date(2026, 8, 31))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 8, 30)))
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))
        self.assertEqual(operational_date_for_manifest(manifest), date(2026, 8, 31))
        self.assertEqual(operational_manifest_classification_map(date(2026, 8, 31))[manifest.pk], "CONFIRMED")

    def test_manifest_created_and_executed_same_day_is_in_operation(self):
        manifest, cte, movement = self.make_movement("BEL000003-1", date(2026, 8, 31), "CTE0003")
        self.add_exit(cte, movement, date(2026, 8, 31))
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))

    def test_later_rom_event_does_not_migrate_old_manifest_to_new_day(self):
        manifest, cte, movement = self.make_movement("BEL-OLD-1", date(2026, 8, 18), "CTE-OLD-1")
        self.add_rom(cte, movement, "13", "ENTREGA PREJUDICADA PELO HORARIO", date(2026, 8, 18), 9)
        self.add_rom(cte, movement, "1", "ENTREGUE", date(2026, 9, 1), 15)
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 8, 18)))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 1)))
        self.assertEqual(operational_date_for_manifest(manifest), date(2026, 8, 18))

    def test_ctrc_consolidated_event_never_infers_route_date(self):
        manifest, cte, movement = self.make_movement("BEL-CTRC-ONLY", date(2026, 8, 18), "CTE-CTRC-ONLY")
        DeliveryOccurrence.objects.create(
            cte=cte, movement=None, code="1", description="ENTREGUE",
            occurred_at=aware(date(2026, 9, 1), 15), source="SSW_CTRC",
        )
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 1)))
        self.assertIn(manifest, planned_manifests(date(2026, 8, 18), lookback_days=1))

    def test_no_85_uses_first_dated_rom_fact_only(self):
        manifest, cte, movement = self.make_movement("BEL-INF-1", date(2026, 8, 30), "CTE-INF-1")
        self.add_rom(cte, movement, "13", "ENTREGA PREJUDICADA PELO HORARIO", date(2026, 8, 31), 10)
        self.add_rom(cte, movement, "1", "ENTREGUE", date(2026, 9, 1), 16)
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 1)))
        self.assertEqual(operational_manifest_classification_map(date(2026, 8, 31))[manifest.pk], "INFERRED")

    def test_undated_85_does_not_invent_d_plus_one(self):
        manifest, cte, movement = self.make_movement("BEL-UNDATED-85", date(2026, 8, 30), "CTE-UNDATED-85", status="PENDENTE")
        self.add_rom(cte, movement, "85", "SAIDA PARA ENTREGA", None)
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 8, 30)))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))
        self.assertIn(manifest, planned_manifests(date(2026, 8, 30), lookback_days=1))

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_today_current_ctrc_saida_moves_route_out_of_planning_without_rewriting_history(self, _today):
        manifest, cte, movement = self.make_movement("BEL-LIVE-85", date(2026, 9, 2), "CTE-LIVE-85", status="PENDENTE")
        # O estado consolidado é fotografia ao vivo, não evento histórico. Ainda
        # assim, para HOJE, uma SAIDA PARA ENTREGA atual não pode ficar em
        # Planejamento. Nenhuma data passada é inventada.
        cte.current_status = "SAIDA PARA ENTREGA"
        cte.save(update_fields=["current_status"])
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 9, 2)))
        self.assertNotIn(manifest, planned_manifests(date(2026, 9, 2), lookback_days=1))
        self.assertEqual(operational_manifest_classification_map(date(2026, 9, 2))[manifest.pk], "CONFIRMED")
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 1)))

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_today_same_day_manifest_with_live_movement_saida_leaves_planning(self, _today):
        manifest, cte, movement = self.make_movement("BEL-LIVE-MOVE", date(2026, 9, 2), "CTE-LIVE-MOVE", status="PENDENTE")
        movement.occurrence_text = "SAIDA PARA ENTREGA"
        movement.save(update_fields=["occurrence_text"])
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 9, 2)))
        self.assertNotIn(manifest, planned_manifests(date(2026, 9, 2), lookback_days=1))
        # O mesmo snapshot não deve inventar uma rota em dia encerrado.
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 1)))

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_live_saida_is_in_period_that_contains_today(self, _today):
        manifest, cte, movement = self.make_movement("BEL-LIVE-RANGE", date(2026, 9, 2), "CTE-LIVE-RANGE", status="PENDENTE")
        cte.current_status = "SAIDA PARA ENTREGA"
        cte.save(update_fields=["current_status"])
        qs = operational_movements_for_period(date(2026, 8, 4), date(2026, 9, 2))
        self.assertTrue(qs.filter(manifest=manifest).exists())

    def test_same_cte_multiple_attempts_keep_independent_manifest_dates(self):
        m1, cte, move1 = self.make_movement("BEL-ATT-1", date(2026, 8, 18), "CTE-MULTI")
        self.add_rom(cte, move1, "13", "ENTREGA PREJUDICADA PELO HORARIO", date(2026, 8, 18), 10)
        m2 = Manifest.objects.create(number="BEL-ATT-2", date=date(2026, 9, 1), driver=self.driver, vehicle=self.vehicle)
        move2 = DeliveryMovement.objects.create(
            cte=cte, manifest=m2, driver=self.driver, vehicle=self.vehicle, client=self.client_obj,
            address=self.address, movement_date=date(2026, 9, 1), status="BAIXADO",
        )
        self.add_exit(cte, move2, date(2026, 9, 1))
        self.assertIn(m1, manifests_for_operational_date(date(2026, 8, 18)))
        self.assertNotIn(m1, manifests_for_operational_date(date(2026, 9, 1)))
        self.assertIn(m2, manifests_for_operational_date(date(2026, 9, 1)))

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_historical_dates_do_not_receive_carryover(self, _today):
        manifest, cte, movement = self.make_movement("BEL-HIST-CARRY", date(2026, 8, 29), "CTE-HIST-CARRY")
        self.add_exit(cte, movement, date(2026, 8, 29))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))
        self.assertFalse(operational_movements_for_period(date(2026, 8, 31), date(2026, 8, 31)).filter(manifest=manifest).exists())

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_current_day_can_receive_open_carryover(self, _today):
        manifest, cte, movement = self.make_movement("BEL-CARRY-TODAY", date(2026, 9, 1), "CTE-CARRY-TODAY")
        self.add_exit(cte, movement, date(2026, 9, 1))
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 9, 2)))
        self.assertTrue(operational_movements_for_period(date(2026, 9, 2), date(2026, 9, 2)).filter(manifest=manifest).exists())

    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_current_carryover_stops_after_later_rom_fact(self, _today):
        manifest, cte, movement = self.make_movement("BEL-CARRY-CLOSED", date(2026, 9, 1), "CTE-CARRY-CLOSED")
        self.add_exit(cte, movement, date(2026, 9, 1))
        self.add_rom(cte, movement, "1", "ENTREGUE", date(2026, 9, 1), 17)
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 9, 2)))


class RetentionTemporalTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista Retenção", cpf="30030030030")
        self.customer = Client.objects.create(name="Cliente Retenção", cnpj="RET")
        self.address = ClientAddress.objects.create(client=self.customer, street="Rua R", district="Marco", city="Belem", state="PA", normalized_address="RUA R MARCO")
        self.manifest = Manifest.objects.create(number="BEL-RET-1", date=date(2026, 9, 1), driver=self.driver)
        self.cte = CTe.objects.create(ctrc="CTE-RET-1", client=self.customer)
        self.move = DeliveryMovement.objects.create(cte=self.cte, manifest=self.manifest, driver=self.driver, client=self.customer, address=self.address, movement_date=date(2026, 9, 1))
        DeliveryOccurrence.objects.create(cte=self.cte, movement=self.move, code="85", description="SAIDA PARA ENTREGA", occurred_at=aware(date(2026, 9, 1), 8), source="SSW_ROMANEIO")
        DeliveryOccurrence.objects.create(cte=self.cte, movement=self.move, code="34", description="MERCADORIA EM CONFERENCIA NO CLIENTE", occurred_at=aware(date(2026, 9, 1), 11), source="SSW_ROMANEIO")

    def test_undated_rom34_without_route_evidence_stays_unconfirmed(self):
        manifest = Manifest.objects.create(number="BEL-RET-UNDATED", date=date(2026,8,18), driver=self.driver)
        cte = CTe.objects.create(ctrc="CTE-RET-UNDATED", client=self.customer)
        move = DeliveryMovement.objects.create(cte=cte, manifest=manifest, driver=self.driver, client=self.customer, address=self.address, movement_date=date(2026,8,18))
        DeliveryOccurrence.objects.create(cte=cte, movement=move, code="34", description="MERCADORIA EM CONFERENCIA NO CLIENTE", occurred_at=None, source="SSW_ROMANEIO")
        RetainedProof.objects.create(cte=cte, client=self.customer, address=self.address, original_driver=self.driver, original_manifest=manifest, retained_at=aware(date(2026,8,18),12))
        self.assertEqual(retention_stats_for_date(date(2026,8,18))["retained"], 0)

    def test_retained_day_remains_historical_after_later_recovery(self):
        RetainedProof.objects.create(
            cte=self.cte, client=self.customer, address=self.address, original_driver=self.driver,
            original_manifest=self.manifest, retained_at=aware(date(2026, 9, 2), 8),
            recovered_at=aware(date(2026, 9, 3), 10), recovery_driver=self.driver,
            status=RetainedProof.Status.RECOVERED,
        )
        stats = retention_stats_for_date(date(2026, 9, 1))
        self.assertEqual(stats, {"retained": 1, "recovered_later": 1, "still_open": 0})
        self.assertEqual(retention_stats_for_date(date(2026, 9, 2))["retained"], 0)


class RouteOpportunityTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista Oportunidade", cpf="55566677788")
        self.client_obj = Client.objects.create(name="Cliente Exato", cnpj="12.345.678/0001-90")
        self.addr = ClientAddress.objects.create(
            client=self.client_obj, street="Rua A", district="Marco", postal_code="66000000",
            city="Belem", state="PA", normalized_address="RUA A | MARCO | 66000000 | BELEM | PA"
        )
        self.manifest = Manifest.objects.create(number="BEL100001-1", date=date(2026, 8, 31), driver=self.driver, status="BAIXADO")
        self.cte_route = CTe.objects.create(ctrc="ROTA1", client=self.client_obj)
        self.move = DeliveryMovement.objects.create(
            cte=self.cte_route, manifest=self.manifest, driver=self.driver, client=self.client_obj,
            address=self.addr, movement_date=date(2026, 8, 31), status="BAIXADO"
        )
        DeliveryOccurrence.objects.create(cte=self.cte_route, movement=self.move, code="85", description="SAIDA PARA ENTREGA", occurred_at=aware(date(2026,8,31)), source="SSW_ROMANEIO")

    def test_exact_proof_is_counted_once_across_cards(self):
        proof_cte = CTe.objects.create(ctrc="PEND1", client=self.client_obj)
        proof = RetainedProof.objects.create(
            cte=proof_cte, client=self.client_obj, address=self.addr, original_driver=self.driver,
            original_manifest=self.manifest, retained_at=aware(date(2026, 8, 20), 10)
        )
        other_manifest = Manifest.objects.create(number="BEL100002-1", date=date(2026, 8, 31), driver=self.driver, status="BAIXADO")
        other_cte = CTe.objects.create(ctrc="ROTA2", client=self.client_obj)
        other_move = DeliveryMovement.objects.create(
            cte=other_cte, manifest=other_manifest, driver=self.driver, client=self.client_obj,
            address=self.addr, movement_date=date(2026, 8, 31), status="BAIXADO"
        )
        DeliveryOccurrence.objects.create(cte=other_cte, movement=other_move, code="85", description="SAIDA PARA ENTREGA", occurred_at=aware(date(2026,8,31),9), source="SSW_ROMANEIO")
        cards = build_manifest_cards([self.manifest, other_manifest], persist_available=False, operational_date=date(2026, 8, 31))
        exact_ids, regional_ids = opportunities_summary(cards)
        self.assertEqual(exact_ids, {proof.pk})
        self.assertEqual(regional_ids, set())

    def test_historical_card_sees_proof_that_was_open_that_day_even_if_recovered_later(self):
        proof_cte = CTe.objects.create(ctrc="PEND-HIST", client=self.client_obj)
        proof = RetainedProof.objects.create(
            cte=proof_cte, client=self.client_obj, address=self.addr, original_driver=self.driver,
            original_manifest=self.manifest, retained_at=aware(date(2026, 8, 20), 10),
            recovered_at=aware(date(2026, 9, 2), 10), recovery_driver=self.driver, status=RetainedProof.Status.RECOVERED,
        )
        cards = build_manifest_cards([self.manifest], persist_available=False, operational_date=date(2026, 8, 31))
        exact_ids, _ = opportunities_summary(cards)
        self.assertIn(proof.pk, exact_ids)

    def test_manifest_without_any_rom_evidence_is_planning_not_operation(self):
        manifest = Manifest.objects.create(number="BEL-LEGACY-NO85", date=date(2026, 8, 31), driver=self.driver, status="PENDENTE")
        cte = CTe.objects.create(ctrc="CTE-LEGACY-NO85", client=self.client_obj)
        DeliveryMovement.objects.create(cte=cte, manifest=manifest, driver=self.driver, client=self.client_obj, address=self.addr, movement_date=date(2026, 8, 31), status="PENDENTE")
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 8, 31)))
        self.assertIn(manifest, planned_manifests(date(2026, 8, 31), lookback_days=1))


class DeliveriesAndCteDetailViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ops-qa", password="x")
        self.client.force_login(self.user)
        self.driver = Driver.objects.create(name="Motorista Entregas", cpf="70070070070")
        self.customer = Client.objects.create(name="Cliente Entregas", cnpj="ENTREGAS")
        self.address = ClientAddress.objects.create(client=self.customer, street="Rua E", district="Marco", city="Belem", state="PA", normalized_address="RUA E MARCO")
        self.manifest = Manifest.objects.create(number="BEL-ENT-1", date=date(2026, 9, 1), driver=self.driver)
        self.cte = CTe.objects.create(ctrc="CTE-ENT-1", invoice_number="NF-123", client=self.customer, freight_value=Decimal("250.00"))
        self.move = DeliveryMovement.objects.create(cte=self.cte, manifest=self.manifest, driver=self.driver, client=self.customer, address=self.address, movement_date=date(2026, 9, 1), weight_kg=Decimal("50"), volumes=2)
        DeliveryOccurrence.objects.create(cte=self.cte, movement=self.move, code="85", description="SAIDA PARA ENTREGA", occurred_at=aware(date(2026,9,1)), source="SSW_ROMANEIO")

    def test_deliveries_lists_operational_cte_and_cte_detail_opens(self):
        response = self.client.get(reverse("deliveries"), {"start":"2026-09-01", "end":"2026-09-01"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CTE-ENT-1")
        self.assertEqual(response.context["total_ctes"], 1)
        detail = self.client.get(reverse("cte_detail", args=[self.cte.pk]), {"next": response.request["PATH_INFO"] + "?start=2026-09-01&end=2026-09-01"})
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "NF-123")
        self.assertContains(detail, "BEL-ENT-1")


class GeoFallbackDataTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista Geo", cpf="80880880808")
        self.customer = Client.objects.create(name="Cliente Geo", cnpj="GEO")

    def _route(self, suffix, city, district):
        address = ClientAddress.objects.create(client=self.customer, street=f"Rua {suffix}", city=city, district=district, state="PA", normalized_address=f"{city} {district}")
        manifest = Manifest.objects.create(number=f"BEL-GEO-{suffix}", date=date(2026,9,1), driver=self.driver)
        cte = CTe.objects.create(ctrc=f"CTE-GEO-{suffix}", client=self.customer)
        movement = DeliveryMovement.objects.create(cte=cte, manifest=manifest, driver=self.driver, client=self.customer, address=address, movement_date=date(2026,9,1))
        DeliveryOccurrence.objects.create(cte=cte, movement=movement, code="85", description="SAIDA PARA ENTREGA", occurred_at=aware(date(2026,9,1)), source="SSW_ROMANEIO")
        return movement

    def test_neighborhood_drilldown_does_not_count_other_city_as_unresolved(self):
        self._route("B", "Belem", "Marco")
        self._route("A", "Ananindeua", "Coqueiro")
        payload = build_geo_summary(date(2026,9,1), date(2026,9,1), level="neighborhood", parent_state="PA", parent_city="Belem")
        self.assertEqual(payload["summary"]["attempts"], 1)
        self.assertEqual(payload["summary"]["unresolved"], 0)
        self.assertEqual([r["name"] for r in payload["regions"]], ["Marco"])

class OperationalRouteAttemptRegressionV0810Tests(OperationalRouteDateTests):
    @patch("apps.core.services.timezone.localdate", return_value=date(2026, 9, 2))
    def test_time_window_failure_closes_old_attempt_and_live_ctrc85_selects_only_new_attempt(self, _today):
        old_manifest, cte, old_move = self.make_movement(
            "BEL-OLD-13", date(2026, 9, 1), "CTE-RETRY-13", status="BAIXADO"
        )
        self.add_rom(
            cte, old_move, "13", "ENTREGA PREJUDICADA PELO HORARIO", date(2026, 9, 1), 17
        )
        other_driver = Driver.objects.create(name="Motorista Nova Tentativa", cpf="55566677788")
        new_manifest = Manifest.objects.create(
            number="BEL-NEW-LIVE", date=date(2026, 9, 2), driver=other_driver,
            vehicle=self.vehicle, status="PENDENTE",
        )
        new_move = DeliveryMovement.objects.create(
            cte=cte, manifest=new_manifest, driver=other_driver, vehicle=self.vehicle,
            client=self.client_obj, address=self.address, movement_date=date(2026, 9, 2),
            status="PENDENTE", occurrence_text="SAIDA PARA ENTREGA",
        )
        cte.current_status = "SAIDA PARA ENTREGA"
        cte.save(update_fields=["current_status"])

        today_manifests = set(manifests_for_operational_date(date(2026, 9, 2)))
        self.assertIn(new_manifest, today_manifests)
        self.assertNotIn(old_manifest, today_manifests)
        self.assertEqual(
            DeliveryMovement.objects.filter(
                manifest__in=today_manifests, cte=cte
            ).count(),
            1,
        )

    def test_undated_rom_fact_can_be_reconstructed_from_unique_same_ctrc_fact(self):
        manifest, cte, movement = self.make_movement(
            "BEL-HIST-REBUILD", date(2026, 4, 1), "CTE-HIST-REBUILD"
        )
        self.add_rom(cte, movement, "1", "ENTREGUE", None)
        DeliveryOccurrence.objects.create(
            cte=cte, movement=None, code="1", description="ENTREGUE",
            occurred_at=aware(date(2026, 4, 2), 16), source="SSW_CTRC",
        )
        self.assertIn(manifest, manifests_for_operational_date(date(2026, 4, 2)))
        self.assertNotIn(manifest, manifests_for_operational_date(date(2026, 4, 1)))
        self.assertEqual(
            operational_manifest_classification_map(date(2026, 4, 2))[manifest.pk],
            "INFERRED",
        )

    def test_reconstruction_refuses_same_event_shared_by_two_attempts(self):
        m1, cte, move1 = self.make_movement(
            "BEL-HIST-AMB-A", date(2026, 4, 1), "CTE-HIST-AMB"
        )
        self.add_rom(cte, move1, "1", "ENTREGUE", None)
        m2 = Manifest.objects.create(
            number="BEL-HIST-AMB-B", date=date(2026, 4, 2), driver=self.driver,
            vehicle=self.vehicle, status="BAIXADO",
        )
        move2 = DeliveryMovement.objects.create(
            cte=cte, manifest=m2, driver=self.driver, vehicle=self.vehicle,
            client=self.client_obj, address=self.address, movement_date=date(2026, 4, 2),
            status="BAIXADO",
        )
        self.add_rom(cte, move2, "1", "ENTREGUE", None)
        DeliveryOccurrence.objects.create(
            cte=cte, movement=None, code="1", description="ENTREGUE",
            occurred_at=aware(date(2026, 4, 3), 16), source="SSW_CTRC",
        )
        self.assertNotIn(m1, manifests_for_operational_date(date(2026, 4, 3)))
        self.assertNotIn(m2, manifests_for_operational_date(date(2026, 4, 3)))
