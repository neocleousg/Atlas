from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.forms import AtlasAdminAuthenticationForm, AtlasAuthenticationForm

admin.site.site_header = "ΑΤΛΑΣ · Διαχείριση"
admin.site.site_title = "ΑΤΛΑΣ"
admin.site.index_title = "Φορείς, χρήστες και ταξινομίες"
admin.site.login_form = AtlasAdminAuthenticationForm

urlpatterns = [
    path("diaxeirisi/", admin.site.urls),
    path(
        "syndesi/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True, authentication_form=AtlasAuthenticationForm),
        name="login",
    ),
    path("aposyndesi/", auth_views.LogoutView.as_view(), name="logout"),
    path("kodikos/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("kodikos/ok/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("", include("core.urls")),
]
