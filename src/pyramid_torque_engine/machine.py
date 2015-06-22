# -*- coding: utf-8 -*-

"""Provides a ``includeme()`` pyramid configuration entry point that only
  includes the minimum necessary to register the state machine rules.

  This is useful for apps that want to use the ``request.state_machine``
  api without exposing all the views and whatnot.
"""

from . import action

noop = lambda *a, **kw: None

def includeme(config):
    """Provide the ``allow(...)`` rules directive and mock the ``on()``
      and ``after()`` directives.
    """

    config.include('pyramid_torque_engine.action')
    config.add_directive('add_engine_resource', noop)
    config.add_directive('add_engine_subscriber', noop)
    config.add_directive('add_engine_transition', noop)
