from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ssw.models import ImportRun
from apps.ssw.robot_bridge import RobotArtifact, build_robot_payload, RobotBridgeError
from apps.ssw.robot_service import execute_robot_import


@override_settings(
    SSW_ROBOT_ENABLED=True,
    SSW_ROBOT_UNIT="BEL",
    SSW_ROBOT_OPTION="036",
    SSW_ROBOT_EXCEL="S",
    SSW_ROBOT_REPORT_TYPE="ROMANEIOS_036",
)
class RobotP13IntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="qa-p13", password="test12345")

    def make_run(self):
        return ImportRun.objects.create(
            kind=ImportRun.Kind.HISTORY,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            requested_by=self.user,
            status=ImportRun.Status.QUEUED,
        )

    def test_payload_has_no_credentials(self):
        run = self.make_run()
        payload, _ = build_robot_payload(run)
        self.assertEqual(payload["unit"], "BEL")
        self.assertEqual(payload["report_type"], "ROMANEIOS_036")
        for forbidden in ("password", "senha", "cpf", "username", "usuario", "company", "empresa", "domain"):
            self.assertNotIn(forbidden, {key.lower() for key in payload})

    @patch("apps.ssw.robot_service.import_ssw_delivery_file")
    @patch("apps.ssw.robot_service.run_homologated_robot")
    def test_downloaded_is_handed_to_importer_before_success(self, fake_robot, fake_importer):
        run = self.make_run()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "relatorio_036.sswweb"
            path.write_text("ok", encoding="utf-8")
            fake_robot.return_value = RobotArtifact(path=path, size=2, sha256="abc", result={"robot_status": "DOWNLOADED"})

            def importer(_path, **kwargs):
                current = ImportRun.objects.get(pk=run.pk)
                self.assertEqual(current.status, ImportRun.Status.RUNNING)
                current.status = ImportRun.Status.SUCCESS
                current.save(update_fields=["status"])
                return current, object()

            fake_importer.side_effect = importer
            execute_robot_import(run.pk)
            self.assertTrue(fake_importer.called)
            self.assertEqual(ImportRun.objects.get(pk=run.pk).status, ImportRun.Status.SUCCESS)

    @patch("apps.ssw.robot_service.import_ssw_delivery_file")
    @patch("apps.ssw.robot_service.run_homologated_robot")
    def test_robot_error_blocks_importer(self, fake_robot, fake_importer):
        run = self.make_run()
        fake_robot.side_effect = RobotBridgeError("Falha login", code="AUTH_OR_OPTION_TIMEOUT")
        with self.assertRaises(RobotBridgeError):
            execute_robot_import(run.pk)
        fake_importer.assert_not_called()
        current = ImportRun.objects.get(pk=run.pk)
        self.assertEqual(current.status, ImportRun.Status.ERROR)
        self.assertIn("AUTH_OR_OPTION_TIMEOUT", current.message)
