from django.urls import path

from . import views

urlpatterns = [
    path("", views.bug_list, name="bugs"),
    path("exportar/", views.bug_export, name="bug_export"),
    path("importar/", views.bug_import, name="bug_import"),
    path("<int:pk>/editar/", views.bug_edit, name="bug_edit"),
]
