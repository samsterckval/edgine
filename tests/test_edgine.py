#!/usr/bin/env python

"""Tests for `edgine` package."""


import unittest
from multiprocessing import Queue, Event
# import multiprocessing
from edgine.src.config.config import Config
from edgine.src.config.config_server import ConfigServer
import time
import os


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
        """Test is config returns false if we try to update from a None queue"""
        config = Config()
        ret = config.update()
        assert(ret is False)

    def test_002_config_write_exception(self):
        """Test is child config refuses write"""
        config = Config()
        self.assertRaises(PermissionError, config.__setattr__, "test", "test")

    def test_003_config_update_good(self):
        """Test is child config updates from queue"""
        q = Queue()
        fake_log_q = Queue()
        config = Config(in_q=q, logging_q=fake_log_q)
        q.put_nowait(["test_name", "test_value"])
        time.sleep(0.1)
        config.update()
        time.sleep(0.1)
        assert(config.test_name == "test_value")

    def test_004_configserver(self):
        """Test if children get updated from config master"""
        fake_stop = Event()
        fake_log_q = Queue()
        cs = ConfigServer(stop_event=fake_stop, name="test-cs", logging_q=fake_log_q)
        config = cs.get_config_copy()
        cs.config.test_004 = "configserver"
        cs.start()
        time.sleep(1.1)
        fake_stop.set()
        cs.join()
        config.update()
        assert(config.test_004 == "configserver")

    def test_005_saveconfig(self):
        """Test if a new config can be loaded from a file"""
        fake_stop = Event()
        fake_log_q = Queue()
        cs = ConfigServer(stop_event=fake_stop, name="test-cs", config_file="config.json", logging_q=fake_log_q)
        cs.config.test_005 = "saveconfig"
        cs.save_config()
        cs2 = ConfigServer(stop_event=fake_stop, name="test-cs2", config_file="config.json", logging_q=fake_log_q)
        assert(cs2.config.test_005 == cs.config.test_005)
