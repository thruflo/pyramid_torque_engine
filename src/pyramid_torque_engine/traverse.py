# -*- coding: utf-8 -*-

"""XXX in here what we want is to provide an ``EngineRoot`` as per
  the previous tree module but one where the resource / container
  mapping is got from the registry, which is populated by a
  ``register_resource`` directive that this module provides.
"""

__all__ = [
    'EngineRoot',
    # config.add_engine_resource
]

import logging
logger = logging.getLogger(__name__)

import colander

from pyramid_basemodel import tree

from . import auth

class EngineRoot(tree.BaseContentRoot):
    """Lookup contexts by tablename and id and restrict access by api key."""

    @property
    def __acl__(self):
        wrapper = auth.ACLWrapper(self.request)
        return wrapper.__acl__

    @property
    def mapping(self):
        """Lookup instances of the selected model classes by tablename and id."""

        config = {
            'property_name': 'id',
            'validator': colander.Range(min=1),
        }
        resources = NotImplemented # get from registry
        return {
            cls.__tablename__: (cls, iface, config) for cls, iface in resources
        }

def includeme(config):
    # XXX provide register resource directive
    raise NotImplementedError
