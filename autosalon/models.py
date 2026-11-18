from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

BODY_TYPES = [
    ("sedan", "Седан"),
    ("suv", "Внедорожник"),
    ("coupe", "Купе"),
    ("wagon", "Универсал"),
    ("hatchback", "Хэтчбек"),
]

TRANSMISSIONS = [("AT", "Автомат"), ("MT", "Механика")]

DRIVE_TYPES = [
    ("FWD", "Передний привод"),
    ("RWD", "Задний привод"),
    ("AWD", "Полный привод"),
]

INSTANCE_STATUSES = [
    ("available", "В наличии"),
    ("reserved", "Забронирован"),
    ("sold", "Продан"),
    ("on_order", "В поставке"),
]

CONDITIONS = [("new", "Новый"), ("used", "С пробегом")]

BOOKING_STATUSES = [
    ("pending", "Ожидает подтверждения"),
    ("confirmed", "Подтверждена"),
    ("completed", "Проведена"),
    ("cancelled", "Отменена"),
]

TRADE_IN_STATUSES = [
    ("new", "Новая"),
    ("estimated", "Оценена"),
    ("accepted", "Принята"),
    ("rejected", "Отклонена"),
]

PAYMENT_METHODS = [("card", "Банковская карта"), ("sbp", "СБП")]

RESERVATION_DEPOSIT_MIN = 50_000
RESERVATION_DAYS = 5
TEST_DRIVE_MIN_EXPERIENCE = 2
TEST_DRIVE_SLOT_MINUTES = 60


def validate_file_size(value):
    """Не больше 5 МБ на фотографию."""
    limit = 5 * 1024 * 1024
    if value.size > limit:
        raise ValidationError("Размер файла не должен превышать 5 МБ.")


vin_validator = RegexValidator(
    regex=r"^[A-HJ-NPR-Z0-9]{17}$",
    message="VIN состоит из 17 символов: латинские буквы и цифры.",
)


class CarModel(models.Model):
    name = models.CharField("Название модели", max_length=100, unique=True)
    brand = models.CharField("Марка", max_length=50)
    year_introduced = models.PositiveIntegerField(
        "Год начала выпуска",
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
    )
    body_type = models.CharField(
        "Тип кузова", max_length=20, choices=BODY_TYPES, default="sedan"
    )
    description = models.TextField("Описание", blank=True)
    image = models.CharField(
        "Изображение",
        max_length=200,
        default="img/cars/cayenne.png",
        help_text="Путь к файлу в каталоге static/",
    )

    class Meta:
        verbose_name = "Модель автомобиля"
        verbose_name_plural = "Модели автомобилей"
        ordering = ["brand", "name"]

    def __str__(self):
        return f"{self.brand} {self.name}"

    @property
    def title(self):
        return f"{self.brand} {self.name}"


