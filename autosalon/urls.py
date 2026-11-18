from django.urls import path

from . import views

app_name = "autosalon"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<slug:slug>/", views.car_detail, name="car_detail"),
    path("test-drive/", views.test_drive, name="test_drive"),
    path("trade-in/", views.trade_in, name="trade_in"),
    path("about/", views.about, name="about"),
    path("contacts/", views.contacts, name="contacts"),
    path("register/", views.register, name="register"),
    path("privacy/", views.privacy, name="privacy"),
]
