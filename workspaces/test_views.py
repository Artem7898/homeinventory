from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Membership, Workspace


class WorkspaceViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner')
        self.viewer = User.objects.create_user(username='viewer')
        self.new_user = User.objects.create_user(username='new')
        self.workspace = Workspace.objects.create(name='Home')
        self.owner_member = Membership.objects.create(workspace=self.workspace, user=self.owner, role='owner')
        Membership.objects.create(workspace=self.workspace, user=self.viewer, role='viewer')
        self.client.force_login(self.owner)
        self.members_url = reverse('workspaces:members', args=[self.workspace.pk])

    def test_create_workspace_grants_only_creator_ownership(self):
        response = self.client.post(reverse('workspaces:workspace-create'), {'name': 'Workshop', 'kind': 'workshop'})
        self.assertEqual(response.status_code, 302)
        workspace = Workspace.objects.get(name='Workshop')
        self.assertEqual(list(workspace.memberships.values_list('user_id', 'role')), [(self.owner.pk, 'owner')])
        self.assertEqual(self.client.session['workspace_id'], workspace.pk)

    def test_owner_adds_existing_user_and_updates_role(self):
        self.assertEqual(self.client.post(self.members_url, {'username': 'new', 'role': 'editor'}).status_code, 302)
        self.assertEqual(Membership.objects.get(workspace=self.workspace, user=self.new_user).role, 'editor')
        self.assertEqual(self.client.post(self.members_url, {'username': 'new', 'role': 'viewer'}).status_code, 302)
        self.assertEqual(Membership.objects.get(workspace=self.workspace, user=self.new_user).role, 'viewer')

    def test_viewer_cannot_manage_members_or_promote_self(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.members_url).status_code, 403)
        self.assertEqual(self.client.post(self.members_url, {'username': 'viewer', 'role': 'owner'}).status_code, 403)
        self.assertEqual(Membership.objects.get(workspace=self.workspace, user=self.viewer).role, 'viewer')

    def test_cannot_remove_or_demote_last_owner(self):
        response = self.client.post(self.members_url, {'username': 'owner', 'role': 'viewer'})
        self.assertEqual(response.status_code, 400)
        url = reverse('workspaces:member-remove', args=[self.workspace.pk, self.owner_member.pk])
        self.assertEqual(self.client.post(url).status_code, 400)
        self.owner_member.refresh_from_db()
        self.assertEqual(self.owner_member.role, 'owner')

    def test_can_remove_member_and_access_is_revoked(self):
        membership = Membership.objects.get(user=self.viewer, workspace=self.workspace)
        url = reverse('workspaces:member-remove', args=[self.workspace.pk, membership.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(list(self.client.get('/spaces/').context['workspaces']), [])
        self.assertEqual(self.client.post(reverse('workspaces:workspace-select', args=[self.workspace.pk])).status_code, 404)

    def test_unknown_user_is_validation_error(self):
        self.assertEqual(self.client.post(self.members_url, {'username': 'missing', 'role': 'viewer'}).status_code, 400)
        self.assertEqual(self.workspace.memberships.count(), 2)
