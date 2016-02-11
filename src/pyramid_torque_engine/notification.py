# -*- coding: utf-8 -*-

"""Provides sync for podio."""

__all__ = [
    'add_notification',
    'AddNotification'
]

import logging
logger = logging.getLogger(__name__)

from pyramid_torque_engine import unpack
from pyramid_torque_engine import operations as ops

from pyramid_torque_engine import repo
from pyramid import path

from pyramid_simpleauth.model import get_existing_user

import colander
import notification_table_executer
import datetime
import pyramid_basemodel as bm
import requests
import json
import os


def send_from_notification_dispatch(request, notification_dispatch_id):
    """Boilerplate to extract information from the notification
    dispatch and send an email.
    Please note that no verification if it should
    be sent is made prior to sending.
    """

    lookup = repo.LookupNotificationDispatch()
    dotted_name_resolver = path.DottedNameResolver()

    notification_dispatch = lookup(notification_dispatch_id)
    if not notification_dispatch:
        return False

    # Extract information from the notification dispatch.
    spec = notification_dispatch.single_spec
    send_to = notification_dispatch.address
    view = dotted_name_resolver.resolve(notification_dispatch.view)
    event = notification_dispatch.notification.event
    bcc = notification_dispatch.bcc
    context = event.parent
    channel = notification_dispatch.category

    # Get the template vars.
    tmpl_vars = view(request, context, send_to, event, event.action)

    # Set some defaults for the template vars.
    tmpl_vars.setdefault('context', context)
    tmpl_vars.setdefault('to', send_to)
    tmpl_vars.setdefault('from', repo.extract_us(request))
    tmpl_vars.setdefault('state_or_action', event.action)
    tmpl_vars.setdefault('event', event)
    tmpl_vars.setdefault('subject', '{0} {1}'.format(event.target, event.action))
    # Check if we should add bcc.
    if bcc:
        tmpl_vars.setdefault('bcc', bcc)

    if channel == 'email':
        request.render_email(
                tmpl_vars['from'],
                tmpl_vars['to'],
                tmpl_vars['subject'],
                spec, tmpl_vars, **tmpl_vars)
    elif channel == 'sms':
        pass
    else:
        raise Exception('Unknown channel to send the notification')

    # Set the sent info in our db.
    notification_dispatch.sent = datetime.datetime.now()
    bm.save(notification_dispatch)

    return True


def notification_single_view(request):
    """View to handle a single notification dispatch"""

    class SingleNotificationSchema(colander.Schema):
        notification_dispatch_id = colander.SchemaNode(
            colander.Integer(),
        )

    schema = SingleNotificationSchema()

    # Decode JSON.
    try:
        json = request.json
    except ValueError as err:
        request.response.status_int = 400
        return {'JSON error': str(err)}

    # Validate.
    try:
        appstruct = schema.deserialize(json)
    except colander.Invalid as err:
        request.response.status_int = 400
        return {'error': err.asdict()}

    # Get data out of JSON.
    notification_dispatch_id = appstruct['notification_dispatch_id']

    # Send the email.
    r = send_from_notification_dispatch(request, notification_dispatch_id)
    if not r:
        request.response.status_int = 404
        return {'error': u'Notification dispatch not Found.'}

    # Return 200.
    return {'dispatched': 'ok'}


def notification_batch_view(request):
    """View to handle a batch email notification dispatch"""
    pass


class AddNotification(object):
    """Standard boilerplate to add a notification."""

    def __init__(self, iface, role, dispatch_mapping, delay=None, bcc=None):
        """"""

        self.dispatch_mapping = dispatch_mapping
        self.notification_factory = repo.NotificationFactory
        self.role = role
        self.delay = delay
        self.bcc = bcc
        self.iface = iface

    def __call__(self, request, context, event, op, **kwargs):
        """"""

        # Unpack.
        dispatch_mapping = self.dispatch_mapping
        notification_factory = self.notification_factory(request)
        delay = self.delay
        bcc = self.bcc
        iface = self.iface
        role = self.role

        # Prepare.
        notifications = []

        # get relevant information.
        interested_users_func = get_roles_mapping(request, iface)
        interested_users = interested_users_func(request, context)
        for user in interested_users[role]:
            # Just user is a shorthand for context.user.
            if user == 'user':
                user = context.user
            # create the notifications.
            notification = notification_factory(event, user, dispatch_mapping, delay, bcc)
            notifications.append(notification)

        # Tries to optimistically send the notification.
        dispatch_notifications(request, notifications)


def add_notification(config,
                     iface,
                     state_or_action_changes,
                     role,
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
        logger.warn('Notification: roles_mapping alreaady configured for {}'.format(iface))
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
      We look them up by username, constructed from the client server name.
      The operator should be the one to receive e-mails that target
      the website / administration.
    """

    if registry == None:
        # Unpack.
        settings = request.registry.settings
    else:
        settings = registry.settings

    # Get the user, which depends on the server.
    server = os.environ.get('INI_site__title', '')
    if server.lower() == 'opendesk':
        username = u'opendesk_operator'
    elif server.lower() == 'fabhub':
        username = u'fabhub_operator'
    else:
        raise Exception('Operator user not configured.')

    return get_existing_user(username=username)


def dispatch_notifications(request, notifications):
    """Dispatches a notification directly without waiting for the
    background process."""

    lookup = repo.LookupNotificationDispatch()
    now = datetime.datetime.now()

    # Loop through the notifications and check if we should send them.
    for notification in notifications:
        # Get our create the user preferences.
        preference = repo.get_or_create_notification_preferences(notification.user)
        # Check if its due to dispatch, if so, dispatch.
        for dispatch in lookup.by_notification_id(notification.id):
            if dispatch.due <= now:
                send_from_notification_dispatch(request, dispatch.id)


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

        # Dispatch the notifications.
        config.add_request_method(dispatch_notifications, 'dispatch_notifications', reify=True)

        # Adds a notification to the resource.
        config.add_directive('add_notification', self.add_notification)
        config.registry.roles_mapping = {}

        # Adds / gets role mapping.
        config.add_directive('add_roles_mapping', self.add_roles_mapping)
        config.add_directive('get_roles_mapping', self.get_roles_mapping)

        # Operator user to receive admin related emails.
        config.add_request_method(get_operator_user, 'operator_user', reify=True)

        # Email sender.
        config.include('pyramid_postmark')

        # Expose webhook views to notifications such as single / batch emails / sms's.
        config.add_route('notification_single', '/notifications/single')
        config.add_view(notification_single_view, renderer='json',
                request_method='POST', route_name='notification_single')

        config.add_route('notification_batch', '/notifications/batch')
        config.add_view(notification_batch_view, renderer='json',
                request_method='POST', route_name='notification_batch')


includeme = IncludeMe().__call__
