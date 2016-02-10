# -*- coding: utf-8 -*-

"""High level integration / functional tests of the work engine actions."""

import logging
logger = logging.getLogger(__name__)

import fysom
import transaction
import pyramid_basemodel as bm

from pyramid import config as pyramid_config

from pyramid_torque_engine import unpack
a, o, r, s = unpack.constants()

from . import boilerplate
from . import model

from pyramid_torque_engine import repo

class TestAllowedActions(boilerplate.AppTestCase):
    """Test ``allow(context, action, (from_states), to_state)`` rules."""

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

    def test_initial_state(self):
        """Models start off in ``state:CREATED``."""

        context = model.factory()
        self.assertEqual(context.work_status.value, s.CREATED)

    def test_invalid_action(self):
        """Performing an invalid action will raise an error."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Ask for permission.
        state_changer = request.state_changer
        self.assertFalse(state_changer.can_perform(context, a.COMPLETE))

        # Beg for forgiveness.
        err = fysom.FysomError
        self.assertRaises(err, state_changer.perform, context, a.COMPLETE, None)

    def test_perform_action(self):
        """Performing an invalid action will work."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Create a dummy event and get it back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # Check we're allowed.
        state_changer = request.state_changer
        with transaction.manager:
            bm.Session.add(context)
            self.assertTrue(state_changer.can_perform(context, a.START))
            context_id = context.id

        # Perform the action.
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        context = model.Model.query.get(context_id)
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            _ = state_changer.perform(context, a.START, event)
            status = context.work_status.value

        # The context is now in the configured state.
        self.assertEqual(status, s.STARTED)

    def test_asterix_and_ellipsis(self):
        """You can perform an action registered on any state."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Create a dummy event and get it back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # First of all it's OK to perform the action in any state.
        state_changer = request.state_changer
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.POKE, event)

            bm.Session.add(event)
            bm.Session.add(context)
            s1 = context.work_status.value
            state_changer.perform(context, a.START, event)

            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.POKE, event)
            s2 = context.work_status.value
            context_id = context.id

        # And because it has a to state of Ellipsis, it stays in
        # whatever state its in.
        self.assertEqual(s1, s.CREATED)
        self.assertEqual(s2, s.STARTED)

        # Although an '*' from state can prescribe a to state too.
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.TRANSMOGRIFY, event)
            s3 = context.work_status.value
        self.assertEqual(s3, s.TRANSMOGRIFIED)

    def test_multiple_rules(self):
        """A from state can have multiple to states."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory(initial_state=s.STARTED)

        # Create a dummy event and get it back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # Complete -> completed.
        state_changer = request.state_changer
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.COMPLETE, event)
            s1 = context.work_status.value
            context_id = context.id

        self.assertEqual(s1, s.COMPLETED)

        # Complete -> absolutely completed.
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.COMPLETE, event)
            s2 = context.work_status.value
        self.assertEqual(s2, s.ABSOLUTELY_COMPLETED)

        # Complete -> ... the same state ...
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        context = model.Model.query.get(context_id)
        with transaction.manager:
            bm.Session.add(event)
            state_changer.perform(context, a.COMPLETE, event)
            s3 = context.work_status.value
        self.assertEqual(s3, s.ABSOLUTELY_COMPLETED)

    def test_multiple_states(self):
        """A context can allow an action for multiple states."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Create a dummy event and get it back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # Cancel when created.
        state_changer = request.state_changer
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.CANCEL, event)
            s1 = context.work_status.value
        self.assertEqual(s1, s.CANCELLED)

        # Cancel when started.
        c2 = model.factory(initial_state=s.STARTED)
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            state_changer.perform(c2, a.CANCEL, event)
            s2 = c2.work_status.value
        self.assertEqual(s2, s.CANCELLED)

class TestConflictingActions(boilerplate.AppTestCase):
    """Test two identical allow rules raise a conflict error."""

    @classmethod
    def includeme(cls, config):
        """Setup the test configuration."""

        allow, on, after = unpack.directives(config)
        config.add_engine_resource(model.Model, model.IContainer)
        s.register('CREATED', 'STARTED',)
        a.register('START',)

        IModel = model.IModel
        allow(IModel, a.START, (s.CREATED), s.STARTED)
        allow(IModel, a.START, (s.CREATED), s.STARTED)

    def test_conflicting_actions(self):
        """Performing an invalid action will raise an error."""

        err = pyramid_config.ConfigurationError
        self.assertRaises(err, self.factory) # calls the includeme

class TestInterfaceSpecificity(boilerplate.AppTestCase):
    """Test edge cases where instances provide multiple interfaces."""

    @classmethod
    def includeme(cls, config):
        """Setup the test configuration."""

        allow, on, after = unpack.directives(config)
        config.add_engine_resource(model.Model, model.IContainer)
        config.add_engine_resource(model.Foo, model.IFooContainer)
        s.register(
            'CREATED',
            'DRAFTED',
            'PUBLISHED',
            'PENDING_MODERATION',
        )
        a.register(
            'DRAFT',
            'PUBLISH',
            'APPROVE',
            'POKE',
        )

        allow(model.IModel, a.DRAFT, (s.CREATED), s.DRAFTED)
        allow(model.IModel, a.PUBLISH, (s.DRAFTED), s.PUBLISHED)
        allow(model.IFoo, a.PUBLISH, (s.DRAFTED), s.PENDING_MODERATION)
        allow(model.IFoo, a.APPROVE, (s.PENDING_MODERATION), s.PUBLISHED)
        allow(model.IFoo, a.POKE, '*', Ellipsis)

    def test_for_model_without_moderation(self):
        """Instances that provide IModel should publish without moderation."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory()

        # Create a dummy event and get it back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # Draft -> publish -> s.PUBLISHED.
        state_changer = request.state_changer

        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.DRAFT, event)
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.PUBLISH, event)
            s1 = context.work_status.value
        self.assertEqual(s1, s.PUBLISHED)

    def test_for_foo_with_moderation(self):
        """Instances that provide *both* IModel & IFoo should require moderation."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        context = model.factory(cls=model.Foo)

        # Create two dummy events and get them back.
        event_id = boilerplate.createEvent(context)
        event = repo.LookupActivityEvent()(event_id)

        # Draft -> publish -> s.PENDING_MODERATION.
        state_changer = request.state_changer
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.DRAFT, event)
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.PUBLISH, event)
            s1 = context.work_status.value
            context_id = context.id
        self.assertEqual(s1, s.PENDING_MODERATION)

        # Approve -> s.PUBLISHED.
        # We have to use a transaction manager because perform creates
        # a new event on state change.
        # context = model.Foo.query.get(context_id)
        with transaction.manager:
            bm.Session.add(event)
            bm.Session.add(context)
            state_changer.perform(context, a.APPROVE, event)
            s2 = context.work_status.value
        self.assertEqual(s2, s.PUBLISHED)

    def test_must_provide_interface(self):
        """If you don't provide the interface, you don't have the rule."""

        # Prepare.
        app = self.factory()
        request = self.getRequest(app)
        m = model.factory()
        f = model.factory(cls=model.Foo)

        # It's OK to poke a foo.
        state_changer = request.state_changer
        self.assertTrue(state_changer.can_perform(f, a.POKE))

        # But not a model.
        self.assertFalse(state_changer.can_perform(m, a.POKE))
