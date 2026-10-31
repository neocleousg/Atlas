from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "ΑΤΛΑΣ · Διαχείριση"
admin.site.site_title = "ΑΤΛΑΣ"
admin.site.index_title = "Φορείς, χρήστες και ταξινομίες"

urlpatterns = [
    path("diaxeirisi/", admin.site.urls),
    path("syndesi/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("aposyndesi/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
]
