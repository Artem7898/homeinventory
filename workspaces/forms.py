from django import forms
from django.contrib.auth import get_user_model
from .models import Membership, Workspace


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name', 'kind']


class MembershipForm(forms.Form):
    username = forms.CharField(label='Имя существующего пользователя', max_length=150)
    role = forms.ChoiceField(label='Роль', choices=Membership.Role.choices)

    def clean_username(self):
        value = self.cleaned_data['username']
        try:
            self.user = get_user_model().objects.get(username=value, is_active=True)
        except get_user_model().DoesNotExist:
            raise forms.ValidationError('Активный пользователь с таким именем не найден.') from None
        return value
