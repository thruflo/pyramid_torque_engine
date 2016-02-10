# -*- coding: utf-8 -*-

"""Create and lookup activity events."""

__all__ = [
    'ActivityEventFactory',
    'LookupActivityEvent',
    'NotificationFactory',
    'LookupNotification',
    'LookupNotificationDispatch',
    'NotificationPreferencesFactory',
    'get_or_create_notification_preferences',
]

import logging
logger = logging.getLogger(__name__)

import json
import pyramid_basemodel as bm

from . import orm
from . import render
from . import util

import datetime
from dateutil.relativedelta import relativedelta

class DefaultJSONifier(object):
    def __init__(self, request):
        self.request = request

    def __call__(self, instance):
        return render.json_dumps(self.request, instance)

class ActivityEventFactory(object):
    """Boilerplate to create and save ``ActivityEvent``s."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.jsonify = kwargs.get('jsonify', DefaultJSONifier(request))
        self.model_cls = kwargs.get('model_cls', orm.ActivityEvent)
        self.session = kwargs.get('session', bm.Session)

    @staticmethod
    def type_from_context_action(parent, action=None):
        """Returns a formated type_."""

        target = parent.singular_class_slug
        if action is None:
            action = parent.work_status.value
        action_name = action.split(u':')[-1].lower()
        type_ = u'{0}:{1}'.format(target, action_name)
        return type_

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

    def inline(self, instance):
        return {
            'id': instance.id,
            'type': instance.class_slug,
        }

    def snapshot(self, parent, user=None):
        request = self.request
        data = {
            'parent': self.inline(parent),
        }
        if user:
            if isinstance(user, basestring):
                data = json.loads(user)
                user_data = {
                    'id': data['id'],
                    'type': 'auth_users'
                }
            else:
                user_data = self.inline(user)
            data['user'] = user_data
        return data

    def __call__(self, parent, user, type_=None, data=None, action=None):
        """Create and store an activity event."""

        # Compose.
        if data is None:
            data = {}
        if type_ is None:
            type_ = self.type_from_context_action(parent, action)

        # Add context snapshot to the event data.
        self.session.add(parent)
        data['snapshot'] = self.snapshot(parent, user)

        # Return a saved instance.
        data = self.factory({
            'user': user,
            'parent': parent,
            'type_': type_,
            'data': data,
        })
        return data

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
        query = query.filter(status_text == data['status'])
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

class NotificationFactory(object):
    """Boilerplate to create and save ``Notification``s."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.jsonify = kwargs.get('jsonify', DefaultJSONifier(request))
        self.notification_cls = kwargs.get('notification_cls', orm.Notification)
        self.notification_dispatch_cls = kwargs.get('notification_dispatch_cls',
                orm.NotificationDispatch)
        self.notification_preference_factory = kwargs.get('notification_preference_factory',
                NotificationPreferencesFactory())
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, event, user, dispatch_mapping, delay=None):
        """Create and store a notification and a notification dispatch."""

        # Unpack.
        session = self.session

        # Create notification.
        notification = self.notification_cls(user=user, event=event)
        session.add(notification)
        due = datetime.datetime.now()
        email = user.best_email.address

        # Get or create user preferences.
        preference = get_or_create_notification_preferences(user)
        timeframe = preference.frequency

        # If daily normalise to 20h of each day.
        if timeframe == 'daily':
            if due.hour > 20:
                due = datetime.datetime(due.year, due.month, due.day + 1, 20)
            else:
                due = datetime.datetime(due.year, due.month, due.day, 20)

        # If hourly normalise to the next hour.
        elif timeframe == 'hourly':
            due = datetime.datetime(due.year, due.month, due.day, due.hour + 1, 0)

        # Check if there's a delay in minutes add to it.
        if delay:
            delay = relativedelta(minutes=delay)
            due = due + delay

        # Create a notification dispatch for each channel.
        for k, v in dispatch_mapping.items():
            notification_dispatch = self.notification_dispatch_cls(notification=notification,
                    due=due, category=k, view=v['view'],
                    single_spec=v['single'], batch_spec=v['batch'], address=email)
            session.add(notification_dispatch)

        # Save to the database.
        session.flush()

        return notification

class LookupNotificationDispatch(object):
    """Lookup notifications dispatch."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.NotificationDispatch)

    def __call__(self, id_):
        """Lookup by notifiction dispatch id."""

        return self.model_cls.query.get(id_)

    def by_notification_id(self, id_, type=u'email'):
        """Lookup all notification dispatches that belong to
        the notification id and type."""

        return self.model_cls.query.filter_by(notification_id=id_).all()

def get_or_create_notification_preferences(user):
    """Gets or creates the notification preferences for the user."""
    notification_preference_factory = NotificationPreferencesFactory()
    preference = user.notification_preference
    if preference is None:
        preference = notification_preference_factory(user.id)
        bm.Session.add(user)
    return preference


class NotificationPreferencesFactory(object):
    """Boilerplate to create and save ``Notification preference``s."""

    def __init__(self, **kwargs):
        self.notification_preference_cls = kwargs.get('notification_preference_cls',
                orm.NotificationPreference)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user_id, frequency=None, channel='email'):
        """Create and store a notification and a notification dispatch."""

        # Unpack.
        session = self.session

        # Create notification.
        notification_preference = self.notification_preference_cls(
                user_id=user_id, frequency=frequency, channel=channel)

        # Save to the database.
        session.add(notification_preference)
        session.flush()

        return notification_preference
