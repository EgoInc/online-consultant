from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from .mocks import products_for
from .serializers import DialogRequestSerializer, DialogResponseSerializer


@override_settings(CATALOG_PROVIDER="mock", DIALOG_PROVIDER="mock")
class IntegrationApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.search_url = "/api/v1/stores/demo-store/search"
        self.dialog_url = "/api/v1/stores/demo-store/dialog/messages"

    def post(self, url, data):
        return self.client.post(url, data, format="json")

    def test_health_docs_and_schema(self):
        self.assertEqual(self.client.get("/health").json(), {
            "status": "ok", "provider": "mock", "dialog_provider": "mock",
        })
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)
        schema = SchemaGenerator().get_schema()
        self.assertIn(self.dialog_url.replace("demo-store", "{store_id}"), schema["paths"])
        product = schema["components"]["schemas"]["Product"]
        self.assertIn("attributes", product["required"])

    def test_search_returns_normalized_mock_products_and_honors_limit(self):
        response = self.post(self.search_url, {"query": "ноутбук", "limit": 2})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "mock")
        self.assertEqual([p["id"] for p in body["products"]], ["laptop-a", "laptop-b"])
        self.assertEqual(body["products"][0]["attributes"][0]["unit"], "кг")

    def test_published_schema_exposes_chat_with_executable_multiturn_examples(self):
        schema = self.client.get("/openapi.json").json()
        operation = schema["paths"]["/api/v1/stores/{store_id}/dialog/messages"]["post"]
        self.assertEqual(operation["tags"], ["Чат"])
        self.assertEqual(operation["summary"], "Отправить сообщение в чат")
        request = operation["requestBody"]["content"]["application/json"]
        response = operation["responses"]["200"]["content"]["application/json"]
        self.assertTrue(request["schema"]["$ref"].endswith("/DialogRequest"))
        self.assertTrue(response["schema"]["$ref"].endswith("/DialogResponse"))
        self.assertEqual(set(request["examples"]), {"FirstMessage", "ContinueWithState", "ChangeBudget"})
        self.assertIn("ChatResults", response["examples"])
        self.assertIn("Clarification", response["examples"])
        for example in request["examples"].values():
            serializer = DialogRequestSerializer(data=example["value"])
            self.assertTrue(serializer.is_valid(), serializer.errors)
        for example in response["examples"].values():
            serializer = DialogResponseSerializer(data=example["value"])
            self.assertTrue(serializer.is_valid(), serializer.errors)
        result = response["examples"]["ChatResults"]["value"]
        self.assertTrue({"assistantMessage", "state", "products"}.issubset(result))
        self.assertEqual(result["state"]["constraints"][0]["value"], 100000)
        self.assertIn("attributes", result["products"][0])
        self.assertEqual(schema["paths"]["/api/v1/stores/{store_id}/search"]["post"]["tags"], ["Поиск товаров"])

    def test_stores_never_share_fixture_products(self):
        laptop_ids = {p["id"] for p in self.post(self.search_url, {"query": "товар"}).json()["products"]}
        lights = self.post("/api/v1/stores/demo-lighting/search", {"query": "товар"}).json()["products"]
        self.assertTrue(all(product["id"].startswith("light-") for product in lights))
        self.assertTrue(laptop_ids.isdisjoint({p["id"] for p in lights}))

    def test_api_connection_calls_student_module_and_reports_unimplemented(self):
        request = {
            "name": "Магазин освещения", "source_type": "api",
            "catalog_url": "https://shop.example.com/products?token=private-token",
            "product_url_template": "https://shop.example.com/products/{id}",
        }
        with patch("catalog.engine.CatalogEngine.connect", side_effect=NotImplementedError) as engine:
            response = self.post("/api/v1/stores", request)
        self.assertEqual(response.status_code, 501)
        engine.assert_called_once_with(request["name"], {
            "type": "api", "catalog_url": request["catalog_url"],
            "product_url_template": request["product_url_template"],
        })
        self.assertEqual(response.json(), {
            "code": "CATALOG_NOT_IMPLEMENTED", "message": "Метод ещё не реализован.",
            "details": {
                "operation": "catalog_import", "name": request["name"], "source_type": "api",
                "products_imported": 0, "next_step": "CatalogEngine.connect",
            },
        })
        self.assertNotIn("private-token", response.content.decode())

    def test_file_connection_passes_uploaded_source_and_returns_only_metadata(self):
        content = b"<yml_catalog>private-catalog-content</yml_catalog>"
        upload = SimpleUploadedFile("lighting.yml", content, content_type="application/xml")
        received = {}

        def unimplemented(name, source):
            received.update(name=name, source_type=source["type"], content=source["file"].read())
            raise NotImplementedError

        with patch("catalog.engine.CatalogEngine.connect", side_effect=unimplemented) as engine:
            response = self.client.post("/api/v1/stores", {"name": "Освещение", "source_type": "file", "file": upload}, format="multipart")
        self.assertEqual(response.status_code, 501)
        engine.assert_called_once()
        self.assertEqual(received, {"name": "Освещение", "source_type": "file", "content": content})
        self.assertEqual(response.json()["details"]["file_name"], "lighting.yml")
        self.assertEqual(response.json()["details"]["file_size"], len(content))
        self.assertEqual(response.json()["details"]["products_imported"], 0)
        self.assertNotIn("private-catalog-content", response.content.decode())

    def test_connection_validation_precedes_the_student_module(self):
        base = {"name": "Освещение", "source_type": "api", "catalog_url": "https://shop.example.com/products", "product_url_template": "https://shop.example.com/products/{id}"}
        invalid = [
            {}, {**base, "name": ""}, {**base, "source_type": "unknown"},
            {**base, "catalog_url": "ftp://shop.example.com/products"},
            {**base, "product_url_template": "https://shop.example.com/products"},
            {**base, "product_url_template": "ftp://shop.example.com/products/{id}"},
            {**base, "product_url_template": "https://shop.example.com/{id}/{id}"},
            {key: value for key, value in base.items() if key != "catalog_url"},
            {"name": "Освещение", "source_type": "file"},
            {**base, "credentials": {"token": "secret"}},
        ]
        with patch("catalog.engine.CatalogEngine.connect") as engine:
            for body in invalid:
                with self.subTest(body=body):
                    response = self.post("/api/v1/stores", body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["code"], "INVALID_REQUEST")
        engine.assert_not_called()

    def test_connection_rejects_invalid_uploads_and_mixed_source_fields(self):
        cases = [
            ("catalog.csv", b"id,name", {}),
            ("catalog.xml", b"", {}),
            ("catalog.xml", b"x" * (10 * 1024 * 1024 + 1), {}),
            ("catalog.yml", b"<catalog/>", {"catalog_url": "https://shop.example.com/products"}),
        ]
        with patch("catalog.engine.CatalogEngine.connect") as engine:
            for name, content, extra in cases:
                with self.subTest(file=name, size=len(content), extra=extra):
                    upload = SimpleUploadedFile(name, content, content_type="application/xml")
                    response = self.client.post("/api/v1/stores", {"name": "Освещение", "source_type": "file", "file": upload, **extra}, format="multipart")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["code"], "INVALID_REQUEST")
        engine.assert_not_called()

    @override_settings(CATALOG_PROVIDER="real")
    def test_connection_unimplemented_status_does_not_depend_on_mock_provider(self):
        response = self.post("/api/v1/stores", {
            "name": "Освещение", "source_type": "api", "catalog_url": "https://shop.example.com/products",
            "product_url_template": "https://shop.example.com/products/{id}",
        })
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.json()["code"], "CATALOG_NOT_IMPLEMENTED")

    def test_connection_schema_documents_both_sources_and_unimplemented_response(self):
        schema = self.client.get("/openapi.json").json()
        operation = schema["paths"]["/api/v1/stores"]["post"]
        self.assertEqual(set(operation["requestBody"]["content"]), {"application/json", "multipart/form-data"})
        self.assertIn("501", operation["responses"])
        request = schema["components"]["schemas"]["StoreCreateRequest"]
        self.assertEqual(request["properties"]["file"]["format"], "binary")
        self.assertIn("CatalogEngine.connect", operation["description"])

    def test_unknown_store_uses_standard_error_envelope(self):
        response = self.post("/api/v1/stores/unknown/search", {"query": "товар"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "STORE_NOT_FOUND")

    def test_multiturn_budget_update_preserves_other_constraints_and_selection(self):
        first = self.post(self.dialog_url, {"message": "Нужен лёгкий ноутбук до 80 тысяч с хорошей батареей"})
        self.assertEqual(first.status_code, 200)
        state = first.json()["state"]
        self.assertEqual(next(c["value"] for c in state["constraints"] if c["attribute"] == "price"), 80000)
        state["selectedProductIds"] = ["laptop-a", "laptop-b"]
        second = self.post(self.dialog_url, {"message": "Можно до 100000", "state": state})
        self.assertEqual(second.status_code, 200)
        updated = second.json()["state"]
        self.assertEqual(next(c["value"] for c in updated["constraints"] if c["attribute"] == "price"), 100000)
        self.assertEqual({c["attribute"] for c in updated["constraints"]}, {"price", "weight_kg", "battery_hours"})
        self.assertEqual(updated["selectedProductIds"], ["laptop-a", "laptop-b"])
        third = self.post(self.dialog_url, {"message": "Вес больше не важен", "state": updated})
        self.assertNotIn("weight_kg", {c["attribute"] for c in third.json()["state"]["constraints"]})

    def test_manual_state_is_authoritative_and_requests_do_not_share_context(self):
        state = {"constraints": [{"attribute": "memory_gb", "operator": "gte", "value": 16, "priority": "required"}], "selectedProductIds": ["laptop-a"]}
        response = self.post(self.dialog_url, {"message": "Покажи варианты", "state": state})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], {
            "constraints": [{**state["constraints"][0], "label": None}],
            "selectedProductIds": state["selectedProductIds"],
        })
        self.assertNotIn("label", state["constraints"][0])
        independent = self.post(self.dialog_url, {"message": "Покажи варианты"})
        self.assertEqual(independent.json()["state"], {"constraints": [], "selectedProductIds": []})

    def test_budget_update_does_not_remove_an_independent_lower_bound(self):
        state = {"constraints": [
            {"attribute": "price", "operator": "gte", "value": 50000, "priority": "required"},
            {"attribute": "price", "operator": "lte", "value": 80000, "priority": "required"},
        ], "selectedProductIds": []}
        response = self.post(self.dialog_url, {"message": "Можно до 100000", "state": state})
        self.assertEqual(response.status_code, 200)
        bounds = {c["operator"]: c["value"] for c in response.json()["state"]["constraints"]}
        self.assertEqual(bounds, {"gte": 50000, "lte": 100000})

    def test_state_limit_returns_client_error_when_a_demo_rule_adds_a_constraint(self):
        state = {"constraints": [
            {"attribute": f"attribute-{index}", "operator": "eq", "value": True}
            for index in range(100)
        ], "selectedProductIds": []}
        response = self.post(self.dialog_url, {"message": "До 80000", "state": state})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "STATE_LIMIT_EXCEEDED")

    def test_oversized_scripted_budget_is_a_client_error(self):
        response = self.post(self.dialog_url, {"message": "До " + "9" * 400})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_REQUEST")

    def test_scenarios_support_empty_clarification_and_conflict(self):
        for scenario, action in (("clarification", "clarify"), ("empty", "no_results"), ("conflict", "conflict")):
            with self.subTest(scenario=scenario):
                response = self.post(self.dialog_url, {"message": "Покажи варианты", "scenario": scenario})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["action"], action)
                self.assertEqual(response.json()["products"], [])

    def test_mock_error_and_slow_scenarios(self):
        error = self.post(self.dialog_url, {"message": "Покажи варианты", "scenario": "error"})
        self.assertEqual(error.status_code, 503)
        self.assertEqual(error.json()["code"], "MOCK_UNAVAILABLE")
        with patch("api.mocks.time.sleep") as sleep:
            response = self.post(self.search_url, {"query": "ноутбук", "scenario": "slow"})
        self.assertEqual(response.status_code, 200)
        sleep.assert_called_once_with(1.5)

    def test_invalid_nested_inputs_are_rejected_before_provider_call(self):
        invalid = [
            {"message": ""},
            {"message": "Привет", "state": {"constraints": [], "selectedProductIds": "not-list"}},
            {"message": "Привет", "state": {"constraints": [{"attribute": "price", "operator": "lte", "value": "cheap"}], "selectedProductIds": []}},
            {"message": "Привет", "state": {"constraints": [{"attribute": "price", "operator": "in", "value": 10}], "selectedProductIds": []}},
            {"message": "Привет", "scenario": "missing"},
            {"message": "Привет", "state": {"constraints": [], "selectedProductIds": [], "secret": True}},
            {"message": "Привет", "state": {"constraints": [{"attribute": "price", "operator": "lte", "value": 10 ** 400}], "selectedProductIds": []}},
        ]
        with patch("api.services.dialog") as provider:
            for body in invalid:
                with self.subTest(body=body):
                    response = self.post(self.dialog_url, body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["code"], "INVALID_REQUEST")
        provider.assert_not_called()
        self.assertEqual(self.post(self.search_url, {"query": "", "limit": 0}).status_code, 400)

    def test_invalid_json_uses_standard_error(self):
        response = self.client.post(self.dialog_url, data="{invalid", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "INVALID_REQUEST")

    @override_settings(CATALOG_PROVIDER="real")
    def test_real_catalog_is_explicitly_unimplemented_without_mock_fallback(self):
        response = self.post(self.search_url, {"query": "ноутбук"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "CATALOG_NOT_IMPLEMENTED")
        response = self.post(self.search_url, {"query": "ноутбук", "scenario": "results"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "MOCK_SCENARIO_DISABLED")

    @override_settings(CATALOG_PROVIDER="real")
    def test_real_catalog_calls_the_student_entry_point(self):
        with patch("catalog.engine.CatalogEngine.search", return_value=products_for("demo-store")[:1]) as engine:
            response = self.post(self.search_url, {"query": "ноутбук", "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "real")
        engine.assert_called_once_with("demo-store", "ноутбук", [], 1)

    @override_settings(CATALOG_PROVIDER="real")
    def test_mock_dialog_supports_empty_results_from_a_real_catalog(self):
        with patch("catalog.engine.CatalogEngine.status", return_value={}), patch("catalog.engine.CatalogEngine.search", return_value=[]):
            response = self.post(self.dialog_url, {"message": "Покажи варианты"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["products"], [])
        self.assertEqual(response.json()["action"], "no_results")
        self.assertEqual(response.json()["mode"], "real")

    @override_settings(DIALOG_PROVIDER="real")
    def test_real_dialog_has_an_explicit_integration_hook(self):
        response = self.post(self.dialog_url, {"message": "Привет"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "DIALOG_NOT_IMPLEMENTED")

    def test_invalid_provider_output_is_a_gateway_error(self):
        with patch("api.services.search", return_value={"products": [{"id": "broken"}], "mode": "mock"}):
            response = self.post(self.search_url, {"query": "ноутбук"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "INVALID_PROVIDER_RESPONSE")

    def test_nonfinite_provider_prices_are_rejected_before_json_rendering(self):
        for invalid_price in (float("nan"), float("inf"), 10 ** 400):
            with self.subTest(price=invalid_price):
                products = products_for("demo-store")[:1]
                products[0]["price"] = invalid_price
                with patch("api.services.search", return_value={"products": products, "mode": "mock"}):
                    response = self.post(self.search_url, {"query": "ноутбук"})
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()["code"], "INVALID_PROVIDER_RESPONSE")

    def test_cors_allows_configured_hosts_and_preflight(self):
        response = self.client.options(self.dialog_url, HTTP_ORIGIN="http://localhost:3000", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:3000")
        denied = self.client.get("/health", HTTP_ORIGIN="https://unconfigured.example")
        self.assertNotIn("Access-Control-Allow-Origin", denied)
