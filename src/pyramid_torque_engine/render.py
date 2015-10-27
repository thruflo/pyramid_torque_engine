# -*- coding: utf-8 -*-

"""Provide a function that serialises JSON using the pyramid default
  registered json renderer.
"""

import json
import decimal

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
            renderer = lambda x, y: _json_dumps(x)

    # Use it to dumps.
    return renderer(value, {})



"""
 Json encoding and decoding conventions
"""

class DecimalEncoder(json.JSONEncoder):
    """
    Patching the builtin jason encode to do decimals the way we want
    ie ints as nt ad floats as floats
    internally all numbers are stored as Decimals
    """

    def default(self, o):
        if hasattr(o, "__json__"):
            return o.__json__()
        if isinstance(o, decimal.Decimal):
            if o.to_integral_value() == o:
                return int(o)
            else:
                return float(o)
        return super(DecimalEncoder, self).default(o)


def _json_loads(as_json):
    return json.loads(as_json, parse_float=decimal.Decimal, parse_int=decimal.Decimal)


def _json_dumps(an_obj):
    return json.dumps(an_obj, indent=4, sort_keys=True, cls=DecimalEncoder)