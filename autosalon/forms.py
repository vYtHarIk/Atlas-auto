from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.utils import timezone

from .models import (
    CarConfiguration,
    CarInstance,
    CarReservation,
    Review,
    TestCar,
    TestDriveBooking,
    TradeInRequest,
    UserProfile,
)

User = get_user_model()

PHONE_VALIDATOR = RegexValidator(
    regex=r"^\+?[0-9\s\-()]{10,20}$",
    message="Укажите телефон в формате +7 (900) 000-00-00.",
)

VIN_VALIDATOR = RegexValidator(
    regex=r"^[A-HJ-NPR-Z0-9]{17}$",
    message="VIN состоит из 17 символов: латинские буквы и цифры.",
)

TEST_DRIVE_SLOTS = ["10:00", "12:00", "14:00", "16:00", "18:00"]
WORK_START_HOUR = 9
WORK_END_HOUR = 21
MAX_BOOKING_DAYS = 60
MAX_PHOTO_SIZE = 5 * 1024 * 1024
PHOTO_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]


class StyledFormMixin:
    def _style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check__input")
            elif isinstance(widget, forms.RadioSelect):
                widget.attrs.setdefault("class", "form-radio")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "form-file")
            else:
                widget.attrs.setdefault("class", "form-input")
            if field.required and not isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("aria-required", "true")


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="E-mail или логин",
        widget=forms.TextInput(
            attrs={"autocomplete": "username", "placeholder": "you@example.com"}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "placeholder": "Ваш пароль"}
        ),
    )
    error_messages = {
        "invalid_login": "Проверьте e-mail и пароль. Оба поля чувствительны к регистру.",
        "inactive": "Этот аккаунт отключён.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs["autofocus"] = True
        self._style_fields()

    def clean(self):
        login = self.cleaned_data.get("username", "").strip()
        if "@" in login:
            user = User.objects.filter(email__iexact=login).first()
            if user:
                self.cleaned_data["username"] = user.get_username()
        return super().clean()


class RegisterForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)
    email = forms.EmailField(label="E-mail")
    phone = forms.CharField(label="Телефон", max_length=20, validators=[PHONE_VALIDATOR])
    consent = forms.BooleanField(
        label="Согласен на обработку персональных данных",
        error_messages={
            "required": "Без согласия на обработку данных регистрация невозможна."
        },
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Пароль"
        self.fields["password1"].help_text = (
            "Минимум 8 символов, не только цифры и не похож на имя или e-mail."
        )
        self.fields["password2"].label = "Повторите пароль"
        self.fields["password2"].help_text = ""
        self.order_fields(
            [
                "first_name",
                "last_name",
                "email",
                "phone",
                "password1",
                "password2",
                "consent",
            ]
        )
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data["phone"]
            profile.save(update_fields=["phone"])
        return user


class ProfileForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150)
    email = forms.EmailField(label="E-mail")
    phone = forms.CharField(
        label="Телефон", max_length=20, required=False, validators=[PHONE_VALIDATOR]
    )
    driving_experience_years = forms.IntegerField(
        label="Стаж вождения, лет", min_value=0, max_value=70, required=False
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not self.is_bound:
            self.initial.update(
                {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone": profile.phone,
                    "driving_experience_years": profile.driving_experience_years,
                }
            )
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("Этот e-mail уже занят другим аккаунтом.")
        if (
            User.objects.filter(username__iexact=email)
            .exclude(pk=self.user.pk)
            .exists()
        ):
            raise ValidationError("Этот e-mail уже занят другим аккаунтом.")
        return email

    def save(self):
        user = self.user
        email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.email = email
        # Аккаунты, созданные через сайт, используют e-mail как логин.
        if user.username != email and not User.objects.filter(
            username__iexact=email
        ).exclude(pk=user.pk).exists():
            user.username = email
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.phone = self.cleaned_data["phone"]
        profile.driving_experience_years = (
            self.cleaned_data["driving_experience_years"] or 0
        )
        profile.save()
        return user


class AccountPasswordForm(StyledFormMixin, PasswordChangeForm):
    old_password = forms.CharField(
        label="Текущий пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label="Повторите новый пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class TestDriveForm(StyledFormMixin, forms.ModelForm):
    contact_name = forms.CharField(label="Ваше имя", max_length=150)
    contact_phone = forms.CharField(
        label="Телефон", max_length=20, validators=[PHONE_VALIDATOR]
    )
    test_car = forms.ModelChoiceField(
        label="Автомобиль",
        queryset=TestCar.objects.filter(is_active=True).select_related("model"),
        empty_label="Выберите автомобиль",
    )
    booking_datetime = forms.DateTimeField(
        label="Дата и время",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )

    class Meta:
        model = TestDriveBooking
        fields = ("test_car", "booking_datetime", "driving_experience_years", "comment")
        widgets = {
            "comment": forms.Textarea(
                attrs={"placeholder": "Например, хотите сравнить две комплектации"}
            )
        }

    def __init__(self, *args, user=None, initial_car=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not self.is_bound:
            self.initial.setdefault(
                "contact_name", user.get_full_name() or user.first_name
            )
            self.initial.setdefault("contact_phone", profile.phone)
            self.initial.setdefault(
                "driving_experience_years", profile.driving_experience_years
            )
            self.initial.setdefault("booking_datetime", self._default_datetime())
            if initial_car:
                car = self._car_for_configuration(initial_car)
                if car:
                    self.initial["test_car"] = car.pk
        self._style_fields()
        self.fields["contact_name"].widget.attrs["placeholder"] = "Как к вам обращаться"
        self.fields["contact_phone"].widget.attrs["placeholder"] = "+7 (___) ___-__-__"
        self.fields["booking_datetime"].widget.attrs["min"] = self._default_datetime()

    @staticmethod
    def _default_datetime():
        moment = timezone.localtime(timezone.now()) + timedelta(days=1)
        return moment.replace(hour=12, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%dT%H:%M"
        )

    @staticmethod
    def _car_for_configuration(configuration):
        return (
            TestCar.objects.filter(
                is_active=True, model=configuration.model
            )
            .select_related("model")
            .first()
        )

    def clean_booking_datetime(self):
        value = self.cleaned_data["booking_datetime"]
        now = timezone.now()
        if value <= now + timedelta(hours=1):
            raise ValidationError("Запись возможна не раньше чем через час.")
        if value > now + timedelta(days=MAX_BOOKING_DAYS):
            raise ValidationError(
                f"Записаться можно не более чем на {MAX_BOOKING_DAYS} дней вперёд."
            )
        local = timezone.localtime(value)
        if not (WORK_START_HOUR <= local.hour < WORK_END_HOUR):
            raise ValidationError("Салон принимает записи с 09:00 до 21:00.")
        if local.minute not in (0, 30):
            raise ValidationError("Выберите время с шагом 30 минут.")
        return value

    def clean(self):
        cleaned = super().clean()
        car = cleaned.get("test_car")
        moment = cleaned.get("booking_datetime")
        if car and moment:
            conflict = (
                TestDriveBooking.objects.filter(
                    test_car=car,
                    booking_datetime=moment,
                    status__in=("pending", "confirmed"),
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if conflict:
                raise ValidationError(
                    "На это время автомобиль уже занят. Выберите другой слот."
                )
            same_user = (
                TestDriveBooking.objects.filter(
                    user=self.user,
                    booking_datetime=moment,
                    status__in=("pending", "confirmed"),
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if same_user:
                raise ValidationError(
                    "У вас уже есть запись на это время. Выберите другой слот."
                )
        return cleaned

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.user = self.user
        if commit:
            booking.save()
            profile, _ = UserProfile.objects.get_or_create(user=self.user)
            profile.phone = self.cleaned_data["contact_phone"]
            profile.driving_experience_years = self.cleaned_data[
                "driving_experience_years"
            ]
            profile.save()
            name = self.cleaned_data["contact_name"].strip()
            if name and not self.user.get_full_name():
                parts = name.split(maxsplit=1)
                self.user.first_name = parts[0]
                self.user.last_name = parts[1] if len(parts) > 1 else ""
                self.user.save(update_fields=["first_name", "last_name"])
        return booking


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        items = data if isinstance(data, (list, tuple)) else [data]
        return [super().clean(item, initial) for item in items]


class TradeInForm(StyledFormMixin, forms.ModelForm):
    photos = MultipleFileField(
        label="Фотографии автомобиля",
        required=False,
        help_text="JPG, PNG или WEBP, до 5 МБ каждая.",
    )

    class Meta:
        model = TradeInRequest
        fields = ("brand", "model", "year", "mileage", "comment")
        widgets = {
            "comment": forms.Textarea(
                attrs={"placeholder": "Состояние, комплектация, особенности"}
            ),
            "year": forms.NumberInput(attrs={"min": 1950, "max": timezone.now().year}),
            "mileage": forms.NumberInput(attrs={"min": 0, "step": 1000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].widget.attrs["placeholder"] = "Например, Toyota"
        self.fields["model"].widget.attrs["placeholder"] = "Например, Camry"
        if not self.is_bound:
            self.initial.setdefault("year", timezone.now().year - 3)
        self._style_fields()

    def clean_year(self):
        year = self.cleaned_data["year"]
        current = timezone.now().year
        if year < 1950 or year > current:
            raise ValidationError(f"Год выпуска — от 1950 до {current}.")
        return year

    def clean_mileage(self):
        mileage = self.cleaned_data["mileage"]
        if mileage > 2_000_000:
            raise ValidationError("Проверьте пробег: значение выглядит нереальным.")
        return mileage

    def clean_photos(self):
        photos = self.cleaned_data.get("photos") or []
        if len(photos) > 8:
            raise ValidationError("Можно загрузить не больше 8 фотографий.")
        validator = FileExtensionValidator(PHOTO_EXTENSIONS)
        for photo in photos:
            validator(photo)
            if photo.size > MAX_PHOTO_SIZE:
                raise ValidationError(
                    f"Файл «{photo.name}» больше 5 МБ. Сожмите фотографию."
                )
        return photos


class ReservationForm(StyledFormMixin, forms.ModelForm):
    agreement = forms.BooleanField(
        label="Подтверждаю условия бронирования",
        error_messages={
            "required": "Для бронирования нужно подтвердить условия."
        },
    )

    class Meta:
        model = CarReservation
        fields = ("deposit_amount", "payment_method")
        widgets = {
            "deposit_amount": forms.NumberInput(
                attrs={"min": 50000, "step": 1000, "placeholder": "Минимум 50 000 ₽"}
            ),
            "payment_method": forms.RadioSelect,
        }
        labels = {
            "deposit_amount": "Сумма задатка, ₽",
            "payment_method": "Способ оплаты",
        }

    def __init__(self, *args, car=None, **kwargs):
        self.car = car
        super().__init__(*args, **kwargs)
        if not self.is_bound and car:
            max_deposit = int(car.final_price)
            self.fields["deposit_amount"].widget.attrs["max"] = max_deposit
            self.fields["deposit_amount"].help_text = (
                f"Минимум 50 000 ₽, не больше стоимости автомобиля "
                f"({max_deposit:,} ₽).".replace(",", " ")
            )
            self.initial.setdefault("deposit_amount", 50_000)
        self._style_fields()
        self.fields["payment_method"].widget.attrs.pop("class", None)

    def clean_deposit_amount(self):
        amount = self.cleaned_data["deposit_amount"]
        if amount < 50_000:
            raise ValidationError("Минимальная сумма задатка — 50 000 ₽.")
        if self.car and amount > self.car.final_price:
            raise ValidationError("Задаток не может превышать стоимость автомобиля.")
        return amount


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Оценка",
        coerce=int,
        choices=[
            (5, "5 — отлично"),
            (4, "4 — хорошо"),
            (3, "3 — нормально"),
            (2, "2 — есть замечания"),
            (1, "1 — плохо"),
        ],
        initial=5,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Review
        fields = ("rating", "text")
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Поделитесь впечатлениями об автомобиле",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["rating"].widget.attrs.pop("class", None)


class ReservationLookupForm(StyledFormMixin, forms.Form):
    vin = forms.CharField(
        label="VIN-номер автомобиля",
        max_length=17,
        validators=[VIN_VALIDATOR],
        widget=forms.TextInput(
            attrs={
                "placeholder": "17 символов",
                "autocomplete": "off",
                "style": "text-transform: uppercase",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_vin(self):
        return self.cleaned_data["vin"].strip().upper()

    def get_instance(self):
        return (
            CarInstance.objects.select_related(
                "configuration__model"
            )
            .filter(vin=self.cleaned_data["vin"])
            .first()
        )
