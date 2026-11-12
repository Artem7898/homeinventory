from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from workspaces.models import Membership, Workspace


class Command(BaseCommand):
    help = "Явно назначить владельца пространства; выполнять только оператору сервера."

    def add_arguments(self, parser):
        parser.add_argument("workspace_id", type=int)
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            space = Workspace.objects.get(pk=options["workspace_id"])
            user = get_user_model().objects.get(username=options["username"], is_active=True)
        except (Workspace.DoesNotExist, get_user_model().DoesNotExist) as exc:
            raise CommandError("Пространство или активный пользователь не найдены.") from exc
        Membership.objects.update_or_create(workspace=space, user=user, defaults={"role": "owner"})
        self.stdout.write(self.style.SUCCESS(f"Владелец назначен для пространства {space.pk}."))
