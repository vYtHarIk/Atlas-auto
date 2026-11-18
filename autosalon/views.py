"""Представления автосалона «Атлас Авто»."""

from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import demo_data
from .forms import (
    AccountPasswordForm,
    LoginForm,
    ProfileForm,
    RegisterForm,
    ReservationForm,
    ReservationLookupForm,
    ReviewForm,
    TestDriveForm,
    TradeInForm,
)
from .models import (
    BOOKING_STATUSES,
    BODY_TYPES,
    CarConfiguration,
    CarInstance,
    CarModel,
    CarReservation,
    Favorite,
    Review,
    TestCar,
    TestDriveBooking,
    TradeInPhoto,
    TradeInRequest,
)

MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

AVAILABILITY_CHOICES = [
    ("", "Все автомобили"),
    ("available", "В наличии"),
    ("on_order", "В поставке"),
    ("reserved", "Забронированы"),
]

CONDITION_CHOICES = [("", "Любое состояние"), ("new", "Новые"), ("used", "С пробегом")]

SORT_CHOICES = [
    ("default", "По порядку"),
    ("price_asc", "Сначала дешевле"),
    ("price_desc", "Сначала дороже"),
    ("year_desc", "Сначала новые"),
    ("name", "По названию"),
]

PAGE_SIZE = 6


def _profile(user):
    from .models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def upcoming_slots(limit=8):
    now = timezone.localtime(timezone.now()) + timedelta(hours=1)
    today = now.date()
    slots = []
    for offset in range(0, 14):
        day = today + timedelta(days=offset)
        for hour in (10, 12, 14, 16, 18):
            moment = timezone.make_aware(
                datetime.combine(day, time(hour, 0)),
                timezone.get_current_timezone(),
            )
            if moment <= now:
                continue
            if day == today:
                label = f"Сегодня, {hour:02d}:00"
            elif day == today + timedelta(days=1):
                label = f"Завтра, {hour:02d}:00"
            else:
                label = f"{day.day} {MONTHS[day.month - 1]}, {hour:02d}:00"
            slots.append({"value": moment.strftime("%Y-%m-%dT%H:%M"), "label": label})
            if len(slots) >= limit:
                return slots
    return slots


def _featured_configurations(limit=3):
    return (
        CarConfiguration.objects.select_related("model")
        .prefetch_related("instances")
        .order_by("sort_order", "base_price")[:limit]
    )


def _favorite_ids(request):
    if not request.user.is_authenticated:
        return set()
    return set(
        Favorite.objects.filter(user=request.user).values_list(
            "configuration_id", flat=True
        )
    )


def home(request):
    cars = list(_featured_configurations())
    body_types = [
        (value, label)
        for value, label in BODY_TYPES
        if value in {"suv", "sedan", "coupe"}
    ]
    context = {
        "hero": demo_data.HERO,
        "steps": demo_data.STEPS,
        "body_types": body_types,
        "cars": cars,
        "cars_count": len(cars),
        "test_drive_slots": upcoming_slots(limit=6),
        "favorite_ids": _favorite_ids(request),
    }
    return render(request, "autosalon/home.html", context)


