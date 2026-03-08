import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from enums.llm_provider import LLMProvider
from utils.get_dynamic_models import (
    get_presentation_outline_model_with_chunks,
    get_presentation_outline_model_with_n_slides,
    get_presentation_structure_model_with_n_slides,
)
from utils.llm_client_error_handler import handle_llm_client_exceptions
from utils.llm_provider import get_llm_provider, get_model
from utils.schema_utils import add_field_in_schema, ensure_strict_json_schema, remove_fields_from_schema


class TestLlmProvider(unittest.TestCase):
    def test_get_llm_provider_invalid(self):
        with patch("utils.llm_provider.get_llm_provider_env", return_value="invalid"):
            with self.assertRaises(HTTPException):
                get_llm_provider()

    def test_get_model_openai_default(self):
        with patch("utils.llm_provider.get_llm_provider_env", return_value="openai"), \
            patch("utils.llm_provider.get_openai_model_env", return_value=None):
            model = get_model()
        self.assertTrue(model)


class TestSchemaUtils(unittest.TestCase):
    def test_remove_fields_from_schema(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        updated = remove_fields_from_schema(schema, ["a"])
        self.assertNotIn("a", updated.get("properties", {}))

    def test_add_field_in_schema(self):
        schema = {"type": "object", "properties": {}}
        updated = add_field_in_schema(schema, {"b": {"type": "number"}}, required=True)
        self.assertIn("b", updated["properties"])
        self.assertIn("b", updated["required"])

    def test_ensure_strict_json_schema_adds_required(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        strict = ensure_strict_json_schema(schema, path=(), root=schema)
        self.assertIn("required", strict)


class TestDynamicModels(unittest.TestCase):
    def test_outline_model_with_n_slides(self):
        Model = get_presentation_outline_model_with_n_slides(2)
        instance = Model(slides=[{"content": "a" * 100}, {"content": "b" * 100}])
        self.assertEqual(len(instance.slides), 2)

    def test_outline_model_with_chunks(self):
        Model = get_presentation_outline_model_with_chunks(1, 2)
        instance = Model(slides=[{"content": "a" * 100, "chunk_refs": [0]}])
        self.assertEqual(instance.slides[0].chunk_refs, [0])

    def test_structure_model_with_n_slides(self):
        Model = get_presentation_structure_model_with_n_slides(2)
        instance = Model(slides=[0, 1])
        self.assertEqual(instance.slides, [0, 1])


class TestLlmClientErrorHandler(unittest.TestCase):
    def test_handle_unknown_exception(self):
        exc = Exception("boom")
        http_exc = handle_llm_client_exceptions(exc)
        self.assertEqual(http_exc.status_code, 500)
