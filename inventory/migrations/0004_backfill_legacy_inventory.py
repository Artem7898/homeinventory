"""Keep data updates in their own transaction before PostgreSQL DDL."""
import unicodedata
import uuid

from django.db import migrations


def backfill_legacy(apps, schema_editor):
    alias = schema_editor.connection.alias
    Workspace = apps.get_model('workspaces', 'Workspace')
    Category = apps.get_model('categories', 'Category')
    Location = apps.get_model('locations', 'Location')
    Item = apps.get_model('inventory', 'Item')
    if any(model.objects.using(alias).filter(workspace__isnull=True).exists() for model in (Category, Location, Item)):
        # No membership is granted automatically. A superuser must assign owners
        # explicitly after reviewing the migrated private inventory.
        space = Workspace.objects.using(alias).create(name='Импортированные данные', kind='home')
        for model in (Category, Location, Item):
            model.objects.using(alias).filter(workspace__isnull=True).update(workspace_id=space.pk)
    for item in Item.objects.using(alias).all().iterator():
        text = unicodedata.normalize('NFKC', f'{item.name} {item.description}').casefold()
        Item.objects.using(alias).filter(pk=item.pk).update(label_id=uuid.uuid4(), search_text=text)



class Migration(migrations.Migration):
    dependencies = [('inventory', '0003_loan_movement_publiclisting_alter_item_options_and_more')]
    operations = [migrations.RunPython(backfill_legacy, migrations.RunPython.noop)]
