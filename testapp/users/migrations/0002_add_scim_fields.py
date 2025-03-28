# Generated by Django 4.2.16 on 2025-02-27 15:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="scim_external_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default=None,
                help_text="A string that is an identifier for the resource as defined by the provisioning client.",
                max_length=254,
                null=True,
                verbose_name="SCIM External ID",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="scim_id",
            field=models.CharField(
                blank=True,
                default=None,
                help_text="A unique identifier for a SCIM resource as defined by the service provider.",
                max_length=254,
                null=True,
                unique=True,
                verbose_name="SCIM ID",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="scim_username",
            field=models.CharField(
                blank=True,
                db_index=True,
                default=None,
                help_text="A service provider's unique identifier for the user",
                max_length=254,
                null=True,
                verbose_name="SCIM Username",
            ),
        ),
    ]
