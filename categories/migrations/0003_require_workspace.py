from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('categories', '0002_alter_category_options_category_workspace'),
        ('inventory', '0005_require_workspace_and_labels'),
    ]
    operations = [
        migrations.AlterField(
            model_name='category', name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='workspaces.workspace'),
        ),
    ]
