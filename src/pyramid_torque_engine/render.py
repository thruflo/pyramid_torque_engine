# -*- coding: utf-8 -*-

"""Provide a function that serialises JSON using the pyramid default
  registered json renderer.
"""

from util import json_dumps as decimal_json_dumps

from pyramid import interfaces as pi

def get_json_renderer(request):
    registry = request.registry
    factory = registry.getUtility(pi.IRendererFactory, name='json')
    return factory(None)

def json_dumps(request, value):
    """Use the registered utility to serialize to a JSON string."""

    # Get the registered renderer utility.
    renderer = get_json_renderer(request)
    is_testing = request.environ.get('paste.testing', False)
    if is_testing:
        import mock
        if isinstance(renderer, mock.Mock):
            renderer = lambda x, y: decimal_json_dumps(x)

    # Use it to dumps.
    return renderer(value, {})