def _int_param(value, default=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def catalog(request):
    params = request.GET
    configs = (
        CarConfiguration.objects.select_related("model")
        .prefetch_related("instances")
        .all()
    )

    query = params.get("q", "").strip()
    brand = params.get("brand", "").strip()
    body_type = params.get("body_type", "").strip()
    condition = params.get("condition", "").strip()
    availability = params.get("availability", "").strip()
    price_min = _int_param(params.get("price_min"))
    price_max = _int_param(params.get("price_max"))
    year_min = _int_param(params.get("year_min"))
    year_max = _int_param(params.get("year_max"))
    sort = params.get("sort", "default")

    if query:
        configs = configs.filter(
            models_q(query)
        )
    if brand:
        configs = configs.filter(model__brand=brand)
    if body_type:
        configs = configs.filter(model__body_type=body_type)
    if condition in {"new", "used"}:
        configs = configs.filter(instances__condition=condition)
    if availability == "available":
        configs = configs.filter(instances__status="available")
    elif availability == "on_order":
        configs = configs.filter(instances__status="on_order")
    elif availability == "reserved":
        configs = configs.filter(instances__status="reserved")
    if price_min is not None:
        configs = configs.filter(base_price__gte=price_min)
    if price_max is not None:
        configs = configs.filter(base_price__lte=price_max)
    if year_min is not None:
        configs = configs.filter(instances__year__gte=year_min)
    if year_max is not None:
        configs = configs.filter(instances__year__lte=year_max)

    if sort == "price_asc":
        configs = configs.order_by("base_price", "sort_order")
    elif sort == "price_desc":
        configs = configs.order_by("-base_price", "sort_order")
    elif sort == "year_desc":
        configs = configs.order_by("-model__year_introduced", "sort_order")
    elif sort == "name":
        configs = configs.order_by("model__brand", "model__name")
    else:
        configs = configs.order_by("sort_order", "base_price")

    configs = configs.distinct()
    total = configs.count()

    from django.core.paginator import Paginator

    paginator = Paginator(configs, PAGE_SIZE)
    page_obj = paginator.get_page(params.get("page"))
    query_params = params.copy()
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "configs": page_obj.object_list,
        "total": total,
        "brands": CarModel.objects.values_list("brand", flat=True)
        .distinct()
        .order_by("brand"),
        "body_types": [
            (value, label)
            for value, label in BODY_TYPES
            if value in {"suv", "sedan", "coupe", "wagon"}
        ],
        "availability_choices": AVAILABILITY_CHOICES,
        "condition_choices": CONDITION_CHOICES,
        "sort_choices": SORT_CHOICES,
        "selected": {
            "q": query,
            "brand": brand,
            "body_type": body_type,
            "condition": condition,
            "availability": availability,
            "price_min": params.get("price_min", ""),
            "price_max": params.get("price_max", ""),
            "year_min": params.get("year_min", ""),
            "year_max": params.get("year_max", ""),
            "sort": sort,
        },
        "query_string": query_params.urlencode(),
        "favorite_ids": _favorite_ids(request),
        "page_title": "Купить автомобиль — АТЛАС АВТО",
    }
    return render(request, "autosalon/catalog.html", context)


def models_q(query):
    from django.db.models import Q

    return (
        Q(model__brand__icontains=query)
        | Q(model__name__icontains=query)
        | Q(name__icontains=query)
        | Q(model__description__icontains=query)
    )


def car_detail(request, pk):
    config = get_object_or_404(
        CarConfiguration.objects.select_related("model").prefetch_related(
            Prefetch("instances", queryset=CarInstance.objects.order_by("status", "vin")),
            "option_links__option",
            Prefetch(
                "reviews",
                queryset=Review.objects.filter(is_published=True).select_related("user"),
            ),
        ),
        pk=pk,
    )
    instances = list(config.instances.all())
    available = next((car for car in instances if car.is_available), None)
    reviews = list(config.reviews.all())
    average_rating = (
        round(sum(review.rating for review in reviews) / len(reviews), 1)
        if reviews
        else None
    )
    similar = (
        CarConfiguration.objects.select_related("model")
        .prefetch_related("instances")
        .filter(model__body_type=config.model.body_type)
        .exclude(pk=config.pk)
        .order_by("sort_order")[:3]
    )
    context = {
        "config": config,
        "car": available or (instances[0] if instances else None),
        "instances": instances,
        "available_instance": available,
        "options": config.option_links.all(),
        "reviews": reviews,
        "average_rating": average_rating,
        "review_form": ReviewForm(),
        "similar": similar,
        "favorite_ids": _favorite_ids(request),
        "is_favorite": config.pk in _favorite_ids(request),
        "page_title": f"{config.model.title} — АТЛАС АВТО",
        "meta_description": (
            f"{config.model.title} {config.name}: {config.specs}. "
            f"Цена от {config.base_price:.0f} ₽. Тест-драйв и бронирование онлайн."
        ),
    }
    return render(request, "autosalon/car_detail.html", context)


