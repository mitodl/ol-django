# Generated by Django 5.1.7 on 2025-03-31 19:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_add_timestamps"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="global_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
