# -*- coding: utf-8 -*-

"""Boilerplate functions that dry up the code needed to unpack the directives
  and constants used in resource configuration.
"""

__all__ = [
    'constants',
    'directives'
]

from . import constants as constants_module

noop = lambda *a, **kw: None

def directives(config):
    action = config.add_engine_action
    subscriber = getattr(config, 'add_engine_subscriber', noop)
    transition = getattr(config, 'add_engine_transition', noop)
    return action, subscriber, transition

def constants():
    c = constants_module
    return c.ACTIONS, c.OPERATIONS, c.RESULTS, c.STATES
