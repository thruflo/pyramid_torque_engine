# -*- coding: utf-8 -*-

"""Test `can perform action` rules."""

import logging
logger = logging.getLogger(__name__)

from . import boilerplate
from . import model

class TestActions(boilerplate.AppTestCase):
    """..."""

    @classmethod
    def includeme(cls, config):
        """Work engine configuration for this test."""

        # ...

    def test_foo(self):
        self.assertTrue(False)