class CarConfiguration(models.Model):
    model = models.ForeignKey(
        CarModel,
        on_delete=models.CASCADE,
        related_name="configurations",
        verbose_name="Модель",
    )
    name = models.CharField("Название комплектации", max_length=100)
    engine_volume = models.DecimalField(
        "Объём двигателя, л",
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.1)],
    )
    power_hp = models.PositiveSmallIntegerField(
        "Мощность, л. с.", validators=[MinValueValidator(1)]
    )
    transmission = models.CharField(
        "Коробка передач", max_length=2, choices=TRANSMISSIONS, default="AT"
    )
    drive_type = models.CharField(
        "Привод", max_length=3, choices=DRIVE_TYPES, default="AWD"
    )
    year = models.PositiveSmallIntegerField(
        "Модельный год",
        validators=[MinValueValidator(1950), MaxValueValidator(2100)],
    )
    base_price = models.DecimalField(
        "Базовая цена, ₽",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    sort_order = models.PositiveSmallIntegerField(
        "Порядок вывода", default=0, help_text="Меньше — выше в каталоге."
    )

    class Meta:
        verbose_name = "Комплектация"
        verbose_name_plural = "Комплектации"
        ordering = ["sort_order", "model__brand", "model__name", "base_price"]
        constraints = [
            models.UniqueConstraint(
                fields=["model", "name"], name="unique_configuration_per_model"
            )
        ]

    def __str__(self):
        return f"{self.model} — {self.name}"

    @property
    def display_name(self):
        return self.model.title

    @property
    def full_name(self):
        return f"{self.model.title} {self.name}"

    @property
    def specs(self):
        return (
            f"{self.engine_volume} {self.transmission} · "
            f"{self.power_hp} л. с. · {self.get_drive_type_display()}"
        )

    def get_absolute_url(self):
        return reverse("autosalon:car_detail", kwargs={"pk": self.pk})

    def available_instance(self):
        instances = list(self.instances.all())
        for car in instances:
            if car.is_available:
                return car
        return instances[0] if instances else None

    @property
    def primary_instance(self):
        return self.available_instance()

    @property
    def price(self):
        instance = self.available_instance()
        if instance and instance.price:
            return instance.price
        return self.base_price

    @property
    def status_label(self):
        instances = list(self.instances.all())
        if any(car.is_available for car in instances):
            return "В наличии"
        if any(car.status == "on_order" for car in instances):
            return "В поставке"
        return "Нет в наличии"


class CarInstance(models.Model):
    configuration = models.ForeignKey(
        CarConfiguration,
        on_delete=models.CASCADE,
        related_name="instances",
        verbose_name="Комплектация",
    )
    vin = models.CharField(
        "VIN-номер", max_length=17, unique=True, validators=[vin_validator]
    )
    color = models.CharField("Цвет", max_length=50)
    status = models.CharField(
        "Статус", max_length=20, choices=INSTANCE_STATUSES, default="available"
    )
    reserved_until = models.DateTimeField("Забронирован до", null=True, blank=True)
    mileage = models.PositiveIntegerField("Пробег, км", default=0)
    year = models.PositiveSmallIntegerField(
        "Год выпуска",
        validators=[MinValueValidator(1950), MaxValueValidator(2100)],
    )
    condition = models.CharField(
        "Состояние", max_length=10, choices=CONDITIONS, default="new"
    )
    price = models.DecimalField(
        "Цена, ₽",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Если не заполнено, используется базовая цена комплектации.",
    )

    class Meta:
        verbose_name = "Автомобиль на складе"
        verbose_name_plural = "Автомобили на складе"
        ordering = ["configuration", "vin"]

    def __str__(self):
        return f"{self.configuration} [{self.vin}]"

    @property
    def final_price(self):
        return self.price if self.price is not None else self.configuration.base_price

    @property
    def is_available(self):
        if self.status == "available":
            return True
        if self.status == "reserved" and self.reserved_until:
            return self.reserved_until <= timezone.now()
        return False

    @property
    def is_new(self):
        return self.condition == "new"


class TestCar(models.Model):
    model = models.ForeignKey(
        CarModel,
        on_delete=models.CASCADE,
        related_name="test_cars",
        verbose_name="Модель",
    )
    state_number = models.CharField(
        "Гос. номер", max_length=20, unique=True
    )
    mileage = models.PositiveIntegerField("Пробег, км", default=0)
    is_active = models.BooleanField("Доступен для теста", default=True)

    class Meta:
        verbose_name = "Тестовый автомобиль"
        verbose_name_plural = "Тестовые автомобили"
        ordering = ["model__brand", "model__name"]

    def __str__(self):
        return f"{self.model} [{self.state_number}]"


class TestDriveBooking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="test_drive_bookings",
        verbose_name="Клиент",
    )
    test_car = models.ForeignKey(
        TestCar,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Тестовый автомобиль",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_bookings",
        verbose_name="Менеджер",
    )
    booking_datetime = models.DateTimeField("Дата и время")
    driving_experience_years = models.PositiveSmallIntegerField(
        "Стаж вождения, лет",
        validators=[MinValueValidator(0), MaxValueValidator(70)],
    )
    status = models.CharField(
        "Статус", max_length=20, choices=BOOKING_STATUSES, default="pending"
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Запись на тест-драйв"
        verbose_name_plural = "Записи на тест-драйв"
        ordering = ["-booking_datetime"]
        indexes = [
            models.Index(fields=["test_car", "booking_datetime"]),
            models.Index(fields=["manager", "booking_datetime"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["test_car", "booking_datetime"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_test_drive_slot",
            )
        ]

    def __str__(self):
        return (
            f"Тест-драйв {self.test_car.model} для {self.user} "
            f"на {self.booking_datetime:%d.%m.%Y %H:%M}"
        )

    @property
    def is_active(self):
        return self.status in ("pending", "confirmed")

    @property
    def is_past(self):
        return self.booking_datetime < timezone.now()


class TradeInRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trade_in_requests",
        verbose_name="Владелец",
    )
    brand = models.CharField("Марка автомобиля", max_length=50)
    model = models.CharField("Модель автомобиля", max_length=50)
    year = models.PositiveSmallIntegerField(
        "Год выпуска",
        validators=[MinValueValidator(1950), MaxValueValidator(2100)],
    )
    mileage = models.PositiveIntegerField("Пробег, км")
    comment = models.TextField("Комментарий", blank=True)
    estimated_price = models.DecimalField(
        "Оценка, ₽", max_digits=12, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        "Статус", max_length=20, choices=TRADE_IN_STATUSES, default="new"
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Заявка на трейд-ин"
        verbose_name_plural = "Заявки на трейд-ин"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand} {self.model}, {self.year} — {self.user}"

    def calculate_estimate(self):
        """Предварительная оценка: возраст автомобиля и пробег."""
        current_year = timezone.now().year
        age = max(0, current_year - self.year)
        base = 2_200_000
        price = base * (0.88**age) - self.mileage * 1.2
        return max(150_000, int(round(price / 1000) * 1000))

    def save(self, *args, **kwargs):
        if self.estimated_price is None:
            self.estimated_price = self.calculate_estimate()
            if self.status == "new":
                self.status = "estimated"
        super().save(*args, **kwargs)


class TradeInPhoto(models.Model):
    request = models.ForeignKey(
        TradeInRequest,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Заявка",
    )
    image = models.FileField(
        "Фотография",
        upload_to="trade_in/%Y/%m/",
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_file_size,
        ],
    )
    uploaded_at = models.DateTimeField("Загружена", auto_now_add=True)

    class Meta:
        verbose_name = "Фотография автомобиля"
        verbose_name_plural = "Фотографии автомобилей"

    def __str__(self):
        return f"Фото к заявке №{self.request_id}"


class CarReservation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name="Покупатель",
    )
    car_instance = models.ForeignKey(
        CarInstance,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="Автомобиль",
    )
    deposit_amount = models.DecimalField(
        "Сумма задатка, ₽",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(RESERVATION_DEPOSIT_MIN)],
    )
    payment_method = models.CharField(
        "Способ оплаты", max_length=10, choices=PAYMENT_METHODS, default="card"
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    expires_at = models.DateTimeField("Срок действия до")
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Бронь автомобиля"
        verbose_name_plural = "Брони автомобилей"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["car_instance"],
                condition=models.Q(is_active=True),
                name="unique_active_reservation_per_car",
            )
        ]

    def __str__(self):
        return f"Бронь {self.car_instance.vin} — {self.user}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=RESERVATION_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.is_active and self.expires_at <= timezone.now()

    @property
    def days_left(self):
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)


