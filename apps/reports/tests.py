from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

class ExportTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user("rel",password="x")
        self.client.force_login(self.user)
    def test_excel_is_real_xlsx(self):
        response=self.client.get(reverse("report_excel",args=["drivers"]))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertIn("spreadsheetml",response["Content-Type"])

    def test_selected_period_is_preserved_in_preview_and_exports(self):
        response = self.client.get(
            reverse("reports"),
            {"start": "2026-08-01", "end": "2026-09-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period_start"], date(2026, 8, 1))
        self.assertEqual(response.context["period_end"], date(2026, 9, 1))
        self.assertIn("start=2026-08-01", response.context["period_query"])
        self.assertIn("end=2026-09-01", response.context["period_query"])

        preview = self.client.get(
            reverse("report_preview", args=["drivers"]),
            {"start": "2026-08-01", "end": "2026-09-01"},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.context["period_start"], date(2026, 8, 1))
        self.assertEqual(preview.context["period_end"], date(2026, 9, 1))
