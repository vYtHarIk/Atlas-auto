from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "autosalon"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<int:pk>/", views.car_detail, name="car_detail"),
    path("test-drive/", views.test_drive, name="test_drive"),
    path("trade-in/", views.trade_in, name="trade_in"),
    path("reservation/", views.reservation_lookup, name="reservation_lookup"),
    path(
        "reservation/<int:instance_id>/",
        views.reservation_create,
        name="reservation_create",
    ),
    path("about/", views.about, name="about"),
    path("contacts/", views.contacts, name="contacts"),
    path("privacy/", views.privacy, name="privacy"),
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="autosalon/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="autosalon:home"),
        name="logout",
    ),
    path("account/", views.account_dashboard, name="account"),
    path("account/bookings/", views.account_bookings, name="account_bookings"),
    path(
        "account/bookings/<int:pk>/cancel/",
        views.booking_cancel,
        name="booking_cancel",
    ),
    path(
        "account/reservations/",
        views.account_reservations,
        name="account_reservations",
    ),
    path(
        "account/reservations/<int:pk>/cancel/",
        views.reservation_cancel,
        name="reservation_cancel",
    ),
    path("account/trade-ins/", views.account_trade_ins, name="account_trade_ins"),
    path("account/favorites/", views.account_favorites, name="account_favorites"),
    path("account/profile/", views.account_profile, name="account_profile"),
    path("account/password/", views.account_password, name="account_password"),
    path(
        "cars/<int:pk>/favorite/",
        views.favorite_toggle,
        name="favorite_toggle",
    ),
    path("cars/<int:pk>/review/", views.review_create, name="review_create"),
]
