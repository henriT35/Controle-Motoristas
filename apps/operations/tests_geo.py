from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver
from apps.proofs.models import RetainedProof
from .geo import (
    active_branch,
    build_geo_summary,
    normalize_geo,
    normalize_neighborhood,
)
from .models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest


class GeoNormalizationTests(TestCase):
    def test_normalizes_accents_case_and_spacing(self):
        self.assertEqual(normalize_geo("  Belém / PA "), "BELEM PA")
        self.assertEqual(normalize_geo("São  José dos Pinhais"), "SAO JOSE DOS PINHAIS")

    def test_neighborhood_alias_is_contextual(self):
        self.assertEqual(
            normalize_neighborhood("40 Horas (Coqueiro)", state="PA", city="Ananindeua"),
            "QUARENTA HORAS",
        )
        self.assertEqual(
            normalize_neighborhood("40 Horas (Coqueiro)", state="PR", city="Curitiba"),
            "40 HORAS COQUEIRO",
        )

    def test_tapana_alias_matches_canonical_polygon_name(self):
        self.assertEqual(
            normalize_neighborhood("Tapanã (Icoaraci)", state="PA", city="Belém"),
            "TAPANA",
        )


class GeoSummaryTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(name="Motorista A", cpf="11111111111")
        self.client = Client.objects.create(name="Cliente A", cnpj="11111111000111")
        self.pedreira = ClientAddress.objects.create(
            client=self.client,
            street="Rua A",
            district="Pedreira",
            postal_code="66000000",
            city="Belém",
            state="PA",
            normalized_address="RUA A | PEDREIRA | 66000000 | BELEM | PA",
        )
        self.marco = ClientAddress.objects.create(
            client=self.client,
            street="Rua B",
            district="Marco",
            postal_code="66000001",
            city="Belém",
            state="PA",
            normalized_address="RUA B | MARCO | 66000001 | BELEM | PA",
        )

    def movement(self, suffix, address, code, description):
        cte = CTe.objects.create(ctrc=f"GRU{suffix}", client=self.client, weight_kg=Decimal("100"), volumes=2)
        manifest = Manifest.objects.create(number=f"BEL{suffix}", date=date(2026, 7, 1), driver=self.driver, status="BAIXADO")
        movement = DeliveryMovement.objects.create(
            cte=cte, manifest=manifest, driver=self.driver, client=self.client,
            address=address, movement_date=date(2026, 7, 1), status=description,
            weight_kg=Decimal("100"), volumes=2,
        )
        DeliveryOccurrence.objects.create(
            cte=cte, movement=movement, code=code, description=description,
            occurred_at=timezone.make_aware(datetime(2026, 7, 1, 16, 0)), source="SSW_ROMANEIO",
        )
        return cte, manifest, movement

    @override_settings(SSW_ROBOT_UNIT="BEL")
    def test_real_attempt_semantics_feed_neighborhood_metrics(self):
        self.movement("001", self.pedreira, "1", "ENTREGUE")
        cte2, manifest2, _ = self.movement("002", self.pedreira, "34", "MERCADORIA EM CONFERENCIA NO CLIENTE")
        self.movement("003", self.marco, "13", "ENTREGA PREJUDICADA PELO HORARIO")
        RetainedProof.objects.create(
            cte=cte2, client=self.client, address=self.pedreira, original_driver=self.driver,
            original_manifest=manifest2, retained_at=timezone.make_aware(datetime(2026, 7, 1, 16, 0)),
            status=RetainedProof.Status.WAITING,
        )

        payload = build_geo_summary(
            date(2026, 7, 1), date(2026, 7, 1), branch="BEL", metric="delivered", level="auto"
        )
        self.assertEqual(payload["level"], "neighborhood")
        rows = {normalize_geo(row["name"]): row for row in payload["regions"]}
        self.assertEqual(rows["PEDREIRA"]["attempts"], 2)
        self.assertEqual(rows["PEDREIRA"]["delivered"], 1)
        self.assertEqual(rows["PEDREIRA"]["retentions"], 1)
        self.assertEqual(rows["PEDREIRA"]["active_proofs"], 1)
        self.assertEqual(rows["MARCO"]["time_window_failures"], 1)
        self.assertEqual(payload["summary"]["delivered"], 1)
        self.assertEqual(payload["summary"]["retentions"], 1)
        self.assertEqual(payload["summary"]["time_window_failures"], 1)

    @override_settings(SSW_ROBOT_UNIT="CWB")
    def test_engine_has_no_bel_branch_hardcode(self):
        self.assertEqual(active_branch(), "CWB")
        curitiba = ClientAddress.objects.create(
            client=self.client,
            street="Rua C",
            district="Água Verde",
            postal_code="80000000",
            city="Curitiba",
            state="PR",
            normalized_address="RUA C | AGUA VERDE | 80000000 | CURITIBA | PR",
        )
        self.movement("010", curitiba, "1", "ENTREGUE")
        payload = build_geo_summary(
            date(2026, 7, 1), date(2026, 7, 1), branch="CWB", metric="delivered", level="auto"
        )
        # Sem provider de bairros homologado para Curitiba na V1, cai de forma
        # automática para município e usa a malha oficial do IBGE.
        self.assertEqual(payload["level"], "municipality")
        self.assertEqual(payload["branch"], "CWB")
        self.assertTrue(payload["geometry"]["urls"])
        self.assertIn("PR", payload["geometry"]["urls"][0])
        self.assertIn("codarea", payload["geometry"]["feature_code_properties"])
        self.assertTrue(payload["geometry"]["locality_sources"])
        self.assertIn("/estados/PR/municipios", payload["geometry"]["locality_sources"][0]["url"])

    @override_settings(SSW_ROBOT_UNIT="BEL")
    def test_rejects_cross_branch_query_on_single_branch_v1_database(self):
        with self.assertRaises(ValueError):
            build_geo_summary(date(2026, 7, 1), date(2026, 7, 1), branch="CWB")
