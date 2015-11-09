# -*- coding: utf-8 -*-

"""Provides sync for podio."""

__all__ = [
    'add_notification',
    'AddNotification'
]

from pyramid_torque_engine import unpack
from pyramid_torque_engine import operations as ops

from pyramid_torque_engine import repo

from pyramid import path as pyramid_path

# XXX specs big object with all possible actions and look up by action
# 'view': 'dotted.path' -> dotted path function adapter renders specs
# due date has to be aware of when the weekly thingy goes out set to that


class AddNotification(object):
    """Standard boilerplate to add a notification."""

    def __init__(self, role_function=None, dispatch_mapping=None, delay=None):
        """By default an operation called `o.DO_FOO` will dispatch to
          `/hooks/do_foo`.
        """

        self.role_function = role_function
        self.dispatch_mapping = dispatch_mapping
        self.notification_factory = repo.NotificationFactory
        self.delay = delay

    def __call__(self, request, context, event, op, **kwargs):
        """Dispatch a task to the hook by path, with a standard set of data
          optionally augemented with extra data extracted by the ``pliers``.
        """

        # Unpack.
        role_function = self.role_function
        dispatch_mapping = self.dispatch_mapping
        notification_factory = self.notification_factory(request)
        delay = self.delay

        # get relevant information
        # XXX should be role_list = config.get_mapping(context)
        interested_users = role_function(context)
        for user in interested_users['users']:
            notification = notification_factory(event, user, dispatch_mapping, delay)

def add_notification(config,
                     iface,
                     state_or_action_changes,
                     role_function,
                     dispatch_mapping,
                     delay=None):

    # Unpack.
    _, o, _, s = unpack.constants()
    _, on, _ = unpack.directives(config)

    o.register(
        'CREATE_NOTIFICATION',
    )

    dispatch = AddNotification(role_function=role_function, dispatch_mapping=dispatch_mapping, delay=delay)
    on(iface, state_or_action_changes, o.CREATE_NOTIFICATION, dispatch)


class IncludeMe(object):
    """Set up the state change event subscription system and provide an
      ``add_engine_subscriber`` directive.
    """

    def __init__(self, **kwargs):
        self.add_notification = kwargs.get('add_notification', add_notification)

    def __call__(self, config):
        """Handle `/events` requests and provide subscription directive."""

        config.add_directive('add_notification', add_notification)

includeme = IncludeMe().__call__
