# -*- coding: utf-8 -*-

"""Create and lookup activity events."""

__all__ = [
    'ActivityEventFactory',
    'LookupActivityEvent',
]

import logging
logger = logging.getLogger(__name__)

import json
import pyramid_basemodel as bm

from . import orm
from . import render
from . import util

class DefaultJSONifier(object):
    def __init__(self, request):
        self.request = request

    def __call__(self, instance):
        return instance.__json__(request=self.request)

class ActivityEventFactory(object):
    """Boilerplate to create and save ``ActivityEvent``s."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.jsonify = kwargs.get('jsonify', DefaultJSONifier(request))
        self.model_cls = kwargs.get('model_cls', orm.ActivityEvent)
        self.session = kwargs.get('session', bm.Session)

    def save(self, instance):
        self.session.add(instance)
        self.session.flush()
        return instance

    def factory(self, properties):
        parent = properties.pop('parent', None)
        instance = self.model_cls(**properties)
        if parent.activity_events:
            parent.activity_events.append(instance)
        else:
            parent.activity_events = [instance]
        return self.save(instance)

    def snapshot(self, parent, user=None):
        request = self.request
        data = {
            'parent': self.jsonify(parent),
        }
        if user:
            data['user'] = self.jsonify(user)
        return json.loads(render.json_dumps(request, data))

    def __call__(self, parent, user, type_=None, data=None, action=None):
        """Create and store an activity event."""

        # Compose.
        if data is None:
            data = {}
        if type_ is None:
            target = parent.singular_class_slug
            if action is None:
                action = parent.work_status.value
            action_name = action.split(u':')[-1].lower()
            type_ = u'{0}:{1}'.format(target, action_name)

        # Add context snapshot to the event data.
        data['snapshot'] = self.snapshot(parent, user)

        # Return a saved instance.
        return self.factory({
            'user': user,
            'parent': parent,
            'type_': type_,
            'data': data,
        })

class LookupActivityEvent(object):
    """Lookup activity events."""

    def __init__(self, **kwargs):
        self.dicts_match = kwargs.get('dicts_match', util.dicts_are_the_same)
        self.model_cls = kwargs.get('model_cls', orm.ActivityEvent)

    def __call__(self, id_):
        """Lookup by ID."""

        return self.model_cls.query.get(id_)

    def matching_status(self, quote, user, data):
        """See whether there's an exact duplicate status update."""

        # Unpack.
        model_cls = self.model_cls
        dicts_match = self.dicts_match

        # First lookup an event that *might* match.
        query = model_cls.query
        query = query.filter_by(user=user)
        query = query.filter_by(association_id=quote.activity_event_association_id)
        query = query.filter_by(message=data['message'])
        status_text = model_cls.__table__.c.data['status'].astext
        query = query.filter(status_text==data['status'])
        instance = query.first()
        if not instance:
            return None

        # Now, manually check the parent, image and video data matches.
        # (OK, we do this because we couldn't be arsed figuring out
        # how to build the SQL query to match optional JSON data).
        image_data = data.get('image', {})
        stored_image_data = instance.data.get('image', {})
        if not dicts_match(image_data, stored_image_data):
            return None
        video_data = data.get('video', {})
        stored_video_data = instance.data.get('video', {})
        if not dicts_match(video_data, stored_video_data):
            return None

        # Ok, we got a match.
        return instance
