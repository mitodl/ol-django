# Generated by Django 4.2.16 on 2025-02-21 20:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("google_sheets_refunds", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="refundrequest",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
