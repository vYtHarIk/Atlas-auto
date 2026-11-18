from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import TestDriveForm
from .models import (
    CarConfiguration,
    CarInstance,
    CarModel,
    CarReservation,
    Favorite,
    Review,
    TestCar,
    TestDriveBooking,
    TradeInRequest,
    UserProfile,
)

User = get_user_model()


def future_slot(days=2, hour=12):
    moment = timezone.localtime(timezone.now()) + timedelta(days=days)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0)


class SalonTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.model = CarModel.objects.create(
            name="Cayenne",
            brand="Porsche",
            year_introduced=2024,
            body_type="suv",
            description="Тестовая модель",
            image="img/cars/cayenne.png",
        )
        cls.config = CarConfiguration.objects.create(
            model=cls.model,
            name="Cayenne",
            engine_volume=Decimal("3.0"),
            power_hp=353,
            transmission="AT",
            drive_type="AWD",
            year=2025,
            base_price=Decimal("12900000"),
            sort_order=1,
        )
        cls.other_config = CarConfiguration.objects.create(
            model=cls.model,
            name="Cayenne S",
            engine_volume=Decimal("4.0"),
            power_hp=474,
            transmission="AT",
            drive_type="AWD",
            year=2025,
            base_price=Decimal("16500000"),
            sort_order=2,
        )
        cls.instance = CarInstance.objects.create(
            configuration=cls.config,
            vin="WP1ZZZ9YZRDA00001",
            color="Серый металлик",
            status="available",
            year=2025,
        )
        cls.second_instance = CarInstance.objects.create(
            configuration=cls.other_config,
            vin="WP1ZZZ9YZRDA00002",
            color="Чёрный металлик",
            status="available",
            year=2025,
        )
        cls.test_car = TestCar.objects.create(
            model=cls.model, state_number="А001МР77", mileage=1200
        )
        cls.user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="Client12345",
            first_name="Алексей",
            last_name="Смирнов",
        )
        UserProfile.objects.update_or_create(
            user=cls.user, defaults={"phone": "+7 (900) 123-45-67"}
        )

    def test_catalog_renders_and_filters(self):
        response = self.client.get(reverse("autosalon:catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Porsche")
        self.assertEqual(response.context["total"], 2)

        response = self.client.get(
            reverse("autosalon:catalog"), {"price_max": "14000000"}
        )
        self.assertEqual(response.context["total"], 1)
        self.assertEqual(list(response.context["configs"]), [self.config])

    def test_car_detail_and_404(self):
        response = self.client.get(self.config.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WP1ZZZ9YZRDA00001")
        response = self.client.get(reverse("autosalon:car_detail", kwargs={"pk": 9999}))
        self.assertEqual(response.status_code, 404)

    def test_booking_requires_login(self):
        response = self.client.get(reverse("autosalon:test_drive"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("autosalon:login"), response.url)

    def test_register_creates_profile_and_logs_in(self):
        response = self.client.post(
            reverse("autosalon:register"),
            {
                "first_name": "Иван",
                "last_name": "Петров",
                "email": "ivan@example.com",
                "phone": "+7 (900) 111-22-33",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
                "consent": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="ivan@example.com")
        self.assertEqual(user.username, "ivan@example.com")
        self.assertEqual(user.profile.phone, "+7 (900) 111-22-33")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_rejected(self):
        response = self.client.post(
            reverse("autosalon:register"),
            {
                "first_name": "Иван",
                "last_name": "Петров",
                "email": "CLIENT@example.com",
                "phone": "+7 (900) 111-22-33",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
                "consent": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже зарегистрирован")

    def test_login_by_email(self):
        response = self.client.post(
            reverse("autosalon:login"),
            {"username": "client@example.com", "password": "Client12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("autosalon:account"))

    def test_test_drive_booking_and_conflict(self):
        self.client.force_login(self.user)
        moment = future_slot()
        payload = {
            "contact_name": "Алексей Смирнов",
            "contact_phone": "+7 (900) 123-45-67",
            "test_car": self.test_car.pk,
            "booking_datetime": moment.strftime("%Y-%m-%dT%H:%M"),
            "driving_experience_years": 7,
            "comment": "Хочу сравнить",
        }
        response = self.client.post(reverse("autosalon:test_drive"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("autosalon:account_bookings"))
        self.assertTrue(
            TestDriveBooking.objects.filter(
                user=self.user, test_car=self.test_car
            ).exists()
        )

        response = self.client.post(
            reverse("autosalon:test_drive"), payload, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже занят")
        self.assertEqual(TestDriveBooking.objects.filter(user=self.user).count(), 1)

    def test_test_drive_rejects_past_slot(self):
        self.client.force_login(self.user)
        moment = timezone.localtime(timezone.now()) - timedelta(days=1)
        response = self.client.post(
            reverse("autosalon:test_drive"),
            {
                "contact_name": "Алексей",
                "contact_phone": "+7 (900) 123-45-67",
                "test_car": self.test_car.pk,
                "booking_datetime": moment.strftime("%Y-%m-%dT%H:%M"),
                "driving_experience_years": 7,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не раньше чем через час")
        self.assertFalse(TestDriveBooking.objects.exists())

    def test_reservation_create_and_cancel(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "autosalon:reservation_create",
                kwargs={"instance_id": self.instance.pk},
            ),
            {
                "deposit_amount": "60000",
                "payment_method": "sbp",
                "agreement": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, "reserved")
        reservation = CarReservation.objects.get(user=self.user, is_active=True)
        self.assertEqual(reservation.deposit_amount, Decimal("60000"))

        response = self.client.post(
            reverse("autosalon:reservation_cancel", kwargs={"pk": reservation.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.instance.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(self.instance.status, "available")
        self.assertFalse(reservation.is_active)

    def test_reservation_minimum_deposit(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "autosalon:reservation_create",
                kwargs={"instance_id": self.instance.pk},
            ),
            {
                "deposit_amount": "10000",
                "payment_method": "card",
                "agreement": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Минимальная сумма задатка")
        self.assertFalse(CarReservation.objects.exists())

    def test_trade_in_estimate(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("autosalon:trade_in"),
            {
                "brand": "Toyota",
                "model": "Camry",
                "year": 2018,
                "mileage": 96000,
                "comment": "Один владелец",
            },
        )
        self.assertEqual(response.status_code, 302)
        request_obj = TradeInRequest.objects.get(user=self.user)
        self.assertEqual(request_obj.status, "estimated")
        self.assertGreater(request_obj.estimated_price, 0)

    def test_review_is_unique_per_user(self):
        self.client.force_login(self.user)
        url = reverse("autosalon:review_create", kwargs={"pk": self.config.pk})
        self.client.post(url, {"rating": 5, "text": "Отлично"})
        self.client.post(url, {"rating": 4, "text": "Обновлённый отзыв"})
        self.assertEqual(
            Review.objects.filter(configuration=self.config, user=self.user).count(), 1
        )
        review = Review.objects.get(configuration=self.config, user=self.user)
        self.assertEqual(review.rating, 4)
        self.assertIn("Обновлённый", review.text)

    def test_favorite_toggle_json(self):
        self.client.force_login(self.user)
        url = reverse("autosalon:favorite_toggle", kwargs={"pk": self.config.pk})
        response = self.client.post(
            url, HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_favorite"])
        self.assertTrue(Favorite.objects.filter(user=self.user).exists())

        response = self.client.post(
            url, HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json"
        )
        self.assertFalse(response.json()["is_favorite"])
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_account_pages_require_login_and_render(self):
        for name in (
            "account",
            "account_bookings",
            "account_reservations",
            "account_trade_ins",
            "account_favorites",
            "account_profile",
            "account_password",
        ):
            response = self.client.get(reverse(f"autosalon:{name}"))
            self.assertEqual(response.status_code, 302, name)
        self.client.force_login(self.user)
        for name in (
            "account",
            "account_bookings",
            "account_reservations",
            "account_trade_ins",
            "account_favorites",
            "account_profile",
            "account_password",
        ):
            response = self.client.get(reverse(f"autosalon:{name}"))
            self.assertEqual(response.status_code, 200, name)

    def test_profile_update(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("autosalon:account_profile"),
            {
                "first_name": "Алексей",
                "last_name": "Смирнов",
                "email": "client@example.com",
                "phone": "+7 (900) 765-43-21",
                "driving_experience_years": 8,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, "+7 (900) 765-43-21")
        self.assertEqual(self.user.profile.driving_experience_years, 8)

    def test_cancel_booking(self):
        self.client.force_login(self.user)
        booking = TestDriveBooking.objects.create(
            user=self.user,
            test_car=self.test_car,
            booking_datetime=future_slot(3),
            driving_experience_years=7,
            status="confirmed",
        )
        response = self.client.post(
            reverse("autosalon:booking_cancel", kwargs={"pk": booking.pk})
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "cancelled")
