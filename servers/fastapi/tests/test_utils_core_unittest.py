import asyncio
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi import UploadFile

from utils.async_iterator import iterator_to_async
from utils.datetime_utils import get_current_utc_datetime
from utils.dict_utils import (
    deep_update,
    get_dict_at_path,
    get_dict_paths_with_key,
    has_more_than_n_keys,
    set_dict_at_path,
)
from utils.file_utils import (
    get_file_ext_or_none,
    get_file_name_with_random_uuid,
    get_original_file_name,
    replace_file_name,
    set_file_ext,
)
from utils.parsers import parse_bool_or_none
from utils.validators import validate_files
from utils.dummy_functions import do_nothing_async
import utils.error_handling as error_handling


class TestAsyncIterator(unittest.IsolatedAsyncioTestCase):
    async def test_iterator_to_async(self):
        def gen():
            yield 1
            yield 2

        async_gen = iterator_to_async(gen)
        result = []
        async for item in async_gen():
            result.append(item)
        self.assertEqual(result, [1, 2])


class TestDatetimeUtils(unittest.TestCase):
    def test_get_current_utc_datetime(self):
        dt = get_current_utc_datetime()
        self.assertIsNotNone(dt.tzinfo)


class TestParsers(unittest.TestCase):
    def test_parse_bool_or_none(self):
        self.assertTrue(parse_bool_or_none("true"))
        self.assertFalse(parse_bool_or_none("false"))
        self.assertIsNone(parse_bool_or_none(None))


class TestValidators(unittest.TestCase):
    def test_validate_files_rejects_size(self):
        file = MagicMock(spec=UploadFile)
        file.size = 6 * 1024 * 1024
        file.filename = "big.txt"
        file.content_type = "text/plain"
        with self.assertRaises(HTTPException):
            validate_files(file, nullable=False, multiple=False, max_size=5, accepted_types=["text/plain"])


class TestFileUtils(unittest.TestCase):
    def test_replace_and_restore_filename(self):
        new_name = replace_file_name("file.txt", "new")
        self.assertEqual(new_name, "new.txt")
        randomized = get_file_name_with_random_uuid("file.txt")
        self.assertTrue(randomized.endswith(".txt"))
        original = get_original_file_name("file----uuid.txt")
        self.assertEqual(original, "file.txt")

    def test_set_file_ext(self):
        self.assertEqual(set_file_ext("file", ".pptx"), "file.pptx")
        self.assertEqual(get_file_ext_or_none("file.txt"), ".txt")


class TestDictUtils(unittest.TestCase):
    def test_paths_and_update(self):
        data = {"a": {"b": [{"c": 1}]}}
        paths = get_dict_paths_with_key(data, "c")
        self.assertEqual(len(paths), 1)
        value = get_dict_at_path(data, paths[0])
        self.assertEqual(value, {"c": 1})
        set_dict_at_path(data, paths[0], {"c": 2})
        self.assertEqual(data["a"]["b"][0]["c"], 2)

    def test_deep_update_and_has_keys(self):
        original = {"a": {"b": 1}, "list": [{"x": 1}]}
        updates = {"a": {"c": 2}, "list": [{"x": 2}]}
        deep_update(original, updates)
        self.assertEqual(original["a"]["c"], 2)
        self.assertTrue(has_more_than_n_keys({"a": 1, "b": 2}, 1))


class TestDummyFunctions(unittest.IsolatedAsyncioTestCase):
    async def test_do_nothing_async(self):
        result = await do_nothing_async("noop")
        self.assertIsNone(result)


class TestErrorHandlingModule(unittest.TestCase):
    def test_module_import(self):
        self.assertTrue(hasattr(error_handling, "__file__"))
