from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("programmata/", views.ProgrammeListView.as_view(), name="programme_list"),
    path("programmata/<int:pk>/", views.ProgrammeHomeView.as_view(), name="programme_home"),
    path("programmata/<int:pk>/dilosi/", views.DeclarationView.as_view(), name="declaration_start"),
    path("programmata/<int:pk>/dilosi/<int:step>/", views.DeclarationView.as_view(), name="declaration"),
    path("aaek/", views.AaekDashboardView.as_view(), name="aaek_dashboard"),
    path("aaek/exagogi.csv", views.AaekExportView.as_view(), name="aaek_export"),
    path("aaek/demo-epanafora/", views.DemoResetView.as_view(), name="demo_reset"),
]
