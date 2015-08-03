# -*- coding: utf-8 -*-

"""High level integration / functional tests of the work engine actions."""

import logging
logger = logging.getLogger(__name__)

import json
import fysom

from pyramid import config as pyramid_config

from pyramid_torque_engine import constants
from pyramid_torque_engine import operations as ops
from pyramid_torque_engine import unpack
a, o, r, s = unpack.constants()

from . import boilerplate
from . import model

def get_handlers_for(dispatched, event, names_only=False):
    names = []
    handlers = []
    for dispatch in dispatched:
        data = json.loads(dispatch['data'])
        type_ = event.split(':')[0]
        if data.get(type_) == event:
            handlers.extend(dispatch['response']['handlers'])
    if names_only:
        for item in handlers:
            names.extend(item.keys())
        return names
    return handlers

class TestSubscriptions(boilerplate.AppTestCase):
    """Test ``on(context, events, operation, handler)`` rules."""

    @classmethod
    def includeme(cls, config):
        """Setup the test configuration."""

        # Unpack.
        allow, on, after = unpack.directives(config)

        # Traversal.
        config.add_engine_resource(model.Model, model.IContainer)
        config.add_engine_resource(model.Foo, model.IFooContainer)

        # Declare constants.
        s.register(
            'CREATED',
            'STARTED',
            'POKED',
        )
        a.register(
            'START',
            'POKE',
        )
        o.register(
            'BEEP',
            'BEEP_A_LOT',
            'GO_FORTH',
            'MULTIPLY',
        )

        # Get a handle on the model interface.
        IModel = model.IModel
        IFoo = model.IFoo

        # Declare actions.
        allow(IModel, a.START, (s.CREATED), s.STARTED)
        allow(IModel, a.POKE, '*', Ellipsis)
        allow(IFoo, a.POKE, '*', s.POKED)

        # Register s.STARTED state change subscribers.
        on(IModel, (s.STARTED), o.GO_FORTH, ops.Dispatch())
        on(IFoo, (s.STARTED), o.MULTIPLY, ops.Dispatch())

        # Register a catch all subscriber.
        on(IModel, '*', o.BEEP, ops.Dispatch())

        # And an action subscriber.
        on(IFoo, a.POKE, o.BEEP_A_LOT, ops.Dispatch())

    def test_state_change_event_subscriber(self):
        """Handle a state change event."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Perform a state change.
        state_changer = request.state_changer
        _, _, dispatched = state_changer.perform(context, a.START, None)

        # The s.STARTED event should trigger GO_FORTH and BEEP.
        handlers = get_handlers_for(dispatched, s.STARTED, names_only=True)
        if handlers:
            self.assertEqual(o.GO_FORTH, handlers[0])
            self.assertEqual(o.BEEP, handlers[1])
