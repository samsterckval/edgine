#!/usr/bin/env python

"""Tests for `edgine` package."""


import unittest

from edgine import edgine


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
        print(output)
        print(self.hello_message)
        assert(output == self.hello_message)
