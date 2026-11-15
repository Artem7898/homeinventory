import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('inventory', '0004_backfill_legacy_inventory')]
    operations = [
        migrations.AlterField(
            model_name='item', name='label_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='item', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
        migrations.AlterField(
            model_name='container', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
        migrations.AlterField(
            model_name='loan', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
        migrations.AlterField(
            model_name='movement', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
        migrations.AlterField(
            model_name='publiclisting', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
    ]
