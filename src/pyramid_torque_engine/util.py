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
