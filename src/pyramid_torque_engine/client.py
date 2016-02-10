# -*- coding: utf-8 -*-

"""Provides `nTorque <http://ntorque.com>`_ task queue clients."""

__all__ = [
    'DEFAULTS',
    'HookDispatcher',
    'WebTestDispatcher',
    'WorkEngineClient',
    'get_torque_api',
    'includeme',
]

import logging
logger = logging.getLogger(__name__)

import json
import os
import threading
import urlparse

from collections import namedtuple
from os.path import join as join_path

from pyramid.settings import asbool

from ntorque import client
from ntorque import model as ntorque_model
from ntorque.model import constants as nc
from ntorque.tests.ftests import test_client

from . import constants as c
from . import render
from . import util

env = os.environ
DEFAULTS = {
    'engine.api_key': util.get_var(env, c.ENGINE_API_KEY_NAMES),
    'engine.url': util.get_var(env, c.ENGINE_URL_NAMES, '/engine'),
    'torque.api_key': env.get(c.TORQUE_API_KEY, None),
    'torque.url': env.get(c.TORQUE_URL, '/ntorque'),
    'webhooks.api_key': util.get_var(env, c.WEBHOOKS_API_KEY_NAMES),
    'webhooks.url': util.get_var(env, c.WEBHOOKS_URL_NAMES, '/hooks'),
}

def client_factory(client_cls, dispatcher, settings):
    """Shared logic to instantiate a configured torque client utility."""

    torque_url = settings.get('torque.url')
    torque_api_key = settings.get('torque.api_key')
    return client_cls(dispatcher, torque_url, torque_api_key)


class WebTestDispatcher(client.DirectDispatcher):
    """A dispatcher that skips nTorque and just makes the request directly
      using a ``ntorque.tests.ftests.test_client.WestTestPoster``.
    """

    def __init__(self, webtest_poster, **kwargs):
        self.webtest_poster = webtest_poster
        self.parse_qsl = kwargs.get('parse_qsl', urlparse.parse_qsl)
        self.header_prefix = kwargs.get('header_prefix', nc.PROXY_HEADER_PREFIX)
        self.default_method = kwargs.get('default_method', nc.DEFAULT_METHOD)

    def __call__(self, url, post_data, request_headers):
        """Extract the relevant parts of the request data and use it to make
          a request directly to the destination url.
        """

        # Parse `url` and `method` out of the query params.
        params = dict(self.parse_qsl(url.split('?')[1]))
        url = params['url']
        method = params.get('method', 'POST')

        # Get the relevant headers.
        headers = {'Content-Type': request_headers['Content-Type']}
        for key, value in request_headers.items():
            if key.lower().startswith(self.header_prefix.lower()):
                k = key[len(self.header_prefix):]
                headers[k] = value

        # Make and handle the response.
        # Make and handle the response.
        r = self.make_request(url, post_data, headers, method=method)
        return self.handle(r)


    def make_request(self, *args, **kwargs):
        mapping = {}
        patched_args = (mapping,) + args
        t = threading.Thread(target=self._make_request, args=patched_args,
                kwargs=kwargs)
        t.start()
        t.join()
        return mapping['r']

    def _make_request(self, mapping, *args, **kwargs):
        mapping['r'] = self.webtest_poster(*args, **kwargs)


class HookDispatcher(object):
    """Instantiate and authenticate a generic torque client and use it to
      dispatch web hooks tasks.
    """

    def __init__(self, request, **kwargs):
        """Compose and instantiate client."""

        # Compose.
        self.request = request
        self.join_path = kwargs.get('join_path', join_path)
        client_cls = kwargs.get('client_cls', client.HybridTorqueClient)
        dispatcher = kwargs.get('dispatcher', client.AfterCommitDispatcher())
        settings = request.registry.settings
        self.client = client_factory(client_cls, dispatcher, settings)

    def __call__(self, path, data=None, headers=None, timeout=None):
        """Use the request to instantiate a client and dispatch a request."""

        # Unpack.
        request = self.request
        settings = request.registry.settings
        webhooks_url = settings.get('webhooks.url')
        webhooks_api_key = settings.get('webhooks.api_key')

        # Authenticate.
        if headers is None:
            headers = {}
        if webhooks_api_key:
            for item in c.WEBHOOKS_API_KEY_NAMES:
                key = 'NTORQUE-PASSTHROUGH-{0}'.format(item)
                headers[key] = webhooks_api_key

        # JSONify.
        if not headers.has_key('Content-Type'):
            headers['Content-Type'] = 'application/json; utf-8'
            if data is not None and not isinstance(data, basestring):
                data = render.json_dumps(request, data)

        # Dispatch.
        url = self.join_path(webhooks_url, path)
        status, response_data, response_headers = self.client(url, data=data,
                headers=headers, timeout=timeout)

        # Return.
        headers_dict = dict(response_headers.items()) if response_headers else {}
        return {
            'data': data,
            'path': path,
            'response': response_data,
            'response_headers': headers_dict,
            'status': status,
            'url': url,
        }

