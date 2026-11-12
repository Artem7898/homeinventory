from django.urls import path
from . import views

app_name = 'workspaces'
urlpatterns = [
    path('', views.workspace_list, name='workspace-list'),
    path('add/', views.workspace_create, name='workspace-create'),
    path('<int:pk>/select/', views.workspace_select, name='workspace-select'),
    path('<int:pk>/members/', views.members, name='members'),
    path('<int:pk>/members/<int:member_pk>/remove/', views.member_remove, name='member-remove'),
]
