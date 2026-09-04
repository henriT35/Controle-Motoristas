from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver
from apps.operations.models import CTe, DeliveryMovement, Manifest


class ClientDependentGeoFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("client-qa", password="x")
        self.client.force_login(self.user)
        self.driver = Driver.objects.create(name="Motorista Real", cpf="12345678901")
        customer = Client.objects.create(name="Cliente", cnpj="C1")
        belem = ClientAddress.objects.create(client=customer, city="Belém", district="Marco", state="PA", normalized_address="BELEM MARCO")
        ana = ClientAddress.objects.create(client=customer, city="Ananindeua", district="Coqueiro", state="PA", normalized_address="ANANINDEUA COQUEIRO")
        for idx, address in enumerate((belem, ana), 1):
            manifest = Manifest.objects.create(number=f"ROM-C{idx}", date=date(2026,8,31), driver=self.driver)
            cte = CTe.objects.create(ctrc=f"CTE-C{idx}", client=customer)
            DeliveryMovement.objects.create(cte=cte, manifest=manifest, driver=self.driver, client=customer, address=address, movement_date=date(2026,8,31))

    def test_selected_city_limits_district_options(self):
        response = self.client.get(reverse("clients"), {"start":"2026-08-31", "end":"2026-08-31", "city":"Belém"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["districts"], ["Marco"])
