# -*- coding: utf-8 -*-

"""Utility functions."""

import logging
logger = logging.getLogger(__name__)

import collections
import inspect
import urllib
import zope.interface

def as_namespaced_named_tuple(name, data):
    """Takes a name and either a dict or list of strings, uses the name
      to namespace the values and return as a named tuple::

          >>> foo = as_namespaced_named_tuple(u'Foo', [u'a', u'b'])
          >>> foo.a
          u'foo:a'
          >>> baz = as_namespaced_named_tuple(u'Baz', {'a': u'b'})
          >>> baz.a
          u'baz:b'
    """

    ns = name.lower()
    if hasattr(data, 'items'): # dict
        keys, values = zip(*data.items())
    else: # list
        keys, values = data, data
    values = [u'{0}:{1}'.format(ns, item) for item in values]
    return collections.namedtuple(name, keys)(*values)

def as_request_params(**kwargs):
    """Coerce kwargs into a tuple of param=value strings."""

    return tuple('{0}={1}'.format(k, v) for k, v in kwargs.items())

def get_interfaces(resource):
    """Return a list, most specific first, of the classes and interfaces
      provided or implemented by the resource (depending on whether its
      a class or not) -- and their ancestor classes and interfaces.

      See http://docs.zope.org/zope.interface/README.html#specifications
    """

    if hasattr(resource, '__sro__'): # it's an interface.
        ifaces = resource.__sro__
    elif inspect.isclass(resource):
        ifaces = zope.interface.implementedBy(resource).__sro__
    else:
        ifaces = zope.interface.providedBy(resource).__sro__
    return ifaces

def get_object_id(instance):
    """Return ``u'tablename#ID'`` for ``instance``."""

    return pack_object_id(instance.__tablename__, instance.id)

def pack_object_id(tablename, target_id):
    return u'{0}#{1}'.format(tablename, target_id)

def unpack_object_id(object_id):
    """Return ``(table_name, id)`` for ``object_id``::

          >>> unpack_object_id(u'questions#1234')
          (u'questions', 1234)
          >>> unpack_object_id(u'questions#*')
          (u'questions', None)

    """

    parts = object_id.split('#')
    try:
        parts[1] = int(parts[1])
    except ValueError:
        parts[1] = None
    return tuple(parts)

def get_unpacked_object_id(instance):
    """Return ``(table_name, id)`` for ``instance``."""

    oid = get_object_id(instance)
    return unpack_object_id(oid)

def pack_object_id(tablename, target_id):
    return u'{0}#{1}'.format(tablename, target_id)

def get_var(environ, keys, default=None):
    """Try each of the keys in turn before falling back on the default."""

    for key in keys:
        if environ.has_key(key):
            return environ.get(key)
    return default