class WorkEngineClient(object):
    """Instantiate and authenticate a generic torque client and use it to
      dispatch work engine updates.
    """

    def __init__(self, request, **kwargs):
        """Compose and instantiate client."""

        # Compose.
        self.request = request
        self.join_path = kwargs.get('join_path', join_path)
        self.unpack = kwargs.get('unpack', util.get_unpacked_object_id)
        client_cls = kwargs.get('client_cls', client.HybridTorqueClient)
        dispatcher = kwargs.get('dispatcher', client.AfterCommitDispatcher())
        settings = request.registry.settings
        self.client = client_factory(client_cls, dispatcher, settings)

    def _get_traversal_path(self, route, context):
        """Get the traversal path to context, prefixed with the route.

          E.g.: the path to <Job id=1234> on the events route is
          `events/jobs/1234`.
        """

        # Get the request path from the `context`, e.g.: a `Job` instance
        # with id `1234` will result in a path of ``jobs/1234``. If there
        # is no context the path will be empty.
        parts = self.unpack(context) if context else []

        # Prepend the route part.
        parts = [route] + list(parts)

        # Lose any ``None``s.
        parts = (str(item) for item in parts if item is not None)

        # Return as a `/` joined string.
        return self.join_path(*parts)

    def dispatch(self, path, data=None, headers=None, timeout=None):
        """Use the request to instantiate a client and dispatch a request."""

        # Unpack.
        request = self.request
        settings = request.registry.settings
        engine_url = settings.get('engine.url')
        engine_api_key = settings.get('engine.api_key')

        # Authenticate.
        if headers is None:
            headers = {}
        if engine_api_key:
            for item in c.ENGINE_API_KEY_NAMES:
                key = 'NTORQUE-PASSTHROUGH-{0}'.format(item)
                headers[key] = engine_api_key

        # JSONify.
        if not headers.has_key('Content-Type'):
            headers['Content-Type'] = 'application/json; utf-8'
            if data is not None and not isinstance(data, basestring):
                data = render.json_dumps(request, data)

        # Dispatch.
        url = self.join_path(engine_url, path)
        status, response_data, response_headers = self.client(url, data=data,
                headers=headers, timeout=timeout)

        # Return.
        headers_dict = dict(response_headers.items()) if response_headers else {}
        return {
            'data': data,
            'path': path,
            'response': response_data,
            'response_headers': headers_dict,
            'status': status,
            'url': url,
        }

    def changed(self, context, event, state=None):
        """Tell the work engine that a ``context`` changed state."""

        # Get the path to the context on the events route.
        path = self._get_traversal_path('events', context)

        # Either use the state passed in or look it up on the context.
        if state is None:
            state = context.work_status.value

        # Build the post data.
        data = {
            'state': state,
        }
        if event:
            data['event_id'] = event.id

        logger.info((
            'torque.engine.changed',
            'context: ', context.class_slug, context.id,
            'new state: ', state,
        ))

        # Dispatch to the engine.
        return self.dispatch(path, data=data)

    def happened(self, context, action, event=None, **kwargs):
        """Tell the work engine that an action happened to a ``context``."""

        # Get the path to the context on the events route.
        path = self._get_traversal_path('events', context)

        # Build the post data.
        data = {
            'action': action,
        }
        if event:
            data['event_id'] = event.id

        logger.info((
            'torque.engine.happened',
            'context: ', context.class_slug, context.id,
            'action: ', action,
        ))

        # Dispatch to the engine.
        return self.dispatch(path, data=data)

    def result(self, context, operation, result, event=None, event_id=None, **kwargs):
        """Tell the work engine that an ``operation`` had the specified ``result``."""

        # Get the path to the context on the results route.
        path = self._get_traversal_path('results', context)

        # Build the post data.
        data = {
            'operation': operation,
            'result': result,
        }
        if event:
            data['event_id'] = event.id
        elif event_id:
            data['event_id'] = event_id
        else:
            raise Exception('You either need an event or an event_id.')

        logger.info((
            'torque.engine.result',
            'context: ', context.class_slug, context.id,
            'operation: ', operation,
            'result', result,
        ))

        # Dispatch to the engine.
        return self.dispatch(path, data=data)

def get_torque_api(request):
    """Provide a ``request.torque`` api, where the dispatchers used depend
      on whether we're ftesting or not.
    """

    # Are we ftesting and do we explicitly want to enable dispatch anyway?
    is_testing = request.environ.get('paste.testing', False)
    if is_testing:
        settings = request.registry.settings
        key = 'torque.enable_ftesting_dispatch'
        should_enable = asbool(settings.get(key, False))
        if should_enable:
            poster = test_client.WebTestPoster(settings['webtest_app'])
            default = WebTestDispatcher(poster)
            immediate = WebTestDispatcher(poster)
        else:
            default = client.NoopDispatcher()
            immediate = client.NoopDispatcher()

        client_cls=client.HTTPTorqueClient
    else:
        default = client.AfterCommitDispatcher()
        immediate = client.DirectDispatcher()
        client_cls=client.HybridTorqueClient

    # Provide the api.
    api = {
        'dispatch': HookDispatcher(request, dispatcher=default,
                client_cls=client_cls),
        'dispatch_now': HookDispatcher(request, dispatcher=immediate,
                client_cls=client_cls),
        'engine': WorkEngineClient(request, dispatcher=default,
                client_cls=client_cls),
    }
    keys, values = zip(*api.items())
    return namedtuple('Torque', keys)(*values)

def includeme(config, **kwargs):
    """Apply default settings and register the torque application id."""

    # Compose.
    lookup = kwargs.get('lookup', ntorque_model.LookupApplication())

    # Apply the default settings.
    settings = config.get_settings()
    for key, value in DEFAULTS.items():
        settings.setdefault(key, value)
    config.add_request_method(get_torque_api, 'torque', reify=True)

    # Register the api authenticated torque `application.id`.
    api_key = settings.get(c.TORQUE_API_KEY, None)
    if api_key:
        app = lookup(api_key)
        if app:
            settings.setdefault('torque.api_authenticated_app_id', app.id)
