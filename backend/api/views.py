from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .exceptions import IntegrationError
from .serializers import (
    DialogRequestSerializer, DialogResponseSerializer, ErrorSerializer, HealthSerializer,
    SearchRequestSerializer, SearchResponseSerializer, StoreCreateRequestSerializer,
    StoreCreateResponseSerializer, StoreStatusSerializer,
)

ERRORS = {400: ErrorSerializer, 404: ErrorSerializer, 502: ErrorSerializer, 503: ErrorSerializer}


def validated(serializer_type, data):
    serializer = serializer_type(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def output(serializer_type, data, status=200):
    # A provider must obey the same public contract as the mock implementation.
    serializer = serializer_type(data=data)
    if not serializer.is_valid():
        raise IntegrationError("INVALID_PROVIDER_RESPONSE", "Подключённый модуль вернул ответ, не соответствующий контракту.", 502)
    return Response(serializer.data, status=status)


class HealthView(APIView):
    @extend_schema(responses={200: HealthSerializer, 503: ErrorSerializer}, tags=["Сервис"], summary="Liveness API и выбранные провайдеры")
    def get(self, request):
        if settings.CATALOG_PROVIDER not in ("mock", "real") or settings.DIALOG_PROVIDER not in ("mock", "real"):
            raise IntegrationError("INVALID_PROVIDER", "Проверьте настройки провайдеров.")
        return output(HealthSerializer, {"status": "ok", "provider": settings.CATALOG_PROVIDER, "dialog_provider": settings.DIALOG_PROVIDER})


class StoreCreateView(APIView):
    parser_classes = [JSONParser, MultiPartParser]

    @extend_schema(
        request={"application/json": StoreCreateRequestSerializer, "multipart/form-data": StoreCreateRequestSerializer},
        responses={202: StoreCreateResponseSerializer, 501: ErrorSerializer, **ERRORS},
        tags=["Магазины"], summary="Подключить источник каталога",
        description=(
            "API принимает и проверяет настоящий запрос подключения. Для source_type=api передайте "
            "JSON с name, catalog_url и product_url_template (HTTP(S) URL с одной подстановкой {id}). "
            "Для source_type=file передайте multipart/form-data с name и непустым file (.xml/.yml, "
            "до 10 МиБ). Поля другого способа подключения не передаются.\n\n"
            "Целевая обработка: получить весь каталог через API/файл → определить товары, поля и "
            "единицы измерения → семантически нормализовать → сохранить в нашей БД. Поиск должен "
            "работать с нормализованным каталогом, а не перенаправлять фильтры внешнему магазину.\n\n"
            "Точка подключения — CatalogEngine.connect в catalog/engine.py. Пока она пуста, "
            "возвращается HTTP 501 CATALOG_NOT_IMPLEMENTED с безопасными метаданными принятого запроса "
            "и products_imported=0. Каталог не загружается, товары и магазин в БД не сохраняются; "
            "фиктивный успешный импорт не возвращается. Это действует и при CATALOG_PROVIDER=mock. "
            "HTTP 202 станет доступен после реализации модуля интеграции."
        ),
        examples=[
            OpenApiExample(
                "ApiCatalog", summary="Подключение через API магазина", request_only=True,
                media_type="application/json",
                value={"name": "Магазин освещения", "source_type": "api", "catalog_url": "https://shop.example.com/api/products", "product_url_template": "https://shop.example.com/api/products/{id}"},
            ),
            OpenApiExample(
                "ImportNotImplemented", summary="Источник принят, модуль импорта ещё не реализован",
                response_only=True, status_codes=["501"],
                value={"code": "CATALOG_NOT_IMPLEMENTED", "message": "Метод ещё не реализован.", "details": {"operation": "catalog_import", "name": "Магазин освещения", "source_type": "api", "products_imported": 0, "next_step": "CatalogEngine.connect"}},
            ),
        ],
    )
    def post(self, request):
        return output(StoreCreateResponseSerializer, services.create_store(validated(StoreCreateRequestSerializer, request.data)), 202)


class StoreStatusView(APIView):
    @extend_schema(responses={200: StoreStatusSerializer, **ERRORS}, tags=["Магазины"], summary="Получить статус подготовки каталога")
    def get(self, request, store_id):
        return output(StoreStatusSerializer, services.store_status(store_id))


class ProductSearchView(APIView):
    @extend_schema(
        request=SearchRequestSerializer,
        responses={200: SearchResponseSerializer, **ERRORS},
        tags=["Поиск товаров"],
        summary="Найти товары и их характеристики",
        description=(
            "Принимает query и необязательные структурированные constraints. Возвращает products: "
            "товары с ценой, наличием и attributes — характеристиками с ключом, подписью, значением "
            "и единицей измерения. Этот endpoint не формирует реплику ассистента; для чата используйте "
            "POST /api/v1/stores/{store_id}/dialog/messages.\n\n"
            "В mock-режиме возвращаются фиксированные товары без поиска и ранжирования. "
            "Поле scenario доступно только для mock."
        ),
    )
    def post(self, request, store_id):
        return output(SearchResponseSerializer, services.search(store_id, validated(SearchRequestSerializer, request.data)))


class DialogMessageView(APIView):
    @extend_schema(
        request=DialogRequestSerializer,
        responses={200: DialogResponseSerializer, **ERRORS},
        tags=["Чат"],
        summary="Отправить сообщение в чат",
        description=(
            "Основной endpoint для диалога покупателя с консультантом. При первом сообщении достаточно "
            "передать message. При следующем передайте новое message и state из предыдущего ответа. "
            "Например, фраза «Можно до 100 тысяч» обновляет бюджет, сохраняя остальные требования.\n\n"
            "Ответ содержит assistantMessage (реплика ассистента), state (требования constraints и "
            "выбранные selectedProductIds), products (товары с характеристиками attributes), "
            "action (действие для интерфейса) и mode (mock/real каталога). "
            "История сообщений и сессии на сервере не хранятся; клиент хранит переписку и передаёт "
            "формализованный state явно. При смене магазина клиент сбрасывает state.\n\n"
            "Для проверки интерфейса в mock-режиме доступны scenario: default — сценарный диалог; "
            "clarification — уточнение (action=clarify); results — товары (action=results); "
            "empty — нет результатов (action=no_results); conflict — конфликт требований "
            "(action=conflict); slow — задержка ответа; error — ошибка 503 MOCK_UNAVAILABLE. "
            "В сценариях уточнения, отсутствия результатов и конфликта products пуст. "
            "Остальные ошибки возвращаются в формате code/message: 400 — некорректный запрос, "
            "404 — магазин не найден, 502 — неверный ответ подключённого модуля, "
            "503 — модуль недоступен или ещё не реализован.\n\n"
            "Пока DIALOG_PROVIDER=mock распознаёт только демонстрационные фразы о бюджете, "
            "лёгком весе, автономности и отмене важности веса. Это заглушка, а не подключённая LLM."
        ),
        examples=[
            OpenApiExample(
                "FirstMessage", summary="Первое сообщение",
                value={"message": "Нужен лёгкий ноутбук до 80 тысяч"},
                request_only=True,
            ),
            OpenApiExample(
                "ContinueWithState", summary="Продолжение с текущими требованиями",
                value={
                    "message": "Покажи варианты",
                    "state": {
                        "constraints": [
                            {"attribute": "price", "operator": "lte", "value": 80000, "priority": "required", "label": "Бюджет"},
                            {"attribute": "weight_kg", "operator": "prefer_low", "priority": "important", "label": "Небольшой вес"},
                        ],
                        "selectedProductIds": ["laptop-a"],
                    },
                },
                request_only=True,
            ),
            OpenApiExample(
                "ChangeBudget", summary="Изменение бюджета с сохранением контекста",
                value={
                    "message": "Можно до 100 тысяч",
                    "state": {
                        "constraints": [
                            {"attribute": "price", "operator": "lte", "value": 80000, "priority": "required", "label": "Бюджет"},
                            {"attribute": "weight_kg", "operator": "prefer_low", "priority": "important", "label": "Небольшой вес"},
                        ],
                        "selectedProductIds": ["laptop-a"],
                    },
                },
                request_only=True,
            ),
            OpenApiExample(
                "ChatResults", summary="Ответ: новый бюджет, прежние требования и товары",
                value={
                    "assistantMessage": "Ниже фиксированные демонстрационные товары. Поиск и ранжирование пока не реализованы; требования сохранены отдельно от истории сообщений.",
                    "state": {
                        "constraints": [
                            {"attribute": "price", "operator": "lte", "value": 100000, "priority": "required", "label": "Бюджет"},
                            {"attribute": "weight_kg", "operator": "prefer_low", "priority": "important", "label": "Небольшой вес"},
                        ],
                        "selectedProductIds": ["laptop-a"],
                    },
                    "products": [{
                        "id": "laptop-a", "title": "Учебный ноутбук A", "price": 79990,
                        "currency": "RUB", "score": 0.91, "availability": "in_stock",
                        "attributes": [{"key": "weight_kg", "label": "Вес", "value": 1.1, "unit": "кг"}],
                    }],
                    "action": "results", "mode": "mock",
                },
                response_only=True, status_codes=["200"],
            ),
            OpenApiExample(
                "Clarification", summary="Ответ: нужно уточнить требования",
                value={
                    "assistantMessage": "Какой бюджет вы рассматриваете? Это сценарный mock-ответ.",
                    "state": {"constraints": [], "selectedProductIds": []},
                    "products": [], "action": "clarify", "mode": "mock",
                },
                response_only=True, status_codes=["200"],
            ),
            OpenApiExample(
                "CatalogUnavailable", summary="Ошибка сценария error",
                value={"code": "MOCK_UNAVAILABLE", "message": "Демонстрационная ошибка каталожной подсистемы."},
                response_only=True, status_codes=["503"],
            ),
        ],
    )
    def post(self, request, store_id):
        return output(DialogResponseSerializer, services.dialog(store_id, validated(DialogRequestSerializer, request.data)))
