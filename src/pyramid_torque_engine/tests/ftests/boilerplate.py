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

import transaction

from cornice.tests import support
from sqlalchemy import engine

from pyramid import config as pyramid_config
from pyramid import registry
from pyramid import testing

from pyramid_torque_engine import action
from pyramid_torque_engine import client
from pyramid_torque_engine import traverse

from pyramid_torque_engine import repo
from pyramid_simpleauth import model as simpleauth_model

from . import settings

# We monkey patch user just because..
class Email(object):
    address = 'testing@test.com'

simpleauth_model.User.best_email = Email()

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

# Authentication related
def createUser(**kwargs):
    name = kwargs.get('name', u'Dummy')
    password = kwargs.get('password', u'password')
    data = {
            'password': password,
            'username': name,
        }
    user = simpleauth_model.User(**data)
    bm.Session.add(user)
    bm.Session.flush()
    return user

def createEvent(context=None):
    """Stubs an event."""
    from pyramid_torque_engine.repo import ActivityEventFactory
    from mock import Mock

    with transaction.manager:
        bm.Session.add(context)
        event = ActivityEventFactory(Mock())(context, None)
        bm.Session.add(event)
        bm.Session.flush()
        event_id = event.id
    return event_id

class StubRequest(object):
    """Provide `request.registry` and `request.environ`."""

    def __init__(self, registry_):
        self.registry = registry_
        self.environ = {'paste.testing': True,}
        self.torque = client.get_torque_api(self)

    @property
    def state_changer(self):
        return action.StateChanger(self)

    def get_state_machine(self, *args, **kwargs):
        return action.get_state_machine(self, *args, **kwargs)

    def __repr__(self):
        return 'StubRequest {0} {1}'.format(self.registry, self.environ)

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
        test_app.registry = reg
        return test_app

class AppTestCase(unittest.TestCase):
    """Unit test case that sets up a work engine WSGI app configured
      using ``cls.includeme(config)``.
    """

    @classmethod
    def includeall(cls, config):
        """Setup the db and work engine and include the app config."""

        # Boilerplate.
        config.include('pyramid_basemodel')
        config.include('pyramid_tm')
        config.include('pyramid_torque_engine')

        # App specifics.
        cls.includeme(config)

    @classmethod
    def includeme(cls, config):
        raise NotImplementedError

    @classmethod
    def setup_class(cls):
        class AppFactory(object):
            def __call__(self, global_config, **settings):
                return make_wsgi_app(traverse.EngineRoot, cls.includeall, **settings)
        cls.factory = TestAppFactory(AppFactory)

    def setUp(self):
        self.factory.begin()

    def tearDown(self):
        self.factory.rollback()

    def getRequest(self, app):
        """Return a stubbed request that has the configured registry and
          provides a minimal api.
        """

        return StubRequest(app.registry)