@login_required
def test_drive(request):
    initial_car = None
    config_id = request.GET.get("car")
    if config_id:
        initial_car = (
            CarConfiguration.objects.select_related("model")
            .filter(pk=config_id)
            .first()
        )
    initial = {}
    if request.GET.get("slot"):
        initial["booking_datetime"] = request.GET["slot"]
    if request.GET.get("name"):
        initial["contact_name"] = request.GET["name"]
    if request.GET.get("phone"):
        initial["contact_phone"] = request.GET["phone"]

    form = TestDriveForm(
        request.POST or None,
        user=request.user,
        initial_car=initial_car,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        booking = form.save()
        messages.success(
            request,
            "Запись создана: "
            f"{booking.test_car.model.title}, "
            f"{timezone.localtime(booking.booking_datetime):%d.%m.%Y в %H:%M}. "
            "Менеджер подтвердит её звонком.",
        )
        return redirect("autosalon:account_bookings")

    context = {
        "form": form,
        "config": initial_car,
        "test_cars": TestCar.objects.filter(is_active=True).select_related("model"),
        "slots": upcoming_slots(limit=8),
        "page_title": "Запись на тест-драйв — АТЛАС АВТО",
    }
    return render(request, "autosalon/test_drive.html", context)


@login_required
def trade_in(request):
    form = TradeInForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        request_obj = form.save(commit=False)
        request_obj.user = request.user
        request_obj.save()
        for photo in form.cleaned_data.get("photos", []):
            TradeInPhoto.objects.create(request=request_obj, image=photo)
        estimate = f"{request_obj.estimated_price:,.0f}".replace(",", " ")
        messages.success(
            request,
            f"Заявка №{request_obj.pk} принята. Предварительная оценка — "
            f"{estimate} ₽. Менеджер уточнит детали и свяжется с вами.",
        )
        return redirect("autosalon:account_trade_ins")

    context = {
        "form": form,
        "page_title": "Трейд-ин — оценка автомобиля | АТЛАС АВТО",
        "page_lead": (
            "Оценим ваш автомобиль за пару минут и зачтём его стоимость "
            "в покупку нового."
        ),
    }
    return render(request, "autosalon/trade_in.html", context)


def _release_expired_reservation(car):
    """Снимает просроченную бронь, чтобы автомобиль снова можно было купить."""
    if (
        car.status == "reserved"
        and car.reserved_until
        and car.reserved_until <= timezone.now()
    ):
        CarReservation.objects.filter(car_instance=car, is_active=True).update(
            is_active=False
        )
        car.status = "available"
        car.reserved_until = None
        car.save(update_fields=["status", "reserved_until"])
        return True
    return False


@login_required
def reservation_lookup(request):
    form = ReservationLookupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        instance = form.get_instance()
        if not instance:
            form.add_error("vin", "Автомобиль с таким VIN не найден в салоне.")
        else:
            _release_expired_reservation(instance)
            if not instance.is_available:
                return render(
                    request,
                    "autosalon/reservation_lookup.html",
                    {
                        "form": form,
                        "found": instance,
                        "page_title": "Бронирование по VIN — АТЛАС АВТО",
                    },
                    status=409,
                )
            return redirect("autosalon:reservation_create", instance_id=instance.pk)

    return render(
        request,
        "autosalon/reservation_lookup.html",
        {"form": form, "page_title": "Бронирование по VIN — АТЛАС АВТО"},
    )


@login_required
def reservation_create(request, instance_id):
    car = get_object_or_404(
        CarInstance.objects.select_related("configuration__model"), pk=instance_id
    )
    _release_expired_reservation(car)
    if not car.is_available:
        messages.error(request, "Этот автомобиль уже забронирован или продан.")
        return redirect("autosalon:car_detail", pk=car.configuration_id)

    form = ReservationForm(request.POST or None, car=car)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked = CarInstance.objects.select_for_update().get(pk=car.pk)
                if not locked.is_available:
                    raise IntegrityError("car is not available")
                reservation = form.save(commit=False)
                reservation.user = request.user
                reservation.car_instance = locked
                reservation.save()
                locked.status = "reserved"
                locked.reserved_until = reservation.expires_at
                locked.save(update_fields=["status", "reserved_until"])
        except IntegrityError:
            messages.error(
                request,
                "Не получилось забронировать: автомобиль только что заняли. "
                "Выберите другой автомобиль.",
            )
            return redirect("autosalon:catalog")

        messages.success(
            request,
            f"Автомобиль {car.configuration.model.title} забронирован до "
            f"{timezone.localtime(reservation.expires_at):%d.%m.%Y}. "
            f"Задаток — {reservation.deposit_amount:,.0f} ₽.".replace(",", " "),
        )
        return redirect("autosalon:account_reservations")

    context = {
        "form": form,
        "car": car,
        "config": car.configuration,
        "page_title": "Бронирование автомобиля — АТЛАС АВТО",
    }
    return render(request, "autosalon/reservation.html", context)


@login_required
@require_POST
def reservation_cancel(request, pk):
    reservation = get_object_or_404(
        CarReservation.objects.select_related("car_instance__configuration__model"),
        pk=pk,
        user=request.user,
    )
    if reservation.is_active:
        with transaction.atomic():
            reservation.is_active = False
            reservation.save(update_fields=["is_active"])
            car = reservation.car_instance
            car.status = "available"
            car.reserved_until = None
            car.save(update_fields=["status", "reserved_until"])
        messages.success(request, "Бронирование отменено, автомобиль снова свободен.")
    else:
        messages.info(request, "Эта бронь уже неактивна.")
    return redirect("autosalon:account_reservations")


@login_required
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(
        TestDriveBooking.objects.select_related("test_car__model"),
        pk=pk,
        user=request.user,
    )
    if booking.is_active and not booking.is_past:
        booking.status = "cancelled"
        booking.save(update_fields=["status"])
        messages.success(request, "Запись на тест-драйв отменена.")
    else:
        messages.info(request, "Эту запись уже нельзя отменить.")
    return redirect("autosalon:account_bookings")


@login_required
@require_POST
def favorite_toggle(request, pk):
    config = get_object_or_404(CarConfiguration, pk=pk)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user, configuration=config
    )
    if not created:
        favorite.delete()
    is_favorite = created
    wants_json = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
    )
    if wants_json:
        return JsonResponse(
            {
                "is_favorite": is_favorite,
                "count": Favorite.objects.filter(user=request.user).count(),
            }
        )
    messages.success(
        request,
        "Автомобиль добавлен в избранное."
        if is_favorite
        else "Автомобиль удалён из избранного.",
    )
    return redirect(
        request.POST.get("next")
        or reverse("autosalon:car_detail", kwargs={"pk": config.pk})
    )


