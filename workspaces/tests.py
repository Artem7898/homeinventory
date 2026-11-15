from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from workspaces.access import active_workspace, accessible_workspaces, can_edit, can_manage, membership_for
from workspaces.models import Membership, Workspace


class WorkspaceAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('owner')
        cls.viewer = get_user_model().objects.create_user('viewer')
        cls.stranger = get_user_model().objects.create_user('stranger')
        cls.root = get_user_model().objects.create_superuser('root', 'root@example.test', None)
        cls.space = Workspace.objects.create(name='Дом')
        cls.other = Workspace.objects.create(name='Чужой дом')
        Membership.objects.create(workspace=cls.space, user=cls.owner, role='owner')
        Membership.objects.create(workspace=cls.space, user=cls.viewer, role='viewer')

    def test_members_see_only_their_workspace(self):
        self.assertQuerySetEqual(accessible_workspaces(self.owner), [self.space])
        self.assertFalse(accessible_workspaces(self.stranger).exists())

    def test_role_gates(self):
        self.assertTrue(can_edit(self.owner, self.space))
        self.assertTrue(can_manage(self.owner, self.space))
        self.assertFalse(can_edit(self.viewer, self.space))
        self.assertFalse(can_manage(self.viewer, self.space))
        self.assertFalse(can_edit(self.owner, self.other))

    def test_editor_cannot_manage_members(self):
        member = membership_for(self.viewer, self.space)
        member.role = 'editor'
        member.save()
        self.assertTrue(can_edit(self.viewer, self.space))
        self.assertFalse(can_manage(self.viewer, self.space))

    def test_superuser_can_review_unclaimed_legacy_space(self):
        self.assertTrue(accessible_workspaces(self.root).filter(pk=self.other.pk).exists())
        self.assertTrue(can_manage(self.root, self.other))

    def test_tampered_session_does_not_select_foreign_space(self):
        request = RequestFactory().get('/')
        request.user = self.owner
        request.session = {'workspace_id': self.other.pk}
        self.assertEqual(active_workspace(request), self.space)
        self.assertEqual(request.session['workspace_id'], self.space.pk)

    def test_inactive_account_loses_membership_access(self):
        self.owner.is_active = False
        self.assertFalse(accessible_workspaces(self.owner).exists())
        self.assertFalse(can_edit(self.owner, self.space))
