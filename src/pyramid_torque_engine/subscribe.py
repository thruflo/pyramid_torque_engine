# -*- coding: utf-8 -*-

"""Including this module sets up a state change event subscription system
  that dispatches incoming http requests to registered subscribers for a
  given context and state.

  You can then register event handlers for a given resource and request
  param value:

      # Subscribe to a state change.
      config.add_engine_subscriber(IFoo, 'state:DECLINED', notify_user)

      # Subscribe to an action happening.
      config.add_engine_subscriber(IFoo, 'action:DECLINE', notify_user)

  And dispatch to them using `torque.engine.changed(context, event)`.
  Plus it provides `request.activity_event` to lookup an activity event
  identified by the `event_id` request param.
"""

__all__ = [
    'AddEngineSubscriber',
    'AsterixSubscriber',
    'GetActivityEvent',
    'ParamAwareSubscriber',
    'StateChangeHandler',
    'operation_config',
]

import logging
logger = logging.getLogger(__name__)

import zope.interface as zi
import pyramid_basemodel as bm

from . import constants
from . import repo

class StateChangeHandler(object):
    """Dispatch state changed events to registered subscribers."""

    def __init__(self, **kwargs):
        self.providedBy = kwargs.get('providedBy', zi.providedBy)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, request):
        """Log and call."""

        # Unpack.
        context = request.context
        event = request.activity_event
        registry = request.registry
        subscriptions = registry.adapters.subscriptions

        # Dispatch.
        results = []
        for handler in subscriptions([self.providedBy(context)], None):
            # XXX it seems that subscription handlers can cause the context to be
            # detatched, perhaps just in tests. So just sanity check / make sure
            # the instance is in the session before passing to each handler.
            # Where the instance is already in the session, this is a noop anyway.
            self.session.add(context)
            # Note that we pass through the args as a single tuple
            # as the Pyramid events machinery expects a single value.
            combined_args = (request, context, event)
            results.append(handler(combined_args))
        return {'handlers': [item for item in results if item is not None]}

class ParamAwareSubscriber(object):
    """Wrap an activity event handler with a callable that only calls the
      handler if a named request param matches.
    """

    def __init__(self, param, value, handler):
        self.param = param
        self.value = value
        self.handler = handler

    def __call__(self, combined_args):
        """Validate that the request param matches and, if so, call the
          handler function.
        """

        # Unpack the combined args into `request, *args`.
        request = combined_args[0]
        args = combined_args[1:]

        # Validate the state param matches.
        param_value = request.json.get(self.param, None)
        if param_value != self.value:
            return None

        # If so, call the handler.
        return self.handler(request, *args)

class AsterixSubscriber(object):
    """Alternative to the param aware subscriber for handlers that should
      be registered for everything using, e.g.:

          on(IFoo, '*', op.PERFORM_FOO, handler)

    """

    def __init__(self, handler):
        self.handler = handler

    def __call__(self, combined_args):
        """Call the handler function."""

        request = combined_args[0]
        args = combined_args[1:]
        return self.handler(request, *args)

class AddEngineSubscriber(object):
    """Register a ``handler`` function for one or more namespaced events."""

    def __init__(self, **kwargs):
        self.asterix_cls = kwargs.get('asterix_cls', AsterixSubscriber)
        self.wrapper_cls = kwargs.get('wrapper_cls', ParamAwareSubscriber)

    def __call__(self, config, context, events, operation, handler, **kw):
        """Subscribe a handler for each event."""

        # Extend the handler's args with the operation.
        def op_handler(*args):
            expanded_args = args + tuple([operation])
            return handler(*expanded_args)

        # Make sure we have a list.
        if not hasattr(events, '__iter__'):
            events = (events,)

        # For each event, add a subscriber.
        for value in events:
            if value == constants.ASTERIX:
                # Subscribe to everything.
                subscriber = self.asterix_cls(op_handler)
            else:
                # Split e.g.: `'state:FOO'` into `('state', 'FOO')`.
                param_name = value.split(':')[0]
                # Add a request param aware subscriber.
                subscriber = self.wrapper_cls(param_name, value, op_handler)
            config.add_subscriber(subscriber, context)

        # Followed up by a discriminator to prevent unintentional duplicated
        # event subscription -- note that we have already registered the
        # subscribers and the function we pass to config.action is a noop
        # because ``config.add_subscriber`` itself hooks into the config commit
        # machinery and if we delay calling it until later, our subscriptions
        # are not actually registered.
        noop = lambda: None
        key = 'engine.subscribe'
        discriminator = [key, context, operation, handler]
        discriminator.extend(events)
        discriminator.extend(kw.items())
        # Make it introspectable.
        intr = config.introspectable(category_name='engine subscriber',
                                     discriminator=tuple(discriminator),
                                     title='An engine subscriber',
                                     type_name=None)
        intr['value'] = (context, events, operation)

        config.action(tuple(discriminator), noop, introspectables=(intr,))

class GetActivityEvent(object):
    """Request method to lookup ActivityEvent instance from the value in the
      ``event_id`` request param, falling back on the instance related to
      the context's work status.
    """

    def __init__(self, **kwargs):
        self.lookup = kwargs.get('lookup', repo.LookupActivityEvent())

    def __call__(self, request):
        candidate = request.json.get('event_id', None)
        try:
            event_id = int(candidate)
        except (TypeError, ValueError):
            pass
        else: # Lookup.
            event = self.lookup(event_id)
            if event:
                return event
        # Fallback.
        if request.context:
            status = getattr(request.context, 'work_status', None)
            if status:
                return status.event

class IncludeMe(object):
    """Set up the state change event subscription system and provide an
      ``add_engine_subscriber`` directive.
    """

    def __init__(self, **kwargs):
        self.handler = kwargs.get('handler', StateChangeHandler())
        self.add_subscriber = kwargs.get('add_subscriber', AddEngineSubscriber())
        self.get_activity_event = kwargs.get('get_activity_event',
                GetActivityEvent().__call__)

    def __call__(self, config):
        """Handle `/events` requests and provide subscription directive."""

        # Unpack.
        handler = self.handler
        add_subscriber = self.add_subscriber
        get_activity_event = self.get_activity_event

        # Handle `POST {state, event_id} /events/:tablename/:id`.
        config.add_route('events', '/events/*traverse')
        config.add_view(handler, renderer='json', request_method='POST',
                route_name='events')

        # Provide `add_state_change_subscriber` directive.
        config.add_directive('add_engine_subscriber', add_subscriber)

        # Provide `request.activity_event`.
        config.add_request_method(get_activity_event, 'activity_event', reify=True)

includeme = IncludeMe().__call__
