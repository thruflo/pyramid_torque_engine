# -*- coding: utf-8 -*-

"""Provides the messaging machinery."""

__all__ = [
    'enable_inbound_messaging'
]

from pyramid_torque_engine import unpack
from pyramid_torque_engine import operations as ops

from pyramid_torque_engine import repo
from pyramid import path

from pyramid_simpleauth.model import get_existing_user

from interfaces import IMessaging
from notification import add_notification

import colander
import notification_table_executer
import datetime
import pyramid_basemodel as bm
import requests
import json
import os

def enable_inbound_messaging(config,
                     iface,
                     role,
                     dispatch_mapping,
                     delay=None):

    # Unpack.
    a, o, r, s = unpack.constants()
    allow, on, after = unpack.directives(config)

    iface.__bases__ = iface.__bases__ + (IMessaging, )

    # This is to send messages.
    add_notification(config,
                     iface,
                     role,
                     a.MAILBOX_MESSAGE,
                     dispatch_mapping,
                     delay)


class IncludeMe(object):
    """Set up the state change event subscription system and provide an
      ``add_engine_subscriber`` directive.
    """

    def __init__(self, **kwargs):
        self.enable_inbound_messaging = kwargs.get('enable_inbound_messaging', enable_inbound_messaging)

    def __call__(self, config):
        """Handle `/events` requests and provide subscription directive."""

        # Enables the messaging machinery to the resource.
        config.add_directive('enable_inbound_messaging', self.enable_inbound_messaging)




includeme = IncludeMe().__call__
