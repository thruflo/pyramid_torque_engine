# -*- coding: utf-8 -*-

"""Basic Pyramid views."""

import logging
logger = logging.getLogger(__name__)

from pyramid.view import view_config

@view_config(route_name='index', request_method='GET', renderer='string')
def index_view(request):
    return u'Work engine reporting for duty, sir!'
