from django.db import migrations


def open_ended(apps, schema_editor):
    """Students with no access window used to be silently locked out; make them open-ended."""
    User = apps.get_model("avto", "User")
    User.objects.filter(
        is_staff=False, is_superuser=False, unlimited=False, account_expires_at__isnull=True,
    ).update(unlimited=True)


class Migration(migrations.Migration):
    dependencies = [("avto", "0013_group_lesson_time")]
    operations = [migrations.RunPython(open_ended, migrations.RunPython.noop)]
