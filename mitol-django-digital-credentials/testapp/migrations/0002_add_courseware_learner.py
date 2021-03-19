# Generated by Django 3.1.5 on 2021-03-19 17:28

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("testapp", "0001_add_courseware_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="democourseware",
            name="learner",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
