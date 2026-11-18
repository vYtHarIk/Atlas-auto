"""Демонстрационные данные для каталога, кабинета и тестов.

Запуск:
    python manage.py seed_demo

Команда идемпотентна: повторный запуск обновляет справочники, но не создаёт
дубликаты автомобилей, записей и пользователей.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from autosalon.models import (
    CarConfiguration,
    CarInstance,
    CarModel,
    CarOption,
    CarReservation,
    ConfigurationOption,
    Favorite,
    Review,
    TestCar,
    TestDriveBooking,
    TradeInRequest,
    UserProfile,
)

User = get_user_model()

MODELS = [
    {
        "name": "Cayenne",
        "brand": "Porsche",
        "year_introduced": 2024,
        "body_type": "suv",
        "image": "img/cars/cayenne.png",
        "description": (
            "Спортивный внедорожник, который одинаково уверенно чувствует себя "
            "в городе и на трассе. Пневмоподвеска, полный привод и характер Porsche."
        ),
        "colors": ["Серый металлик", "Чёрный металлик"],
        "configurations": [
            {
                "name": "Cayenne",
                "engine_volume": Decimal("3.0"),
                "power_hp": 353,
                "transmission": "AT",
                "drive_type": "AWD",
                "year": 2025,
                "base_price": Decimal("12900000"),
                "sort_order": 1,
            },
            {
                "name": "Cayenne S",
                "engine_volume": Decimal("4.0"),
                "power_hp": 474,
                "transmission": "AT",
                "drive_type": "AWD",
                "year": 2025,
                "base_price": Decimal("16500000"),
                "sort_order": 4,
            },
        ],
    },
    {
        "name": "E-Класс",
        "brand": "Mercedes-Benz",
        "year_introduced": 2024,
        "body_type": "sedan",
        "image": "img/cars/e-class.png",
        "description": (
            "Бизнес-седан с эталонным комфортом, цифровым кокпитом MBUX "
            "и мягкой подвеской, которая делает дорогу незаметной."
        ),
        "colors": ["Чёрный металлик", "Белый перламутр"],
        "configurations": [
            {
                "name": "E 200",
                "engine_volume": Decimal("2.0"),
                "power_hp": 197,
                "transmission": "AT",
                "drive_type": "RWD",
                "year": 2025,
                "base_price": Decimal("9800000"),
                "sort_order": 2,
            },
            {
                "name": "E 300",
                "engine_volume": Decimal("2.0"),
                "power_hp": 258,
                "transmission": "AT",
                "drive_type": "AWD",
                "year": 2025,
                "base_price": Decimal("12200000"),
                "sort_order": 5,
            },
        ],
    },
    {
        "name": "X5",
        "brand": "BMW",
        "year_introduced": 2024,
        "body_type": "suv",
        "image": "img/cars/bmw-x5.png",
        "description": (
            "Полноразмерный кроссовер с точной управляемостью, "
            "шестицилиндровым двигателем и премиальным салоном."
        ),
        "colors": ["Белый перламутр", "Чёрный металлик"],
        "configurations": [
            {
                "name": "xDrive40i",
                "engine_volume": Decimal("3.0"),
                "power_hp": 381,
                "transmission": "AT",
                "drive_type": "AWD",
                "year": 2025,
                "base_price": Decimal("11500000"),
                "sort_order": 3,
            },
            {
                "name": "M60i",
                "engine_volume": Decimal("4.4"),
                "power_hp": 530,
                "transmission": "AT",
                "drive_type": "AWD",
                "year": 2025,
                "base_price": Decimal("17800000"),
                "sort_order": 6,
            },
        ],
    },
]

OPTIONS = [
    ("Комплект зимних шин", Decimal("80000"), True),
    ("Сигнализация с автозапуском", Decimal("45000"), True),
    ("Коврики в салон", Decimal("12000"), True),
    ("Защита картера", Decimal("18000"), False),
    ("Антикоррозийная обработка", Decimal("35000"), False),
    ("Панорамная крыша", Decimal("180000"), False),
    ("Аудиосистема Burmester", Decimal("350000"), False),
    ("Пакет ассистентов водителя", Decimal("220000"), False),
]


class Command(BaseCommand):
    help = "Создаёт демонстрационные автомобили, записи и аккаунты"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-demo-user",
            action="store_true",
            help="Не создавать демонстрационного клиента и его записи",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        options_map = self._options()
        configs = self._cars(options_map)
        self._test_cars(configs)
        if not options.get("no_demo_user"):
            self._demo_users(configs, options)
        self._reconcile_reservations()

    def _reconcile_reservations(self):
        """Приводит статус автомобиля в соответствие с активной бронью."""
        for car in CarInstance.objects.filter(status__in=("available", "reserved")):
            active = car.reservations.filter(is_active=True).first()
            desired = "reserved" if active else "available"
            if car.status != desired:
                car.status = desired
                car.reserved_until = active.expires_at if active else None
                car.save(update_fields=["status", "reserved_until"])

    def _options(self):
        result = {}
        for name, price, is_standard in OPTIONS:
            option, _ = CarOption.objects.update_or_create(
                name=name, defaults={"price": price}
            )
            result[name] = (option, is_standard)
        return result

    def _cars(self, options_map):
        configs = {}
        for index, model_data in enumerate(MODELS):
            model, _ = CarModel.objects.update_or_create(
                name=model_data["name"],
                defaults={
                    "brand": model_data["brand"],
                    "year_introduced": model_data["year_introduced"],
                    "body_type": model_data["body_type"],
                    "description": model_data["description"],
                    "image": model_data["image"],
                },
            )
            for conf_index, conf_data in enumerate(model_data["configurations"]):
                config, _ = CarConfiguration.objects.update_or_create(
                    model=model,
                    name=conf_data["name"],
                    defaults={
                        "engine_volume": conf_data["engine_volume"],
                        "power_hp": conf_data["power_hp"],
                        "transmission": conf_data["transmission"],
                        "drive_type": conf_data["drive_type"],
                        "year": conf_data["year"],
                        "base_price": conf_data["base_price"],
                        "sort_order": conf_data["sort_order"],
                    },
                )
                configs[config.name] = config
                self._instances(config, index * 10 + conf_index, model_data["colors"])
                self._config_options(config, conf_index, options_map)
        return configs

    def _instances(self, config, seed, colors):
        model_code = config.model.brand[:3].upper().replace("-", "X")
        for number in range(2):
            vin = f"{model_code}{config.pk:02d}ATLAS{seed:02d}{number:02d}"[:17].ljust(
                17, "0"
            )
            status = "available"
            if config.name in {"Cayenne S", "E 300", "M60i"}:
                status = "on_order"
            instance, created = CarInstance.objects.get_or_create(
                vin=vin,
                defaults={
                    "configuration": config,
                    "color": colors[number % len(colors)],
                    "status": status,
                    "year": config.year,
                    "condition": "new",
                    "mileage": 0,
                },
            )
            if not created and instance.color != colors[number % len(colors)]:
                instance.color = colors[number % len(colors)]
                instance.save(update_fields=["color"])

    def _config_options(self, config, conf_index, options_map):
        names = list(options_map)
        # Базовые опции входят в каждую комплектацию, часть — только в топ.
        selected = names[:3] + (names[3:6] if conf_index else names[3:4])
        for name in selected:
            option, is_standard = options_map[name]
            ConfigurationOption.objects.update_or_create(
                configuration=config,
                option=option,
                defaults={"is_standard": is_standard and name in names[:3]},
            )

    def _test_cars(self, configs):
        for index, config in enumerate(configs.values(), start=1):
            TestCar.objects.update_or_create(
                model=config.model,
                defaults={
                    "state_number": f"А{index:03d}МР77",
                    "mileage": 3500 + index * 750,
                    "is_active": True,
                },
            )

    def _demo_users(self, configs, options_map):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@atlas-auto.ru",
                "first_name": "Администратор",
                "last_name": "Салона",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("Admin12345")
            admin.save()
            self.stdout.write("Создан администратор admin / Admin12345")

        manager, created = User.objects.get_or_create(
            username="manager@atlas-auto.ru",
            defaults={
                "email": "manager@atlas-auto.ru",
                "first_name": "Ирина",
                "last_name": "Волкова",
                "is_staff": True,
            },
        )
        if created:
            manager.set_password("Manager12345")
            manager.save()
        UserProfile.objects.update_or_create(
            user=manager, defaults={"phone": "+7 (495) 000-00-01"}
        )

        client, created = User.objects.get_or_create(
            username="client@example.com",
            defaults={
                "email": "client@example.com",
                "first_name": "Алексей",
                "last_name": "Смирнов",
            },
        )
        if created:
            client.set_password("Client12345")
            client.save()
            self.stdout.write("Создан клиент client@example.com / Client12345")
        UserProfile.objects.update_or_create(
            user=client,
            defaults={"phone": "+7 (900) 123-45-67", "driving_experience_years": 7},
        )

        tomorrow = timezone.localtime(timezone.now()) + timedelta(days=1)
        slot_one = timezone.make_aware(
            datetime.combine(tomorrow.date(), time(10, 0)),
            timezone.get_current_timezone(),
        )
        slot_two = timezone.make_aware(
            datetime.combine((tomorrow + timedelta(days=2)).date(), time(14, 0)),
            timezone.get_current_timezone(),
        )

        for config_name, moment, status in (
            ("Cayenne", slot_one, "confirmed"),
            ("E 200", slot_two, "pending"),
        ):
            config = configs.get(config_name)
            if not config:
                continue
            test_car = TestCar.objects.filter(model=config.model).first()
            if not test_car:
                continue
            TestDriveBooking.objects.get_or_create(
                test_car=test_car,
                booking_datetime=moment,
                defaults={
                    "user": client,
                    "manager": manager,
                    "driving_experience_years": 7,
                    "status": status,
                    "comment": "Хочу сравнить комплектации.",
                },
            )

        reservation_car = None
        active_reservation = (
            CarReservation.objects.filter(user=client, is_active=True)
            .select_related("car_instance")
            .first()
        )
        if active_reservation:
            reservation_car = active_reservation.car_instance
        elif "Cayenne" in configs:
            reservation_car = CarInstance.objects.filter(
                configuration=configs["Cayenne"], status="available"
            ).first()
        if reservation_car:
            reservation, created = CarReservation.objects.get_or_create(
                car_instance=reservation_car,
                is_active=True,
                defaults={
                    "user": client,
                    "deposit_amount": Decimal("50000"),
                    "payment_method": "card",
                    "expires_at": timezone.now() + timedelta(days=4),
                },
            )
            if created:
                reservation_car.status = "reserved"
                reservation_car.reserved_until = reservation.expires_at
                reservation_car.save(update_fields=["status", "reserved_until"])

        if "E 200" in configs:
            TradeInRequest.objects.get_or_create(
                user=client,
                brand="Toyota",
                model="Camry",
                year=2018,
                mileage=96000,
                defaults={"comment": "Один владелец, регулярное обслуживание."},
            )

        for config in list(configs.values())[:2]:
            Favorite.objects.get_or_create(user=client, configuration=config)

        if "Cayenne" in configs:
            Review.objects.update_or_create(
                configuration=configs["Cayenne"],
                user=client,
                defaults={
                    "rating": 5,
                    "text": (
                        "Отличный автомобиль: мощный, но при этом комфортный. "
                        "Тест-драйв помог определиться с комплектацией."
                    ),
                },
            )
