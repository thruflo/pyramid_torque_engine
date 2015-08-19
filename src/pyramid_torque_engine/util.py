# -*- coding: utf-8 -*-

"""Utility functions."""

import logging
logger = logging.getLogger(__name__)

import collections
import inspect
import urllib
import zope.interface

class DeclaredNamespacedNamedTuple(object):
    """Instantiate one of these with a namespace. Call ``register`` to add
      values and then access as normal attributes. I.e.:

          >>> ACTIONS = DeclaredNamespacedNamedTuple(u'Action')
          >>> ACTIONS.register(
          ...     u'ACCEPT',
          ...     u'DECLINE',
          ... )
          >>> ACTIONS.ACCEPT
          u'action:ACCEPT'
          >>> ACTIONS.FOO #doctest:+ELLIPSIS
          Traceback (most recent call last):
          ...
          NameError: name: FOO not found in DeclaredNamespacedNamedTuple
    """

    def __init__(self, namespace, **kwargs):
        self.finalised = False
        self.values = []
        self.namespace = namespace
        self.as_tuple = kwargs.get('as_tuple', as_namespaced_named_tuple)
        self.named_tuple = self.as_tuple(self.namespace, self.values)

    def register(self, *new_values):
        """Maintain a sorted, de-duplicated list of values and, after every
          registration call, wrap them as a new namespaced named tuple.
        """

        if self.finalised:
            has_new_value = False
            for value in new_values:
                if value not in self.values:
                    msg = 'Can\'t register new {0} values after finalising.'
                    raise ValueError(msg.format(self.namespace))
            return

        self.values = sorted(list(set(self.values + list(new_values))))
        self.named_tuple = self.as_tuple(self.namespace, self.values)

    def finalise(self):
        """Stop accepting new values."""

        self.finalised = True

    def __getattr__(self, name):
        """Provide dot attribute access to the named tuple."""

        if not hasattr(self.named_tuple, name):
            raise NameError("name: %s not found in DeclaredNamespacedNamedTuple" % name)
        return getattr(self.named_tuple, name)


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

def dicts_are_the_same(a, b):
    """Compare two dicts, ``a`` and ``b`` and return ``True`` if they contain
      exactly the same items.

      Ref: http://stackoverflow.com/a/17095033
    """

    return not len(set(a.items()) ^ set(b.items()))

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

    if hasattr(instance, '_class_slug'):
        slug = instance._class_slug
    else:
        slug = instance.__tablename__
    return pack_object_id(slug, instance.id)

def id_validator(node, value):
    try:
        assert int(value) > 0
    except Exception:
        msg = u'{0} is not a valid instance id.'.format(value)
        raise ValueError(msg)

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
