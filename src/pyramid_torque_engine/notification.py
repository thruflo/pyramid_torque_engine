# -*- coding: utf-8 -*-

"""Provides sync for podio."""

__all__ = [
    'add_notification',
    'AddNotification'
]

from pyramid_torque_engine import unpack
from pyramid_torque_engine import operations as ops

from pyramid_torque_engine import repo

# XXX specs big object with all possible actions and look up by action
# 'view': 'dotted.path' -> dotted path function adapter renders specs
# due date has to be aware of when the weekly thingy goes out set to that


class AddNotification(object):
    """Standard boilerplate to add a notification."""

    def __init__(self, iface, role, dispatch_mapping, delay=None):
        """By default an operation called `o.DO_FOO` will dispatch to
          `/hooks/do_foo`.
        """

        self.dispatch_mapping = dispatch_mapping
        self.notification_factory = repo.NotificationFactory
        self.role = role
        self.delay = delay
        self.iface = iface

    def __call__(self, request, context, event, op, **kwargs):
        """Dispatch a task to the hook by path, with a standard set of data
          optionally augemented with extra data extracted by the ``pliers``.
        """


        # Unpack.
        dispatch_mapping = self.dispatch_mapping
        notification_factory = self.notification_factory(request)
        delay = self.delay
        iface = self.iface
        role = self.role

        # get relevant information
        interested_users_func = get_roles_mapping(request, iface)
        interested_users = interested_users_func(request, context)
        for user in interested_users[role]:
            _ = notification_factory(event, user, dispatch_mapping, delay)


def add_notification(config,
                     iface,
                     role,
                     state_or_action_changes,
                     dispatch_mapping,
                     delay=None):

    # Unpack.
    _, o, _, s = unpack.constants()
    _, on, _ = unpack.directives(config)

    o.register(
        'CREATE_NOTIFICATION',
    )

    create_notification_in_db = AddNotification(iface, role, dispatch_mapping, delay)
    on(iface, state_or_action_changes, o.CREATE_NOTIFICATION, create_notification_in_db)


def add_roles_mapping(config, iface, mapping):
    """Adds a roles mapping to the resource."""

    # Unpack.
    registry = config.registry

    # Noop if we've done this already.
    roles_mapping = registry.roles_mapping
    if iface in roles_mapping:
        return

    # Register the role mapping.
    roles_mapping[iface] = mapping


def get_roles_mapping(request, iface):
    """Gets the role mapping for the resource."""

    # Unpack.
    registry = request.registry
    roles_mapping = registry.roles_mapping

    return roles_mapping.get(iface, None)

def get_operator_user(request, registry=None):
    """We have a special user in our db representing the operator user. Here
      we look them up by username, constructed from the client id.
      XXXXXX at the moment Andre is the operator user!!!1
    """

    if registry == None:
        # Unpack.
        settings = request.registry.settings
    else:
        settings = registry.settings

    # Get the user.
    from pyramid_simpleauth.model import get_existing_user
    try:
        username = u'aprado'
    except KeyError:
        username = None

    return get_existing_user(username=username)


class IncludeMe(object):
    """Set up the state change event subscription system and provide an
      ``add_engine_subscriber`` directive.
    """

    def __init__(self, **kwargs):
        self.add_notification = kwargs.get('add_notification', add_notification)
        self.add_roles_mapping = kwargs.get('add_roles_mapping', add_roles_mapping)
        self.get_roles_mapping = kwargs.get('get_roles_mapping', get_roles_mapping)

    def __call__(self, config):
        """Handle `/events` requests and provide subscription directive."""

        config.add_directive('add_notification', self.add_notification)
        config.registry.roles_mapping = {}
        config.add_directive('add_roles_mapping', self.add_roles_mapping)
        config.add_directive('get_roles_mapping', self.get_roles_mapping)
        config.add_request_method(get_operator_user, 'operator_user', reify=True)

includeme = IncludeMe().__call__