@login_required
@require_POST
def review_create(request, pk):
    config = get_object_or_404(CarConfiguration, pk=pk)
    form = ReviewForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(
            configuration=config,
            user=request.user,
            defaults={
                "rating": form.cleaned_data["rating"],
                "text": form.cleaned_data["text"],
                "is_published": True,
            },
        )
        messages.success(request, "Спасибо! Отзыв опубликован.")
    else:
        messages.error(request, "Не удалось сохранить отзыв: проверьте оценку и текст.")
    return redirect(f"{reverse('autosalon:car_detail', kwargs={'pk': config.pk})}#reviews")


def about(request):
    return render(
        request,
        "autosalon/about.html",
        {"page_title": "О нас — АТЛАС АВТО"},
    )


def contacts(request):
    return render(
        request,
        "autosalon/contacts.html",
        {"page_title": "Контакты — АТЛАС АВТО"},
    )


def privacy(request):
    return render(
        request,
        "autosalon/privacy.html",
        {"page_title": "Политика конфиденциальности — АТЛАС АВТО"},
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("autosalon:account")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        messages.success(
            request,
            "Добро пожаловать в АТЛАС АВТО! Аккаунт создан, "
            "теперь можно записаться на тест-драйв и бронировать автомобили.",
        )
        return redirect("autosalon:account")
    return render(
        request,
        "autosalon/register.html",
        {"form": form, "login_form": LoginForm(), "page_title": "Регистрация — АТЛАС АВТО"},
    )


@login_required
def account_dashboard(request):
    now = timezone.now()
    profile = _profile(request.user)
    bookings = TestDriveBooking.objects.filter(user=request.user).select_related(
        "test_car__model"
    )
    reservations = CarReservation.objects.filter(
        user=request.user, is_active=True
    ).select_related("car_instance__configuration__model")
    trade_ins = TradeInRequest.objects.filter(user=request.user).prefetch_related(
        "photos"
    )
    context = {
        "profile": profile,
        "upcoming_bookings": bookings.filter(
            booking_datetime__gte=now, status__in=("pending", "confirmed")
        )[:3],
        "active_reservations": reservations,
        "latest_trade_in": trade_ins.first(),
        "favorites_count": Favorite.objects.filter(user=request.user).count(),
        "bookings_count": bookings.count(),
        "reservations_count": reservations.count(),
        "reviews_count": Review.objects.filter(user=request.user).count(),
        "page_title": "Личный кабинет — АТЛАС АВТО",
    }
    return render(request, "autosalon/account/dashboard.html", context)


@login_required
def account_bookings(request):
    bookings = (
        TestDriveBooking.objects.filter(user=request.user)
        .select_related("test_car__model", "manager")
        .order_by("-booking_datetime")
    )
    return render(
        request,
        "autosalon/account/bookings.html",
        {
            "bookings": bookings,
            "status_choices": dict(BOOKING_STATUSES),
            "page_title": "Мои тест-драйвы — АТЛАС АВТО",
        },
    )


@login_required
def account_reservations(request):
    reservations = (
        CarReservation.objects.filter(user=request.user)
        .select_related("car_instance__configuration__model")
        .order_by("-created_at")
    )
    return render(
        request,
        "autosalon/account/reservations.html",
        {"reservations": reservations, "page_title": "Мои брони — АТЛАС АВТО"},
    )


@login_required
def account_trade_ins(request):
    trade_ins = (
        TradeInRequest.objects.filter(user=request.user)
        .prefetch_related("photos")
        .order_by("-created_at")
    )
    return render(
        request,
        "autosalon/account/trade_ins.html",
        {"trade_ins": trade_ins, "page_title": "Мои заявки трейд-ин — АТЛАС АВТО"},
    )


@login_required
def account_favorites(request):
    favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related("configuration__model")
        .prefetch_related("configuration__instances")
        .order_by("-created_at")
    )
    return render(
        request,
        "autosalon/account/favorites.html",
        {
            "favorites": favorites,
            "favorite_ids": {item.configuration_id for item in favorites},
            "page_title": "Избранное — АТЛАС АВТО",
        },
    )


@login_required
def account_profile(request):
    form = ProfileForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль обновлён.")
        return redirect("autosalon:account_profile")
    return render(
        request,
        "autosalon/account/profile.html",
        {"form": form, "page_title": "Профиль — АТЛАС АВТО"},
    )


@login_required
def account_password(request):
    form = AccountPasswordForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        messages.success(request, "Пароль изменён.")
        return redirect("autosalon:account")
    return render(
        request,
        "autosalon/account/password.html",
        {"form": form, "page_title": "Смена пароля — АТЛАС АВТО"},
    )
