# Generated by Django 3.2.13 on 2022-06-17 14:47  # noqa: D100

from django.db import migrations, models


class Migration(migrations.Migration):  # noqa: D101
    dependencies = [  # noqa: RUF012
        ("google_sheets", "0001_initial"),
    ]

    operations = [  # noqa: RUF012
        migrations.AlterField(
            model_name="filewatchrenewalattempt",
            name="sheet_type",
            field=models.CharField(db_index=True, max_length=30),
        ),
    ]
