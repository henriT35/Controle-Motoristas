import io
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import BugExchangeReference, BugReport


class BugNotebookTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("tester", password="Senha@123", is_staff=True)

    def test_anonymous_cannot_access_bug_notebook(self):
        response = self.client.get(reverse("bugs"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_bug(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("bugs"), {
            "screen": BugReport.Screen.OPERATIONS,
            "screen_path": "/operacao/hoje/",
            "title": "Romaneio não aparece",
            "priority": BugReport.Priority.P1,
            "status": BugReport.Status.OPEN,
            "description": "Teste",
            "current_result": "Não aparece",
            "expected_result": "Deve aparecer",
            "reproduction_steps": "1. Abrir tela",
            "browser_info": "Chrome",
        })
        self.assertEqual(response.status_code, 302)
        bug = BugReport.objects.get()
        self.assertEqual(bug.created_by, self.admin)

    def test_resolved_bug_gets_resolved_at(self):
        bug = BugReport.objects.create(
            screen=BugReport.Screen.DASHBOARD,
            title="Teste",
            priority=BugReport.Priority.P2,
            status=BugReport.Status.RESOLVED,
            created_by=self.admin,
        )
        self.assertIsNotNone(bug.resolved_at)

    def test_export_contains_markdown_json_summary(self):
        BugReport.objects.create(
            screen=BugReport.Screen.DASHBOARD,
            title="KPI incorreto",
            priority=BugReport.Priority.P1,
            status=BugReport.Status.OPEN,
            created_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("bug_export"))
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            self.assertIn("BUGS.md", zf.namelist())
            self.assertIn("bugs.json", zf.namelist())
            self.assertIn("resumo.json", zf.namelist())
            payload = json.loads(zf.read("bugs.json").decode("utf-8"))
            self.assertEqual(len(payload["bugs"]), 1)
            self.assertEqual(payload["bugs"][0]["title"], "KPI incorreto")

    def test_import_merges_by_sync_id_without_duplicate(self):
        bug = BugReport.objects.create(
            screen=BugReport.Screen.DASHBOARD,
            title="Título antigo",
            priority=BugReport.Priority.P2,
            status=BugReport.Status.OPEN,
            created_by=self.admin,
        )
        exchange_ref = BugExchangeReference.objects.create(bug=bug)
        payload = {
            "schema_version": 1,
            "product": "Painel Motoristas",
            "app_version": "0.2.2-p1",
            "bugs": [{
                "sync_id": str(exchange_ref.sync_id),
                "screen": BugReport.Screen.DASHBOARD,
                "screen_path": "/dashboard/",
                "title": "Título corrigido",
                "priority": BugReport.Priority.P1,
                "status": BugReport.Status.RETEST,
                "description": "Atualizado fora do sistema",
                "current_result": "A",
                "expected_result": "B",
                "reproduction_steps": "1. Testar",
                "technical_notes": "",
                "resolution_notes": "Patch aplicado",
                "retest_notes": "",
                "app_version": "0.2.2-p1",
                "browser_info": "Chrome",
                "assigned_to": None,
                "attachment": None,
            }],
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bugs.json", json.dumps(payload).encode("utf-8"))
            zf.writestr("BUGS.md", "# Teste")
            zf.writestr("resumo.json", "{}")
        uploaded = SimpleUploadedFile("bugs.zip", stream.getvalue(), content_type="application/zip")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("bug_import"), {"bug_notebook_zip": uploaded})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BugReport.objects.count(), 1)
        bug.refresh_from_db()
        self.assertEqual(bug.title, "Título corrigido")
        self.assertEqual(bug.priority, BugReport.Priority.P1)
        self.assertEqual(bug.status, BugReport.Status.RETEST)

    def test_invalid_import_is_rejected(self):
        self.client.force_login(self.admin)
        uploaded = SimpleUploadedFile("bugs.zip", b"nao-e-zip", content_type="application/zip")
        response = self.client.post(reverse("bug_import"), {"bug_notebook_zip": uploaded})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BugReport.objects.count(), 0)
