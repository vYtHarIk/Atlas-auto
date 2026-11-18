from django.http import Http404
from django.shortcuts import render

from . import demo_data


def home(request):
    cars = demo_data.CARS
    context = {
        "hero": demo_data.HERO,
        "steps": demo_data.STEPS,
        "body_types": demo_data.BODY_TYPES,
        "cars": cars,
        "cars_count": len(cars),
        "test_drive_slots": demo_data.TEST_DRIVE_SLOTS,
    }
    return render(request, "autosalon/home.html", context)


def catalog(request):
    return _section(
        request,
        title="Каталог автомобилей",
        lead="Все новые автомобили в наличии и под заказ.",
        note="Каталог с фильтрами, сортировкой и пагинацией появится на занятии 8.",
    )


def car_detail(request, slug):
    car = next((item for item in demo_data.CARS if item["slug"] == slug), None)
    if car is None:
        raise Http404("Автомобиль не найден")

    return render(
        request,
        "autosalon/car_detail.html",
        {"car": car, "page_title": f"{car['name']} — АТЛАС АВТО"},
    )


def test_drive(request):
    return _section(
        request,
        title="Запись на тест-драйв",
        lead="Выберите автомобиль, дату и удобное время — подтвердим запись звонком.",
        note="Форма записи с серверной валидацией появится на занятии 9.",
    )


def trade_in(request):
    return _section(
        request,
        title="Трейд-ин",
        lead="Оценим ваш автомобиль и зачтём его стоимость в покупку нового.",
        note="Заявка на оценку появится на занятии 8.",
    )


def about(request):
    return _section(
        request,
        title="О нас",
        lead="АТЛАС АВТО — салон автомобилей с характером.",
        note="Статическая страница с историей салона появится на занятии 8.",
    )


def contacts(request):
    return _section(
        request,
        title="Контакты",
        lead="Москва, ежедневно с 09:00 до 21:00.",
        note="Страница с адресом, картой и формой обратной связи появится на занятии 8.",
    )


def register(request):
    return _section(
        request,
        title="Регистрация",
        lead="Личный кабинет покупателя: записи на тест-драйв, брони и заявки.",
        note="Аутентификация средствами django.contrib.auth появится на занятии 9.",
    )


def privacy(request):
    return _section(
        request,
        title="Политика конфиденциальности",
        lead="Как мы обрабатываем и храним персональные данные.",
        note="Текст политики добавим на занятии 8.",
    )


def _section(request, *, title, lead, note):
    return render(
        request,
        "autosalon/section_stub.html",
        {
            "page_title": f"{title} — АТЛАС АВТО",
            "section_title": title,
            "section_lead": lead,
            "section_note": note,
        },
    )
