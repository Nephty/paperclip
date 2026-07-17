from django.urls import path

from . import views

app_name = "pastes"

urlpatterns = [
    path("", views.create, name="create"),
    path("mine/", views.mine, name="mine"),
    path("created/<slug:slug>/", views.created, name="created"),
    path("<slug:slug>/delete/", views.delete, name="delete"),
    path("<slug:slug>/", views.detail, name="detail"),
]
