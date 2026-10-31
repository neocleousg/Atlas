from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("programmata/", views.ProgrammeListView.as_view(), name="programme_list"),
    path("programmata/neo/", views.ProgrammeCreateView.as_view(), name="programme_create"),
    path("programmata/<int:pk>/", views.ProgrammeDetailView.as_view(), name="programme_detail"),
    path("programmata/<int:pk>/epexergasia/", views.ProgrammeUpdateView.as_view(), name="programme_update"),
]
