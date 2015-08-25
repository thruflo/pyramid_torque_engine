# -*- coding: utf-8 -*-

"""Provides a base ``ACLContainer`` class that wraps any context in a
  generic API key aware ``ACLWrapper`` and a
"""

__all__ = [
    'APIKeyAuthenticationPolicy',
    'APIKeyAuthorizationPolicy',
]

import logging
logger = logging.getLogger(__name__)

import re
import zope.interface as zi

from pyramid import authentication
from pyramid import interfaces

VALID_API_KEY = re.compile(r'^\w{40}$')

@zi.implementer(interfaces.IAuthenticationPolicy)
class APIKeyAuthenticationPolicy(authentication.CallbackAuthenticationPolicy):
    """A Pyramid authentication policy which obtains credential data from the
      ``request.headers['api_key']``.
    """

    def __init__(self, header_keys, **kwargs):
        if isinstance(header_keys, basestring):
            header_keys = [header_keys]
        self.header_keys = header_keys
        self.valid_key = kwargs.get('valid_key', VALID_API_KEY)

    def unauthenticated_userid(self, request):
        """The ``api_key`` value found within the ``request.headers``."""

        api_key = None
        for key in self.header_keys:
            value = request.headers.get(key, None)
            if value is not None:
                api_key = value
                break
        if api_key and self.valid_key.match(api_key):
            return api_key.decode('utf8')

    def remember(self, request, principal, **kw):
        """A no-op. There's no way to remember the user."""

        return []

    def forget(self, request):
        """A no-op. There's no user to forget."""

        return []

@zi.implementer(interfaces.IAuthorizationPolicy)
class APIKeyAuthorizationPolicy(object):
    """Global authorization policy that ignores the context and just checks
      whether the target api key is in the principals list.
    """

    def __init__(self, api_key):
        self.api_key = api_key

    def permits(self, context, principals, permission):
        return self.api_key in principals

    def principals_allowed_by_permission(self, context, permission):
        raise NotImplementedError
