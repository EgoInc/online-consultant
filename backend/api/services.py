"""Ready API orchestration. Student algorithms live in catalog/engine.py."""

from copy import deepcopy

from django.conf import settings

from catalog.engine import CatalogEngine
from . import mocks
from .exceptions import IntegrationError


def call_catalog(operation, *args, scenario="default"):
    if settings.CATALOG_PROVIDER not in ("mock", "real"):
        raise IntegrationError("INVALID_PROVIDER", "CATALOG_PROVIDER должен быть mock или real.")
    if settings.CATALOG_PROVIDER == "mock":
        function = getattr(mocks, operation)
        return function(*args, scenario=scenario) if operation == "search" else function(*args)
    if scenario != "default":
        raise IntegrationError("MOCK_SCENARIO_DISABLED", "Сценарии доступны только с CATALOG_PROVIDER=mock.", 400)
    try:
        return getattr(CatalogEngine(), operation)(*args)
    except NotImplementedError as exc:
        raise IntegrationError("CATALOG_NOT_IMPLEMENTED", "Алгоритмический модуль каталоговой ВКР ещё не реализован.") from exc


def create_store(data):
    source = {"type": data["source_type"]}
    details = {
        "operation": "catalog_import", "name": data["name"],
        "source_type": data["source_type"], "products_imported": 0,
        "next_step": "CatalogEngine.connect",
    }
    if data["source_type"] == "api":
        source.update(catalog_url=data["catalog_url"], product_url_template=data["product_url_template"])
    else:
        source["file"] = data["file"]
        details.update(file_name=data["file"].name, file_size=data["file"].size)
    # TODO: передать источник модулю интеграции и семантической нормализации:
    # загрузить весь каталог, нормализовать товары и сохранить их в нашей БД.
    # Подключение всегда идёт через реальную точку входа, даже при mock-поиске.
    try:
        return CatalogEngine().connect(data["name"], source)
    except NotImplementedError as exc:
        raise IntegrationError("CATALOG_NOT_IMPLEMENTED", "Метод ещё не реализован.", 501, details) from exc


def store_status(store_id):
    return call_catalog("status", store_id)


def search(store_id, data):
    return {
        "products": call_catalog("search", store_id, data["query"], data["constraints"], data["limit"], scenario=data["scenario"]),
        "mode": settings.CATALOG_PROVIDER,
    }


def real_dialog(store_id, data):
    """Connect the chosen generative service here when it is available."""
    raise IntegrationError("DIALOG_NOT_IMPLEMENTED", "Подключение генеративной модели ещё не реализовано. Выберите DIALOG_PROVIDER=mock.")


def dialog(store_id, data):
    if settings.CATALOG_PROVIDER not in ("mock", "real"):
        raise IntegrationError("INVALID_PROVIDER", "CATALOG_PROVIDER должен быть mock или real.")
    if settings.CATALOG_PROVIDER == "real" and data["scenario"] != "default":
        raise IntegrationError("MOCK_SCENARIO_DISABLED", "Сценарии доступны только с CATALOG_PROVIDER=mock.", 400)
    if settings.DIALOG_PROVIDER == "real":
        return real_dialog(store_id, data)
    if settings.DIALOG_PROVIDER != "mock":
        raise IntegrationError("INVALID_PROVIDER", "DIALOG_PROVIDER должен быть mock или real.")
    call_catalog("status", store_id, scenario=data["scenario"])
    state = deepcopy(data["state"])
    if data["scenario"] == "default":
        state = mocks.update_state(data["message"], state, store_id)
    products = call_catalog("search", store_id, data["message"], state["constraints"], 10, scenario=data["scenario"])
    return mocks.dialog_response(state, products, data["scenario"], settings.CATALOG_PROVIDER)
