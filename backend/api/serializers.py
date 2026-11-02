"""Canonical public DTOs; /openapi.json is generated from these serializers."""

import math
from collections.abc import Mapping
from pathlib import PurePath

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

SCENARIOS = ["default", "clarification", "results", "empty", "conflict", "error", "slow"]
MODES = ["mock", "real"]


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Неизвестное поле." for key in sorted(unknown, key=str)})
        return super().to_internal_value(data)


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        try:
            value = super().to_internal_value(data)
        except OverflowError as exc:
            raise serializers.ValidationError("Ожидается конечное число.") from exc
        if isinstance(data, bool) or not math.isfinite(value):
            raise serializers.ValidationError("Ожидается конечное число.")
        return value


def scalar(value):
    if isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    return False


@extend_schema_field({"oneOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]})
class AttributeValueField(serializers.JSONField):
    def to_internal_value(self, data):
        if not scalar(data):
            raise serializers.ValidationError("Ожидается строка, конечное число или boolean.")
        return data


@extend_schema_field({"oneOf": [
    {"type": "string"}, {"type": "number"}, {"type": "boolean"},
    {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "number"}]}},
], "nullable": True})
class ConstraintValueField(serializers.JSONField):
    def to_internal_value(self, data):
        if data is None or scalar(data):
            return data
        if isinstance(data, list) and all(
            isinstance(item, (str, int, float)) and not isinstance(item, bool) and scalar(item)
            for item in data
        ):
            return data
        raise serializers.ValidationError("Ожидается скалярное значение или массив строк/чисел.")


class ProductAttributeSerializer(StrictSerializer):
    key = serializers.CharField(max_length=160)
    label = serializers.CharField(max_length=200)
    value = AttributeValueField()
    unit = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ProductSerializer(StrictSerializer):
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True)
    price = FiniteFloatField(min_value=0)
    currency = serializers.CharField(min_length=3, max_length=3)
    score = FiniteFloatField(min_value=0, max_value=1)
    availability = serializers.ChoiceField(choices=["in_stock", "out_of_stock", "unknown"])
    image_url = serializers.URLField(required=False, allow_null=True)
    product_url = serializers.URLField(required=False, allow_null=True)
    attributes = ProductAttributeSerializer(many=True)


class ConstraintSerializer(StrictSerializer):
    attribute = serializers.CharField(max_length=160)
    operator = serializers.ChoiceField(choices=[
        "eq", "neq", "lt", "lte", "gt", "gte", "in", "contains", "prefer_low", "prefer_high",
    ])
    value = ConstraintValueField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=["required", "important", "optional"], default="required")
    label = serializers.CharField(required=False, allow_null=True, max_length=200)

    def validate(self, attrs):
        operator = attrs["operator"]
        value = attrs.get("value")
        if operator in ("prefer_low", "prefer_high"):
            return attrs
        if value is None:
            raise serializers.ValidationError({"value": "Значение обязательно для этого оператора."})
        if operator == "in" and (not isinstance(value, list) or not value):
            raise serializers.ValidationError({"value": "Для in нужен непустой массив."})
        if operator != "in" and isinstance(value, list):
            raise serializers.ValidationError({"value": "Массив допустим только для in."})
        if operator in ("lt", "lte", "gt", "gte") and (
            not isinstance(value, (int, float)) or isinstance(value, bool)
        ):
            raise serializers.ValidationError({"value": "Для сравнения нужно число."})
        if operator == "contains" and not isinstance(value, str):
            raise serializers.ValidationError({"value": "Для contains нужна строка."})
        return attrs


class DialogStateSerializer(StrictSerializer):
    constraints = ConstraintSerializer(many=True, max_length=100)
    selectedProductIds = serializers.ListField(child=serializers.CharField(max_length=200), max_length=100)


def empty_state():
    return {"constraints": [], "selectedProductIds": []}


class SearchRequestSerializer(StrictSerializer):
    query = serializers.CharField(max_length=4000)
    constraints = ConstraintSerializer(many=True, required=False, default=list, max_length=100)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=10)
    scenario = serializers.ChoiceField(choices=SCENARIOS, default="default", help_text="Только для mock-провайдера.")


class SearchResponseSerializer(StrictSerializer):
    products = ProductSerializer(many=True)
    mode = serializers.ChoiceField(choices=MODES)


class DialogRequestSerializer(StrictSerializer):
    message = serializers.CharField(max_length=4000)
    state = DialogStateSerializer(required=False, default=empty_state)
    scenario = serializers.ChoiceField(choices=SCENARIOS, default="default", help_text="Только для mock-провайдера.")


class DialogResponseSerializer(StrictSerializer):
    assistantMessage = serializers.CharField()
    state = DialogStateSerializer()
    products = ProductSerializer(many=True)
    action = serializers.ChoiceField(choices=["clarify", "results", "no_results", "conflict"])
    mode = serializers.ChoiceField(choices=MODES)


@extend_schema_field(OpenApiTypes.BINARY)
class CatalogFileField(serializers.FileField):
    """Uploaded source only; parsing belongs to the student integration module."""


class StoreCreateRequestSerializer(StrictSerializer):
    name = serializers.CharField(max_length=200)
    source_type = serializers.ChoiceField(choices=["api", "file"])
    catalog_url = serializers.URLField(required=False, max_length=2048, validators=[URLValidator(schemes=["http", "https"])])
    product_url_template = serializers.CharField(required=False, max_length=2048, help_text="HTTP(S) URL товара с подстановкой {id}.")
    file = CatalogFileField(required=False, max_length=255, help_text="Непустой .xml или .yml файл, не более 10 МиБ.")

    def validate_product_url_template(self, value):
        if value.count("{id}") != 1:
            raise serializers.ValidationError("URL должен содержать одну подстановку {id}.")
        try:
            URLValidator(schemes=["http", "https"])(value.replace("{id}", "example-product"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError("Ожидается корректный HTTP(S) URL товара.") from exc
        return value

    def validate_file(self, value):
        if PurePath(value.name).suffix.lower() not in (".xml", ".yml"):
            raise serializers.ValidationError("Поддерживаются файлы .xml и .yml.")
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Размер файла не должен превышать 10 МиБ.")
        return value

    def validate(self, attrs):
        if attrs["source_type"] == "api":
            missing = {key: "Обязательное поле для API." for key in ("catalog_url", "product_url_template") if key not in attrs}
            if "file" in attrs:
                missing["file"] = "Для API файл не передаётся."
        else:
            missing = {} if "file" in attrs else {"file": "Обязательное поле для загрузки каталога."}
            for key in ("catalog_url", "product_url_template"):
                if key in attrs:
                    missing[key] = "Для файла URL не передаётся."
        if missing:
            raise serializers.ValidationError(missing)
        return attrs


class StoreCreateResponseSerializer(StrictSerializer):
    store_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["pending"])


class StoreStatusSerializer(StrictSerializer):
    store_id = serializers.CharField()
    status = serializers.ChoiceField(choices=["pending", "processing", "needs_review", "ready", "failed"])
    products = serializers.IntegerField(min_value=0)
    fields_detected = serializers.IntegerField(min_value=0)
    auto_mapped = serializers.IntegerField(min_value=0)
    requires_review = serializers.IntegerField(min_value=0)


class HealthSerializer(StrictSerializer):
    status = serializers.ChoiceField(choices=["ok"])
    provider = serializers.ChoiceField(choices=MODES)
    dialog_provider = serializers.ChoiceField(choices=MODES)


class ErrorSerializer(StrictSerializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(required=False)