class CarOption(models.Model):
    name = models.CharField("Название опции", max_length=100, unique=True)
    price = models.DecimalField(
        "Цена, ₽",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "Дополнительное оборудование"
        verbose_name_plural = "Дополнительное оборудование"
        ordering = ["price"]

    def __str__(self):
        return self.name


class ConfigurationOption(models.Model):
    configuration = models.ForeignKey(
        CarConfiguration,
        on_delete=models.CASCADE,
        related_name="option_links",
        verbose_name="Комплектация",
    )
    option = models.ForeignKey(
        CarOption,
        on_delete=models.CASCADE,
        related_name="configuration_links",
        verbose_name="Опция",
    )
    is_standard = models.BooleanField("Базовое оснащение", default=False)

    class Meta:
        verbose_name = "Опция комплектации"
        verbose_name_plural = "Опции комплектаций"
        constraints = [
            models.UniqueConstraint(
                fields=["configuration", "option"],
                name="unique_option_per_configuration",
            )
        ]

    def __str__(self):
        return f"{self.configuration} — {self.option}"


class Review(models.Model):
    configuration = models.ForeignKey(
        CarConfiguration,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Комплектация",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Автор",
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
    )
    text = models.TextField("Текст отзыва")
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["configuration", "user"], name="one_review_per_user"
            )
        ]

    def __str__(self):
        return f"Отзыв {self.user} на {self.configuration}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Пользователь",
    )
    phone = models.CharField(
        "Телефон",
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9\s\-()]{10,20}$",
                message="Укажите телефон в формате +7 (900) 000-00-00.",
            )
        ],
    )
    driving_experience_years = models.PositiveSmallIntegerField(
        "Стаж вождения, лет",
        default=0,
        validators=[MaxValueValidator(70)],
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль {self.user}"

    @property
    def display_name(self):
        full = self.user.get_full_name()
        return full or self.user.username


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )
    configuration = models.ForeignKey(
        CarConfiguration,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Комплектация",
    )
    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "configuration"], name="unique_favorite"
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.configuration}"
