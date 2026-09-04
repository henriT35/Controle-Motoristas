from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("core","0001_initial")]
    operations=[
        migrations.AddField(model_name="systemsettings",name="driver_v3_proofs_weight",field=models.DecimalField(decimal_places=2,default=50,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_quality_weight",field=models.DecimalField(decimal_places=2,default=35,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_regularity_weight",field=models.DecimalField(decimal_places=2,default=15,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_exact_recovery_bonus",field=models.DecimalField(decimal_places=2,default=0.30,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_gold_recovery_bonus",field=models.DecimalField(decimal_places=2,default=0.90,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_bonus_cap",field=models.DecimalField(decimal_places=2,default=5.00,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="driver_v3_exact_ignored_penalty",field=models.DecimalField(decimal_places=2,default=0.00,max_digits=5)),
        migrations.AddField(model_name="systemsettings",name="top1_reward_description",field=models.CharField(blank=True,max_length=220)),
        migrations.AddField(model_name="systemsettings",name="top2_reward_description",field=models.CharField(blank=True,max_length=220)),
        migrations.AddField(model_name="systemsettings",name="top3_reward_description",field=models.CharField(blank=True,max_length=220)),
    ]
