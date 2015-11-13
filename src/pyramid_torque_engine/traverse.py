# -*- coding: utf-8 -*-

"""Provide a traversal root that looks up registered resources."""

__all__ = [
    'EngineRoot',
]

import logging
logger = logging.getLogger(__name__)

import zope.interface as zi
import pyramid_basemodel as bm

from pyramid_basemodel import container
from pyramid_basemodel import tree

from . import auth
from . import util

QUERY_SPEC = {
    'property_name': 'id',
    'validator': util.id_validator,
}

class EngineRoot(tree.BaseContentRoot):
    """Lookup registered resources by tablename and id, wrapping the result
      in an ACL wrapper that restricts access by api key.
    """

    @property
    def mapping(self):
        registry = self.request.registry
        return getattr(registry, 'engine_resource_mapping', {})

class ResourceContainer(container.BaseModelContainer):
    pass

def add_engine_resource(config, resource_cls, container_iface, query_spec=None):
    """Populate the ``registry.engine_resource_mapping``."""

    # Compose.
    if not query_spec:
        query_spec = QUERY_SPEC

    # Unpack.
    registry = config.registry
    tablename = resource_cls.class_slug

    # Create the container class.
    class_name = '{0}Container'.format(resource_cls.__name__)
    container_cls = type(class_name, (ResourceContainer,), {})
    zi.classImplements(container_cls, container_iface)

    # Make sure we have a mapping.
    if not hasattr(registry, 'engine_resource_mapping'):
        registry.engine_resource_mapping = {}

    # Prepare a function to actually populate the mapping.
    def register():
        mapping = registry.engine_resource_mapping
        mapping[tablename] = (resource_cls, container_cls, query_spec)

    # Register the configuration action with a discriminator so that we
    # don't register the same class twice.
    discriminator = ('engine.traverse', tablename,)

    # Make it introspectable.
    intr = config.introspectable(category_name='engine resources',
                                 discriminator=discriminator,
                                 title='An engine resource',
                                 type_name=None)
    intr['value'] = resource_cls, container_iface

    config.action(discriminator, register, introspectables=(intr,))


def includeme(config, add_resource=None):
    """Provide the ``config.add_engine_resource`` directive."""

    config.add_directive('add_engine_resource', add_engine_resource)
