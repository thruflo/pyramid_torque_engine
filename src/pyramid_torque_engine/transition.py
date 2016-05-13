# -*- coding: utf-8 -*-

"""Including this module sets up an operation-result handling system. You can
  then register actions to perform for a given context, operation and result:

      config.add_engine_transition(
          IFoo,          # context
          'o.VALIDATE',  # operation
          'r.OK',        # result
          'a.SET_VALID', # action
      )

  And dispatch to them using `torque.engine.result(context, 'o.VALIDATE', 'r.OK')`.
"""

__all__ = [
    'AddEngineTransition',
    'TransitionHandler',
]

import logging
logger = logging.getLogger(__name__)

from pyramid import exceptions
from pyramid.config import predicates

from . import util

class JSONPredicate(predicates.RequestParamPredicate):
    """Like the ``@view_config(..., request_params=...)`` but for
      top level ``request.json`` key value pairs.
    """

    def __call__(self, context, request):
        try:
            data = request.json
        except ValueError:
            return False
        for k, v in self.reqs:
            actual = data.get(k)
            if actual is None:
                return False
            if v is not None and actual != v:
                return False
        return True

class TransitionHandler(object):
    """Handle results by setting the ``work_state`` of the ``request.context``
      and dispatching a work engine update to notify about the change.
    """

    def __init__(self, action):
        self.action = action

    def __call__(self, request):
        """Use the ``request.perform_action`` method to perform the state change
          action and then return a dict with a list of the updates dispatched.
        """

        # Unpack.
        action = self.action
        context = request.context
        event = request.activity_event # XXX do we need / get this?
        state_changer = request.state_changer

        # Prepare
        dispatched = []

        # Perform.
        if state_changer.can_perform(context, action):
            _, __, dispatched = request.state_changer.perform(context, action, event)
        return {'dispatched': dispatched}

class AddEngineTransition(object):
    """Configuration directive that uses the Pyramid ``view_config``
      machinery to perform a registered ``action`` for a given ``context``,
      ``operation`` and ``result``.
    """

    def __init__(self, **kwargs):
        self.handler_cls = kwargs.get('handler_cls', TransitionHandler)
        self.get_interfaces = kwargs.get('get_interfaces', util.get_interfaces)
        self.request_params = kwargs.get('request_params', util.as_request_params)

    def __call__(self, config, context, operation, result, action):
        """Register a `results` handler for the given predicates."""

        # Prepare a function to call to validate that the action was
        # registered for this context.
        validate = lambda: self.validate(config.registry, context, action)

        # Register it for this context.
        key = 'engine.transition'
        discriminator = (key, context, operation, result)

        # Instantiate a handler that knows the action to perform.
        handler = self.handler_cls(action)

        # Build the match params.
        params = self.request_params(operation=operation, result=result)

        # Register the handler for the context and params.
        config.add_view(handler, context=context, renderer='json',
                request_method='POST', json_param=params,
                route_name='results')

        # Make it introspectable.
        intr = config.introspectable(category_name='engine transition',
                                     discriminator=discriminator,
                                     title='An engine transition',
                                     type_name=None)
        intr['value'] = (context, operation, result, action)

        config.action(discriminator, validate, introspectables=(intr,))

    def validate(self, registry, context, action):
        """Make sure that there's a registered ``action`` for the ``context``."""

        # Check the `registry.state_action_rules` to see whether this action
        # has been configured for this context.
        rules = registry.state_action_rules
        for key in self.get_interfaces(context):
            if rules.has_key(key):
                parent = rules[key]
                if parent.get(action, None):
                    return True

        # If not, raise a configuration error.
        msg = (action, u'not registered for context', context)
        raise exceptions.ConfigurationError(msg)


def noop_handler(request):
    """Catch all handler, checks if the request has a context, if it
      does, return a 204 else 404.
    """

    response = request.response
    if request.context:
        response.status_int = 204
        response.body = None
        del response.content_type
    else:
        response.status_int = 404
    return response


class IncludeMe(object):
    """Handle `/results...` and provide an ``add_engine_transition`` directive."""

    def __init__(self, **kwargs):
        self.add_transition = kwargs.get('add_transition', AddEngineTransition())

    def __call__(self, config):
        """Expose route and provide directive."""

        # Configure.
        config.add_route('results', '/results/*traverse')
        # Add a catch all view that responds to when a result cannot find
        # a subscriber. In this case 204 is returned instead of 404.
        config.add_view(noop_handler, renderer='json', request_method='POST',
                route_name='results')
        config.add_view_predicate('json_param', JSONPredicate)
        config.add_directive('add_engine_transition', self.add_transition)

includeme = IncludeMe().__call__
