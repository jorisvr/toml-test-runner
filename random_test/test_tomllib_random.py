#!/usr/bin/env python3

"""
Test "tomllib" on random valid TOML documents.
"""

import sys
import datetime
import functools
import io
import math
import random
import tomllib
import unittest

import gen_random_toml


def inject_random_testcases(n):
    """Decorator to inject a specified number of parameterized test cases."""

    def decorate(cls):
        for test_index in range(1, n+1):
            method_name = f"test_{test_index}"
            func = functools.partialmethod(cls._run_test, test_index)
            setattr(cls, method_name, func)
        return cls

    return decorate


@inject_random_testcases(n=10000)
class TestRandomValid(unittest.TestCase):
    """Tesst random valid TOML documents.

    The actual test cases are injected by the decorator."""

    def _check_result(self, value, gold_value):
        if isinstance(gold_value, list):
            self.assertIs(type(value), list)
            self.assertEqual(len(value), len(gold_value))
            for (elem, gold_elem) in zip(value, gold_value):
                self._check_result(elem, gold_elem)
        elif isinstance(gold_value, dict):
            self.assertIs(type(value), dict)
            self.assertEqual(set(value.keys()), set(gold_value.keys()))
            for k in gold_value:
                self._check_result(value[k], gold_value[k])
        else:
            self.assertIs(type(value), type(gold_value))
            if isinstance(gold_value, float) and math.isnan(gold_value):
                self.assertTrue(math.isnan(value))
            else:
                self.assertEqual(value, gold_value)
                if isinstance(gold_value, float):
                    value_sign = math.copysign(1, value)
                    gold_sign = math.copysign(1, gold_value)
                    self.assertEqual(value_sign, gold_sign)

    def _run_test(self, test_index):
        rng = random.Random(test_index)
        gen = gen_random_toml.TomlGenerator(rng)
        (toml_doc, gold_value) = gen.gen_toml()

        # Test loading TOML from string.
        v = tomllib.loads(toml_doc)
        self._check_result(v, gold_value)

        # Test loading TOML from file.
        with io.BytesIO(toml_doc.encode("utf-8")) as f:
            v = tomllib.load(f)
        self._check_result(v, gold_value)


if __name__ == "__main__":
    unittest.main()

