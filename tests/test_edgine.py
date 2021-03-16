#!/usr/bin/env python

"""Tests for `edgine` package."""


import unittest
from multiprocessing import Queue
from edgine.src.config import Config
import time


class TestEdgine(unittest.TestCase):
    """Tests for `edgine` package."""

    def setUp(self):
        """Set up test fixtures, if any."""
        self.hello_message = "Get Edgy!"

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_000_something(self):
        """Test something."""

    def test_001_config_update_bad(self):
        config = Config()
        ret = config.update()
        assert(ret is False)

    def test_002_config_write_exception(self):
        config = Config()
        self.assertRaises(PermissionError, config.__setattr__, "test", "test")

    def test_003_config_update_good(self):
        q = Queue()
        config = Config(in_q=q)
        q.put_nowait(["test_name", "test_value"])
        config.update()
        time.sleep(0.001)
        assert(config.test_name == "test_value")
