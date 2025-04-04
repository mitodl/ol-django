# Generated by Django 3.2.13 on 2022-06-14 12:36

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FileWatchRenewalAttempt",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sheet_type",
                    models.CharField(
                        choices=[
                            ("enrollrequest", "enrollrequest"),
                            ("enrollassign", "enrollassign"),
                            ("enrollchange", "enrollchange"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("sheet_file_id", models.CharField(db_index=True, max_length=100)),
                ("date_attempted", models.DateTimeField(auto_now_add=True)),
                ("result", models.CharField(blank=True, max_length=300, null=True)),
                (
                    "result_status_code",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="GoogleFileWatch",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                ("file_id", models.CharField(db_index=True, max_length=100)),
                ("channel_id", models.CharField(db_index=True, max_length=100)),
                ("version", models.IntegerField(blank=True, db_index=True, null=True)),
                ("activation_date", models.DateTimeField()),
                ("expiration_date", models.DateTimeField()),
                ("last_request_received", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "unique_together": {("file_id", "version")},
            },
        ),
        migrations.CreateModel(
            name="GoogleApiAuth",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                ("access_token", models.CharField(max_length=2048)),
                ("refresh_token", models.CharField(max_length=512, null=True)),
                (
                    "requesting_user",
                    models.OneToOneField(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
