# Generated by Django 4.2.16 on 2025-02-21 20:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("google_sheets", "0002_alter_filewatchrenewalattempt_sheet_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="filewatchrenewalattempt",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="googleapiauth",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AlterField(
            model_name="googlefilewatch",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
