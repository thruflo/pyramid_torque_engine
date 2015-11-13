# -*- coding: utf-8 -*-

"""Test the ``request.torque`` client api."""

import logging
logger = logging.getLogger(__name__)

import json
import unittest

from mock import MagicMock as Mock

from ntorque import client as ntorque_client
from pyramid_torque_engine import client as engine_client

class TestConfiguration(unittest.TestCase):
    """Test the the ``pyramid_torque_engine.client.includeme`` function."""

    def test_default_settings(self):
        """Including `pyramid_torque_engine.client` should set up the
          default settings.
        """

        mock_config = Mock()
        mock_lookup = Mock()
        engine_client.includeme(mock_config, lookup=mock_lookup)
        settings = mock_config.get_settings.return_value
        for key, value in engine_client.DEFAULTS.items():
            settings.setdefault.assert_any_call(key, value)

    def test_provide_request_api(self):
        """Including `pyramid_torque_engine.client` reifies the torque api at
          `request.torque`.
        """

        mock_config = Mock()
        mock_lookup = Mock()
        engine_client.includeme(mock_config, lookup=mock_lookup)
        mock_config.add_request_method.assert_called_with(
                engine_client.get_torque_api, 'torque', reify=True)

    def test_api(self):
        """The ``request.torque`` api provides the right methods."""

        mock_request = Mock()
        api = engine_client.get_torque_api(mock_request)
        self.assertTrue(hasattr(api, 'dispatch'))
        self.assertTrue(hasattr(api, 'dispatch_now'))
        self.assertTrue(hasattr(api, 'engine'))

class TestHookDispatcher(unittest.TestCase):
    """Test the the ``pyramid_torque_engine.client.HookDispatcher``."""

    def setUp(self):
        self.mock_request = Mock()
        self.mock_request.registry.settings = engine_client.DEFAULTS
        self.mock_dispatcher = Mock()
        self.mock_dispatcher.return_value = u'DISPATCHED', {}, {}

    def makeOne(self, **kwargs):
        kwargs.setdefault('client_cls', ntorque_client.HTTPTorqueClient)
        kwargs.setdefault('dispatcher', self.mock_dispatcher)
        return engine_client.HookDispatcher(self.mock_request, **kwargs)

    def test_dispatch_hook(self):
        """Test dispatching a hook."""

        dispatcher = self.makeOne()
        return_value = dispatcher('some/hook')
        status = return_value['status']
        self.assertTrue(status == u'DISPATCHED')

class TestWorkEngineClient(unittest.TestCase):
    """Test the the ``pyramid_torque_engine.client.WorkflowEngineDispatcher``."""

    def setUp(self):
        self.mock_request = Mock()
        self.mock_request.registry.settings = engine_client.DEFAULTS
        self.mock_dispatcher = Mock()
        self.mock_dispatcher.return_value = u'DISPATCHED', {}, {}
        self.mock_join_path = Mock()
        self.mock_join_path.return_value = 'route/jobs/1234'
        self.mock_unpack = Mock()

    def makeOne(self, **kwargs):
        kwargs.setdefault('client_cls', ntorque_client.HTTPTorqueClient)
        kwargs.setdefault('dispatcher', self.mock_dispatcher)
        kwargs.setdefault('join_path', self.mock_join_path)
        kwargs.setdefault('unpack', self.mock_unpack)
        return engine_client.WorkEngineClient(self.mock_request, **kwargs)

    def test_state_changed(self):
        """Test dispatching a state changed event."""

        # Pretend we're updating jobs#1234.
        mock_context = Mock()
        mock_context.work_status.value = u'state:CREATED'
        mock_event = Mock()
        mock_event.id = 1234
        self.mock_unpack.return_value = ('jobs', 1234)

        # Dispatch an update.
        client = self.makeOne()
        return_value = client.changed(mock_context, mock_event)

        # The path is constructed from the context.
        self.mock_unpack.assert_called_with(mock_context)

        # The return value includes the status of the dispatch.
        status = return_value['status']
        self.assertTrue(status == u'DISPATCHED')

        # And the dispatcher was called with the url and data.
        torque_url = self.mock_request.registry.settings['torque.url']
        call_args = self.mock_dispatcher.call_args[0]
        url = call_args[0]
        data = json.loads(call_args[1])
        self.assertTrue(url.startswith(torque_url))
        self.assertTrue(data['event_id'] == 1234)
        self.assertTrue(data['state'] == u'state:CREATED')

    def test_action_happened(self):
        """Test dispatching a work engine action happened notification."""

        # Pretend we're updating jobs#1234.
        mock_context = Mock()
        mock_context.work_status.value = u'state:CREATED'
        self.mock_unpack.return_value = ('jobs', 1234)

        # Dispatch an update.
        client = self.makeOne()
        return_value = client.happened(mock_context, 'action:SPAMMED')

        # The return value includes the status of the dispatch.
        status = return_value['status']
        self.assertTrue(status == u'DISPATCHED')

        # And the dispatcher was called with the data.
        data = json.loads(self.mock_dispatcher.call_args[0][1])
        self.assertTrue(data['action'].endswith('SPAMMED'))

    def test_operation_result(self):
        """Test dispatching a work engine operation result."""

        # Pretend we're updating jobs#1234.
        mock_context = Mock()
        mock_context.work_status.value = u'state:CREATED'
        self.mock_unpack.return_value = ('jobs', 1234)

        # Dispatch an update.
        client = self.makeOne()
        return_value = client.result(mock_context, 'o:VERB', 'r:NOUN', event_id=1)

        # The return value includes the status of the dispatch.
        status = return_value['status']
        self.assertTrue(status == u'DISPATCHED')

        # And the dispatcher was called with the data.
        data = json.loads(self.mock_dispatcher.call_args[0][1])
        self.assertTrue(data['operation'].endswith('VERB'))
        self.assertTrue(data['result'].endswith('NOUN'))
