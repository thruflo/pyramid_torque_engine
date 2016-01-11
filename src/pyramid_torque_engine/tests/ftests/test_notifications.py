# -*- coding: utf-8 -*-

"""High level integration / functional tests for the notifications."""

import logging
logger = logging.getLogger(__name__)

import json
import fysom
import transaction
import mock

import pyramid_basemodel as bm

from pyramid import config as pyramid_config

from pyramid_torque_engine import constants
from pyramid_torque_engine import operations as ops
from pyramid_torque_engine import unpack
from pyramid_torque_engine import repo
a, o, r, s = unpack.constants()

from . import boilerplate
from . import model


class TestNotifications(boilerplate.AppTestCase):
    """"""

    @classmethod
    def includeme(cls, config):
        """Setup the test configuration."""

        # Unpack.
        allow, on, after = unpack.directives(config)

        # Traverse.
        config.add_engine_resource(model.Model, model.IContainer)

        # Declare constants.
        s.register(
            'CREATED',
            'STARTED',
            'COMPLETED',
            'ABSOLUTELY_COMPLETED',
            'CANCELLED',
            'TRANSMOGRIFIED',
        )
        a.register(
            'START',
            'COMPLETE',
            'CANCEL',
            'POKE',
            'TRANSMOGRIFY',
        )

        # Get a handle on the model interface.
        IModel = model.IModel

        # Declare actions.
        allow(IModel, a.START, (s.CREATED), s.STARTED)
        allow(IModel, a.COMPLETE, (s.STARTED), s.COMPLETED)
        allow(IModel, a.COMPLETE, (s.COMPLETED), s.ABSOLUTELY_COMPLETED)
        allow(IModel, a.COMPLETE, (s.ABSOLUTELY_COMPLETED), Ellipsis)
        allow(IModel, a.CANCEL, (s.CREATED, s.STARTED), s.CANCELLED)
        allow(IModel, a.POKE, '*', Ellipsis)
        allow(IModel, a.TRANSMOGRIFY, '*', s.TRANSMOGRIFIED)

    def test_notification_factory(self):
        """Test the notification factory."""

        factory = repo.NotificationFactory(mock.Mock())

        # Create an eventand get it back.
        context = model.factory()
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        with transaction.manager:
            user = boilerplate.createUser()
            bm.Session.add(user)
            notification = factory(event, user, {})

            # It exists!
            self.assertTrue(notification)

        with transaction.manager:
            # The user didn't had preference before, he should have
            # default settings as it was lazily created on the factory.
            bm.Session.add(user)
            notification_preference = user.notification_preference
            self.assertIsNone(notification_preference.frequency)
            self.assertEqual(notification_preference.channel, 'email')
