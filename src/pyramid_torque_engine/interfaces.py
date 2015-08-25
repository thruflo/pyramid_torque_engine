# -*- coding: utf-8 -*-

"""Provides interfaces. These are generally used, in tandem with the
  Pyramid framework machinery, to hang functionality off, e.g.:

  * "expose this view to anything that provides this interface"
  * "subscribe to any event that provides this interface"
  * "get the utility registered as providing this interface"
"""

__all__ = [
    'IWorkStatus',
]

from pyramid import interfaces

class IWorkStatus(interfaces.Interface):
    """Provided by Work Status Machine."""
