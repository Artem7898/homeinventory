from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('locations', '0002_alter_location_options_location_parent_and_more'),
        ('inventory', '0005_require_workspace_and_labels'),
    ]
    operations = [
        migrations.AlterField(
            model_name='location', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
    ]
