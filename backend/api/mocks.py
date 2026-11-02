"""Fixed products and scripted responses for frontend development."""

from copy import deepcopy
import math
import re
import time

from .exceptions import IntegrationError


def attribute(key, label, value, unit=None):
    return {"key": key, "label": label, "value": value, "unit": unit}


LAPTOPS = [
    {
        "id": "laptop-a", "title": "Учебный ноутбук A", "description": "Демонстрационный товар: самый лёгкий из трёх.",
        "price": 79990, "currency": "RUB", "score": 0.91, "availability": "in_stock",
        "image_url": None, "product_url": "https://example.com/products/laptop-a",
        "attributes": [attribute("weight_kg", "Вес", 1.1, "кг"), attribute("battery_hours", "Автономность", 10, "ч"), attribute("screen_inch", "Диагональ", 13.3, "дюйм"), attribute("memory_gb", "Оперативная память", 16, "ГБ")],
    },
    {
        "id": "laptop-b", "title": "Учебный ноутбук B", "description": "Демонстрационный товар: дольше работает без зарядки.",
        "price": 96990, "currency": "RUB", "score": 0.87, "availability": "in_stock",
        "image_url": None, "product_url": "https://example.com/products/laptop-b",
        "attributes": [attribute("weight_kg", "Вес", 1.4, "кг"), attribute("battery_hours", "Автономность", 15, "ч"), attribute("screen_inch", "Диагональ", 14, "дюйм"), attribute("memory_gb", "Оперативная память", 16, "ГБ")],
    },
    {
        "id": "laptop-c", "title": "Учебный ноутбук C", "description": "Демонстрационный товар с неполными данными об автономности.",
        "price": 64990, "currency": "RUB", "score": 0.79, "availability": "unknown",
        "image_url": None, "product_url": "https://example.com/products/laptop-c",
        "attributes": [attribute("weight_kg", "Вес", 1.8, "кг"), attribute("screen_inch", "Диагональ", 15.6, "дюйм"), attribute("memory_gb", "Оперативная память", 8, "ГБ")],
    },
]

LIGHTS = [
    {
        "id": "light-a", "title": "Учебный светильник A", "description": "Демонстрационный светильник с тёплым светом.",
        "price": 3990, "currency": "RUB", "score": 0.92, "availability": "in_stock",
        "image_url": None, "product_url": "https://example.com/products/light-a",
        "attributes": [attribute("power_w", "Мощность", 12, "Вт"), attribute("luminous_flux_lm", "Световой поток", 1000, "лм"), attribute("color_temperature_k", "Цветовая температура", 3000, "К"), attribute("dimmable", "Регулировка яркости", True)],
    },
    {
        "id": "light-b", "title": "Учебный светильник B", "description": "Демонстрационный светильник с нейтральным светом.",
        "price": 5490, "currency": "RUB", "score": 0.86, "availability": "in_stock",
        "image_url": None, "product_url": "https://example.com/products/light-b",
        "attributes": [attribute("power_w", "Мощность", 18, "Вт"), attribute("luminous_flux_lm", "Световой поток", 1600, "лм"), attribute("color_temperature_k", "Цветовая температура", 4000, "К"), attribute("dimmable", "Регулировка яркости", False)],
    },
    {
        "id": "light-c", "title": "Учебный светильник C", "description": "Демонстрационный товар без данных о световом потоке.",
        "price": 2490, "currency": "RUB", "score": 0.75, "availability": "out_of_stock",
        "image_url": None, "product_url": "https://example.com/products/light-c",
        "attributes": [attribute("power_w", "Мощность", 8, "Вт"), attribute("color_temperature_k", "Цветовая температура", 2700, "К")],
    },
]


def products_for(store_id):
    return deepcopy(LIGHTS if store_id == "demo-lighting" else LAPTOPS)


def ensure_store(store_id):
    if store_id not in ("demo-store", "demo-lighting"):
        raise IntegrationError("STORE_NOT_FOUND", "Магазин не найден. Для демо доступны demo-store и demo-lighting.", 404)


def status(store_id):
    ensure_store(store_id)
    return {
        "store_id": store_id, "status": "ready", "products": len(products_for(store_id)),
        "fields_detected": 8, "auto_mapped": 7, "requires_review": 1,
    }


def search(store_id, query, constraints, limit, scenario="default"):
    ensure_store(store_id)
    if scenario == "error":
        raise IntegrationError("MOCK_UNAVAILABLE", "Демонстрационная ошибка каталожной подсистемы.")
    if scenario == "slow":
        time.sleep(1.5)
    if scenario in ("empty", "clarification", "conflict"):
        return []
    # Fixed fixtures deliberately ignore query/constraints; thesis algorithms remain empty.
    return products_for(store_id)[:limit]


def update_state(message, state, store_id):
    """Recognize only the documented demo vocabulary; this is not NLP/LLM."""
    constraints = state["constraints"]

    def upsert(constraint):
        constraints[:] = [item for item in constraints if (
            item["attribute"], item["operator"]
        ) != (constraint["attribute"], constraint["operator"])]
        if len(constraints) >= 100:
            raise IntegrationError("STATE_LIMIT_EXCEEDED", "В состоянии допускается не более 100 требований.", 400)
        constraints.append(constraint)

    budget = re.search(r"до\s+(\d[\d ]*)(?:\s*(тыс(?:яч)?\.?))?", message, re.IGNORECASE)
    if budget:
        amount = int(budget[1].replace(" ", ""))
        if budget[2]:
            amount *= 1000
        try:
            finite = math.isfinite(amount)
        except OverflowError:
            finite = False
        if not finite:
            raise IntegrationError("INVALID_REQUEST", "Значение бюджета слишком велико для демонстрационного сценария.", 400)
        upsert({"attribute": "price", "operator": "lte", "value": amount, "priority": "required", "label": "Бюджет"})
    if store_id != "demo-lighting":
        if re.search(r"вес.*не\s*важ", message, re.IGNORECASE):
            constraints[:] = [item for item in constraints if item["attribute"] != "weight_kg"]
        elif re.search(r"л[её]гк", message, re.IGNORECASE):
            upsert({"attribute": "weight_kg", "operator": "prefer_low", "priority": "important", "label": "Небольшой вес"})
        if re.search(r"батар|заряд|автоном", message, re.IGNORECASE):
            upsert({"attribute": "battery_hours", "operator": "prefer_high", "priority": "important", "label": "Высокая автономность"})
    return state


def dialog_response(state, products, scenario, mode):
    if scenario == "clarification":
        action, answer = "clarify", "Какой бюджет вы рассматриваете? Это сценарный mock-ответ."
    elif scenario == "empty" or (scenario == "default" and not products):
        action, answer = "no_results", "В демонстрационном сценарии подходящих товаров нет. Попробуйте изменить требования."
    elif scenario == "conflict":
        action, answer = "conflict", "В демонстрационном сценарии требования конфликтуют. Уточните, какое из них важнее."
    else:
        action = "results"
        answer = (
            "Ниже фиксированные демонстрационные товары. Поиск и ранжирование пока не реализованы; требования сохранены отдельно от истории сообщений."
            if mode == "mock" else
            "Товары получены из подключённого каталога. Ответ диалога сформирован сценарной заглушкой; генеративная модель пока не подключена."
        )
    return {
        "assistantMessage": answer, "state": state, "products": products,
        "action": action, "mode": mode,
    }
