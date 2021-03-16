#!/usr/bin/env python

"""Tests for `edgine` package."""


import unittest

from edgine import edgine
from edgine.src.config import Config


def helper_config_write_exception(config: Config):
    config.testing = "some test"


class TestEdgine(unittest.TestCase):
    """Tests for `edgine` package."""

    def setUp(self):
        """Set up test fixtures, if any."""
        self.hello_message = "Get Edgy!"

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_000_something(self):
        """Test something."""

    def test_001_hello_world(self):
        output = edgine.hello_world()
        assert(output == self.hello_message)

    def test_002_config_update_bad(self):
        config = Config()
        ret = config.update()
        assert(ret is False)

    def test_003_config_write_exception(self):
        config = Config()
        self.assertRaises(PermissionError, helper_config_write_exception, config)
