# -*- coding: utf-8 -*-

"""Provides a ``includeme()`` pyramid configuration entry point."""

import logging
logger = logging.getLogger(__name__)

import os

from pyramid import authorization
from pyramid import security
from pyramid.settings import asbool

from . import auth
from . import constants
from . import util

DEFAULTS = {
    'engine.api_key': util.get_var(os.environ, constants.ENGINE_API_KEY_NAMES),
}

class IncludeMe(object):
    """Configure the key parts of the work engine application for normal
      usage -- note that this is not the full configuration required for
      this software to work, just some partial setup that should be
      common to all applications.

      Notably, we don't configure the model, we don't local down HSTS and
      we don't actually make a WSGI app. However, we do clobber auth and
      expose an index route, so if that's not what an app needs, it should
      craft its own configuration following this as a reference.

      Also n.b.: that you don't need to include this if you just want a
      `request.torque.dispatch` client -- in that case you can just
      `config.include('pyramid_torque_engine.client')`.
    """

    def __init__(self, **kwargs):
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.authentication_policy = kwargs.get('authentication_policy',
                auth.APIKeyAuthenticationPolicy(constants.ENGINE_API_KEY_NAMES))
        self.authorization_policy_cls = kwargs.get('authorization_policy_cls',
                auth.APIKeyAuthorizationPolicy)

    def __call__(self, config):
        """Apply the default settings and auth policies, expose views
          and provide configuration directives.
        """

        # Apply default settings.
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            settings.setdefault(key, value)

        # Apply auth policies.
        api_key = settings.get('engine.api_key')
        should_authenticate = api_key is not None
        if not should_authenticate:
            config.set_default_permission(security.NO_PERMISSION_REQUIRED)
        else:
            authorization_policy = self.authorization_policy_cls(api_key)
            config.set_authentication_policy(self.authentication_policy)
            config.set_authorization_policy(authorization_policy)
            config.set_default_permission('view')

        # Expose the `/events` and `/results` views and provide the
        # work engine configuration directives.
        config.include('pyramid_torque_engine.action')
        config.include('pyramid_torque_engine.subscribe')
        config.include('pyramid_torque_engine.transition')

        # Provide the ``config.add_engine_resource`` directive to enable
        # instance id conatiner based traversal for a given ORM class.
        config.include('pyramid_torque_engine.traverse')

        # Provide the ``config.add_notification`` directive to enable
        # notifications to be added.
        config.include('pyramid_torque_engine.notification')

        # Provide the `request.torque` client API.
        config.include('pyramid_torque_engine.client')

        # Expose the `/` index view.
        config.add_route('index', '/')
        config.scan('pyramid_torque_engine.view')

includeme = IncludeMe().__call__
