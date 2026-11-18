from django.contrib import admin
from django.utils.html import format_html

from .models import (
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
    TradeInPhoto,
    TradeInRequest,
    UserProfile,
)


class CarConfigurationInline(admin.TabularInline):
    model = CarConfiguration
    extra = 0
    fields = ("name", "engine_volume", "power_hp", "transmission", "year", "base_price")


class ConfigurationOptionInline(admin.TabularInline):
    model = ConfigurationOption
    extra = 0
    autocomplete_fields = ("option",)


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "body_type", "year_introduced", "configurations_count")
    list_filter = ("brand", "body_type")
    search_fields = ("name", "brand", "description")
    inlines = [CarConfigurationInline]

    @admin.display(description="Комплектаций")
    def configurations_count(self, obj):
        return obj.configurations.count()


@admin.register(CarConfiguration)
class CarConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "model",
        "engine_volume",
        "power_hp",
        "transmission",
        "base_price",
        "sort_order",
    )
    list_filter = ("model__brand", "transmission", "drive_type", "year")
    search_fields = ("model__brand", "model__name", "name")
    autocomplete_fields = ("model",)
    inlines = [ConfigurationOptionInline]
    list_select_related = ("model",)


@admin.register(CarInstance)
class CarInstanceAdmin(admin.ModelAdmin):
    list_display = ("vin", "configuration", "color", "status", "year", "mileage", "price")
    list_filter = ("status", "condition", "color")
    search_fields = ("vin", "configuration__model__brand", "configuration__model__name")
    autocomplete_fields = ("configuration",)
    list_select_related = ("configuration__model",)


@admin.register(TestCar)
class TestCarAdmin(admin.ModelAdmin):
    list_display = ("__str__", "model", "state_number", "mileage", "is_active")
    list_filter = ("is_active", "model__brand")
    search_fields = ("state_number", "model__brand", "model__name")
    autocomplete_fields = ("model",)


@admin.register(TestDriveBooking)
class TestDriveBookingAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "test_car",
        "booking_datetime",
        "driving_experience_years",
        "status",
        "manager",
    )
    list_filter = ("status", "booking_datetime", "test_car__model__brand")
    search_fields = ("user__username", "user__email", "user__last_name", "test_car__state_number")
    autocomplete_fields = ("user", "test_car", "manager")
    date_hierarchy = "booking_datetime"


@admin.register(TradeInRequest)
class TradeInRequestAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "brand", "model", "year", "mileage", "estimated_price", "status")
    list_filter = ("status", "brand")
    search_fields = ("brand", "model", "user__username", "user__email")
    autocomplete_fields = ("user",)
    inlines = []


class TradeInPhotoInline(admin.TabularInline):
    model = TradeInPhoto
    extra = 0
    readonly_fields = ("uploaded_at", "preview")

    @admin.display(description="Превью")
    def preview(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="height:80px">', obj.image.url)


TradeInRequestAdmin.inlines = [TradeInPhotoInline]



@admin.register(CarReservation)
class CarReservationAdmin(admin.ModelAdmin):
    list_display = (
        "car_instance",
        "user",
        "deposit_amount",
        "payment_method",
        "created_at",
        "expires_at",
        "is_active",
    )
    list_filter = ("is_active", "payment_method")
    search_fields = ("car_instance__vin", "user__username", "user__email")
    autocomplete_fields = ("user", "car_instance")
    date_hierarchy = "created_at"


@admin.register(CarOption)
class CarOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "price")
    search_fields = ("name",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("__str__", "rating", "is_published", "created_at")
    list_filter = ("rating", "is_published")
    search_fields = ("text", "user__username", "configuration__model__name")
    autocomplete_fields = ("user", "configuration")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "configuration", "created_at")
    search_fields = ("user__username", "configuration__model__name")
    autocomplete_fields = ("user", "configuration")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "driving_experience_years", "created_at")
    search_fields = ("user__username", "user__email", "phone")
    autocomplete_fields = ("user",)
