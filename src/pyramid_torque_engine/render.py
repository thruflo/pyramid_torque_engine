# -*- coding: utf-8 -*-

"""Provide a function that serialises JSON using the pyramid default
  registered json renderer.
"""

from pyramid import interfaces as pi

def get_json_renderer(request):
    registry = request.registry
    factory = registry.getUtility(pi.IRendererFactory, name='json')
    return factory(None)

def json_dumps(request, value):
    renderer = get_json_renderer(request)
    return renderer(value, {})
