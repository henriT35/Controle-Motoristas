from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_v0_9_1_0_ranking_v3")]

    operations = [
        migrations.AddField(
            model_name="systemsettings",
            name="driver_v3_regularity_window_days",
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="systemsettings",
            name="driver_v3_actions_activation_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
