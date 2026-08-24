"""Make global_id unique, with unset stored as NULL rather than "".

Split into three steps deliberately. The column currently defaults to "", so
any estate with more than one unlinked user has duplicate empty strings in it,
and adding the unique constraint in one AlterField would fail on them. Widen
to NULL first, migrate the empty strings across, then constrain.

Consumers of UserGlobalIdMixin need the same three steps. Check for duplicate
non-empty global_ids before running it - those are genuinely forked accounts
and the constraint will refuse them, which is the point.
"""

from django.db import migrations, models


def empty_string_to_null(apps, schema_editor):
    """Move unset global_ids from "" to NULL so the constraint can be added."""
    User = apps.get_model("users", "User")
    User.objects.filter(global_id="").update(global_id=None)


def null_to_empty_string(apps, schema_editor):
    """Reverse of empty_string_to_null."""
    User = apps.get_model("users", "User")
    User.objects.filter(global_id__isnull=True).update(global_id="")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_alter_user_global_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="global_id",
            field=models.CharField(
                blank=True,
                default=None,
                help_text="The SSO ID (usually a Keycloak UUID) for the user.",
                max_length=36,
                null=True,
            ),
        ),
        migrations.RunPython(empty_string_to_null, null_to_empty_string),
        migrations.AlterField(
            model_name="user",
            name="global_id",
            field=models.CharField(
                blank=True,
                default=None,
                help_text="The SSO ID (usually a Keycloak UUID) for the user.",
                max_length=36,
                null=True,
                unique=True,
            ),
        ),
    ]
