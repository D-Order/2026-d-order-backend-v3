import uuid
from django.db import migrations, models


def generate_unique_public_ids(apps, schema_editor):
    Booth = apps.get_model('booth', 'Booth')
    for booth in Booth.objects.all():
        booth.public_id = uuid.uuid4()
        booth.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('booth', '0005_alter_booth_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='booth',
            name='public_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(generate_unique_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='booth',
            name='public_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
