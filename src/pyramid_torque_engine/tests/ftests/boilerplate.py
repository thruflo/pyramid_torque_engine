# -*- coding: utf-8 -*-

"""Provide a boilerplate factory to make the WSGI app to be tested."""

__all__ = [
    'TestAppFactory',
    'make_wsgi_app',
]

import unittest

try:
    import webtest
except ImportError:  # pragma: no cover
    pass

import pyramid_basemodel as bm

from cornice.tests import support
from sqlalchemy import engine

from pyramid import config as pyramid_config
from pyramid import registry
from pyramid import testing

from pyramid_torque_engine import traverse

from . import settings

def make_wsgi_app(root_factory, includeme, registry=None, **settings):
    """Create and return a WSGI application."""

    configurator_cls = pyramid_config.Configurator

    # Initialise a ``Configurator`` and apply the package configuration.
    if registry:
        config = configurator_cls(registry=registry)
        config.setup_registry(settings=settings, root_factory=root_factory)
    else:
        config = configurator_cls(settings=settings, root_factory=root_factory)

    # Include the app config.
    includeme(config)

    # Close any db connection for this thread.
    bm.Session.remove()

    # Return a WSGI app.
    return config.make_wsgi_app()

class TestAppFactory(object):
    """Callable utility that returns a testable WSGI app and manages db state."""

    def __init__(self, app_factory, should_use_tx=True, **kwargs):
        self.app_factory = app_factory
        self.should_use_tx = should_use_tx
        self.base = kwargs.get('base', bm.Base)
        self.catch_errors = kwargs.get('catch_errors', support.CatchErrors)
        self.global_config = kwargs.get('global_config', None)
        self.json_method = kwargs.get('get_json', webtest.utils.json_method)
        self.session = kwargs.get('session', bm.Session)
        self.test_app = kwargs.get('test_app', webtest.TestApp)
        self.test_settings = kwargs.get('test_settings', settings.TEST_SETTINGS)
        self.has_created = False
        self.engine = engine.engine_from_config(self.test_settings,
                prefix='sqlalchemy.')
        self.conn = self.engine.connect()

    def begin(self):
        if self.should_use_tx:
            self.tx = self.conn.begin()
        self.session.configure(bind=self.conn)
        reg = registry.Registry(name='ftesting')
        self.configurator = testing.setUp(registry=reg)

    def rollback(self):
        self.session.remove()
        if self.should_use_tx:
            self.tx.rollback()
        testing.tearDown()

    def __call__(self, **kwargs):
        """Create the WSGI app and wrap it with a patched webtest.TestApp."""

        # Patch TestApp.
        self.test_app.get_json = self.json_method('GET')
        self.test_app.put_json = self.json_method('PUT')
        self.test_app.delete_json = self.json_method('DELETE')

        # Instantiate.
        self.settings = self.test_settings.copy()
        self.settings.update(kwargs)
        factory = self.app_factory()
        reg = self.configurator.registry
        app = factory(self.global_config, registry=reg, **self.settings)

        # Wrap.
        test_app = self.test_app(self.catch_errors(app))

        # Patch into the registry.
        self.configurator.registry.settings['webtest_app'] = test_app

        # Return the wrapped WSGI app.
        return test_app

class AppTestCase(unittest.TestCase):
    """Unit test case that sets up a work engine WSGI app configured
      using ``cls.includeme(config)``.
    """

    @classmethod
    def includeme(config):
        raise NotImplementedError

    @classmethod
    def setup_class(cls):
        app = make_wsgi_app(traverse.EngineRoot, cls.includeme)
        cls.factory = TestAppFactory(app)

    def setUp(self):
        self.factory.begin()

    def tearDown(self):
        self.factory.rollback()
