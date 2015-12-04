# -*- coding: utf-8 -*-

from pyramid_torque_engine import orm
from pyramid_torque_engine import repo

from sqlalchemy import create_engine
from pyramid_basemodel import bind_engine, save, Session

import os
import datetime
import json
import requests
import transaction

AVAILABLE_CHANNELS = ['sms', 'email']


def dispatch_user_notifications(user, user_notifications):
    """ 4. for each channel loop and either write out a single or a batch dispatch task with the
        NotificationDispatcher ids e.g: /dispatch_email, /dispatch_sms and etc.
    """
    for ch in AVAILABLE_CHANNELS:
        # XXX check for preferences e.g: and user.channel == ch
        to_dispatch = [d for d in user_notifications if d.category == ch]
        if len(to_dispatch) == 1:
            dispatch = to_dispatch[0]
            r = requests.post('http://127.0.0.1:5100/hooks/email_single_notification', data=json.dumps({'notification_dispatch_id': dispatch.id}))
            # if sent successfuly...
            if r.status_code < 300:
                dispatch.sent = datetime.datetime.now()
                save(dispatch)
        elif len(to_dispatch) > 1:
            # if sent successfuly...
            d.sent = datetime.datetime.now()
            save(d)
        else:
            print 'nothing here', to_dispatch
    Session.flush()


def run():
    # Bind to the database.
    engine = create_engine(os.environ['DATABASE_URL'])
    bind_engine(engine, should_create=False)

    # Prepare.
    notification_cls = orm.Notification
    notification_dispatch_cls = orm.NotificationDispatch
    notification_preference_factory = repo.NotificationPreferencesFactory()
    now = datetime.datetime.now()

    # Run the algorithm.
    with transaction.manager:
        # 1. ignore all the notifications from the Notification table that have read field set.
        unread_notifications = notification_dispatch_cls.query.join(notification_cls).filter(notification_cls.read == None)

        # 2. get all of the non duplicated user ids who are due to dispatch and have not been sent.
        due_to_dispatch = unread_notifications.filter(notification_dispatch_cls.due <= now).filter(notification_dispatch_cls.sent == None)
        user_ids_to_dispatch = set()
        for dispatch in due_to_dispatch.all():
            user_ids_to_dispatch.add(dispatch.notification.user_id)

        # also use it when a new notification is created so it's sent straightaway

        # check for transient internet errors
        # tests in pyramid torque engine

        # 3. for each user id get all of the notifications grouped by channel
        for user_id in user_ids_to_dispatch:
            # Build the NotificationPreference object so we can get the preferences.
            user = orm.NotificationPreference.query.filter_by(user_id=user_id).one()
            # If we don't have a notification preference object, we just create it on the fly.
            if user is None:
                user = notification_preference_factory(user_id)
            user_notifications = due_to_dispatch.filter(notification_cls.user_id == user_id).all()
            dispatch_user_notifications(user, user_notifications)


if __name__ == '__main__':
    run()
