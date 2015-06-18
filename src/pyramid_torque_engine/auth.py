# -*- coding: utf-8 -*-

"""Provides a base ``ACLContainer`` class that wraps any context in a
  generic API key aware ``ACLWrapper`` and a
"""

__all__ = [
    'ACLContainer',
    'ACLWrapper',
    'APIKeyAuthenticationPolicy',
]

import logging
logger = logging.getLogger(__name__)

import re
import zope.interface as zi

from pyramid import authentication
from pyramid import interfaces
from pyramid import security as sec

from pyramid_basemodel import container

VALID_API_KEY = re.compile(r'^\w{40}$')

class ACLWrapper(object):
    """Adapt a request to provide an ACL."""

    def __init__(self, request):
        self.request = request

    @property
    def __acl__(self):
        """Grant api key authenticated requests full access."""

        # Unpack.
        request = self.request
        settings = request.registry.settings

        # Allow everybody public access.
        rules = [
            [sec.Allow, sec.Everyone, sec.NO_PERMISSION_REQUIRED],
            [sec.Deny, sec.Everyone, sec.ALL_PERMISSIONS],
        ]

        # Allow API key authenticated requests all permissions.
        api_key = settings.get('engine.api_key')
        if api_key:
            rule = [sec.Allow, api_key, sec.ALL_PERMISSIONS]
            rules.insert(0, rule)

        return rules

class ACLContainer(container.BaseModelContainer):
    """Return contexts patched with an ACL."""

    def __getitem__(self, key):
        request = self.request
        context = super(ACLContainer, self).__getitem__(key)
        try:
            context.__acl__ = ACLWrapper(request).__acl__
        except AttributeError:
            policy = ACLWrapper(request).__acl__
            for index, rule in enumerate(policy):
                context.__acl__.insert(index, rule)
        return context

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
