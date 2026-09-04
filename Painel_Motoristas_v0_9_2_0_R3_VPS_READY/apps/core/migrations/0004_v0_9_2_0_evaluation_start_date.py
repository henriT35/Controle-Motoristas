from datetime import date

from django.db import migrations


def set_v3_start_date(apps, schema_editor):
    SystemSettings = apps.get_model("core", "SystemSettings")
    obj, _ = SystemSettings.objects.get_or_create(pk=1)
    # A avaliação oficial desta implantação começa em setembro/2026. Corrige
    # também instalações que inicializaram o marco em 03/09 durante homologação.
    if obj.driver_v3_actions_activation_date is None or obj.driver_v3_actions_activation_date > date(2026, 9, 1):
        obj.driver_v3_actions_activation_date = date(2026, 9, 1)
        obj.save(update_fields=["driver_v3_actions_activation_date"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0003_v0_9_2_0_evaluation_settings")]

    operations = [
        migrations.RunPython(set_v3_start_date, noop_reverse),
    ]
