# -*- coding: utf-8 -*-

"""Including this module sets up a configuration system for specifying which
  actions are valid for a given resource (which will be in a given state).

  Register valid actions using:

      config.add_engine_action(
          IFoo,           # context
          'a.DECLINE',    # action (verb)
          ('s.QUOTED',),  # from states
          's.DECLINED'    # to state
      )

  Then lookup a configured state machine for a resource using:

      machine = request.get_state_machine(context, action='a.DECLINE')

  The machine will have its current state set to the current state of the context,
  which means it can be used to check whether an action is valid:

      machine.can('a.DECLINE') # True or False

  You can register a valid action for any state using the `*` character and
  register an action that doesn't actually set the state using ``Ellipsis``:

      # "decline" is a valid action in any state.
      config.add_engine_action(IFoo, 'a.DECLINE', '*', 's.DECLINED')

      # "tag" doesn't change the state.
      config.add_engine_action(IFoo, 'a.TAG', ('s.DRAFT', 's.PUBLISHED'), Ellipsis)

      # "share" is a valid action in any state and doesn't change the state.
      config.add_engine_action(IFoo, 'a.SHARE', '*', Ellipsis)

"""

__all__ = [
    'AddEngineAction',
    'StateChanger',
    'get_state_machine',
]

import logging
logger = logging.getLogger(__name__)

import fysom

from collections import defaultdict

from . import util
from . import repo

class StateChanger(object):
    """High level api to validate and perform state changes that uses the
      engine configuration and client to make decisions and notify.
    """

    def __init__(self, request, **kwargs):
        self.request = request
        self.engine = kwargs.get('engine', request.torque.engine)
        self.get_machine = kwargs.get('get_machine', request.get_state_machine)

    def can_perform(self, context, action, machine=None):
        """Can ``self.context`` perform ``action`` in its current state?"""

        if machine is None:
            machine = self.get_machine(context, action=action)
        return bool(machine and machine.can(action))

    def perform(self, context, action, event):
        """Return the next state that ``self.context`` should transition to iff
          it's different from the current state.
        """

        # Unpack.
        engine = self.engine
        machine = self.get_machine(context, action=action)
        current_state = machine.current
        request = self.request

        # Prepare return value.
        next_state, has_changed, dispatched = None, False, []

        # Use the state machine to give us the next state.
        try:
            machine.trigger(action)
        except TypeError:
            # If the to_state is `Ellipsis` that means noop. Now, the current
            # fysom machinery raises a TypeError when the value is Ellipsis,
            # so we catch that error in, and only in, that case.
            if machine.current is not Ellipsis:
                raise
        # And here (regardless of whether a TypeError was raised) we revert to
        # the previous state if the new value is `Ellipsis`.
        if machine.current == Ellipsis:
            machine.current = current_state
        next_state = machine.current

        # If the state has changed create a new work status entry (with the
        # activity event hung off it) and notify.
        if next_state != current_state:
            has_changed = True
            # Create a new activity event for the new state.
            event_factory = repo.ActivityEventFactory(request)
            event_type = event_factory.type_from_context_action(event.parent, next_state)
            state_event = event_factory(event.parent, event.user, type_=event_type)
            context.set_work_status(next_state, state_event)
            # Broadcast the new event.
            dispatched.append(engine.changed(context, state_event))

        # Either way, notify that the action has been performed.
        dispatched.append(engine.happened(context, action, event=event))

        # Return all the available information.
        return next_state, has_changed, dispatched

get_state_changer = lambda request: StateChanger(request)

def get_state_machine(request, context, action=None, **kwargs):
    """Request method to lookup a Fysom state machine configured with action rules
      that determine which actions are possible from any given state.

      The machine returned has its current state set to the state of the context.
      The api for validation checks is then the native Fysom api, e.g.:

          machine = request.get_state_machine(context)
          machine.can('do_thing') # True or False depending on action config

    """

    # Compose.
    get_interfaces = kwargs.get('get_interfaces', util.get_interfaces)

    # Unpack.
    machines = request.registry.state_action_machines

    # Get a matching machine.
    machine = None
    for key in get_interfaces(context):
        fsm = machines.get(key, None)
        if not fsm:
            continue
        if action and not hasattr(fsm, action):
            continue
        machine = fsm
        break

    # Populate the current state.
    if machine:
        machine.current = context.work_status.value
    return machine

class AddEngineAction(object):
    """We use (you might say abuse) the Pyramid two-phase configuration machinery
      by eager-building a dictionary of `state_action_rules` on the registry
      keyed by context and name and then using this data to populate a single
      fsm instance for each context.
    """

    def __init__(self, **kwargs):
        self.machine_cls = kwargs.get('machine_cls', fysom.Fysom)

    def __call__(self, config, context, action, from_states, to_state):
        """We use (you might say abuse) the Pyramid two-phase configuration machinery
          by eager-building a dictionary of `state_action_rules` on the registry
          keyed by context and name and then using this data to populate a single
          fsm instance for each context.
        """
        # Unpack.
        registry = config.registry

        # Make sure ``from_states`` is an iterable.
        if not hasattr(from_states, '__iter__'):
            from_states = (from_states,)

        # Unpack the from_states to individual states, so that we can use them
        # in the discriminator: this allows the same action to be registered
        # multiple times -- usually leading to different `to_state`s -- as
        # long as the from_states are unique.
        for state in from_states:
            discriminator = ('engine.action', context, action, state)

            # Make it introspectable.
            intr = config.introspectable(category_name='engine action',
                                         discriminator=discriminator,
                                         title='An engine action',
                                         type_name=None)
            intr['value'] = (context, action, from_states, to_state)
            config.action(discriminator, lambda: self.register(registry, context), introspectables=(intr,))

        # And with that queued up, immediately store the from and two states
        # in an action_rules dict.
        value = (from_states, to_state)
        allowed = registry.state_action_rules[context].get(action)
        if allowed is None:
            registry.state_action_rules[context][action] = allowed = []

        registry.state_action_rules[context][action].append(value)


    def register(self, registry, context):
        """Iff there isn't already a finite state machine registered for this
          context then use the ``registry.state_action_rules`` to create and
          register one.

          This will noop except for the first call for each given ``context``.

          Note that it leaves the rules intact after using them, so they're
          still available for transitions to be validated against.
        """

        # Noop if we've done this already.
        machines = registry.state_action_machines
        if machines.has_key(context):
            return

        # Coerce the stored rules to an fysom.Fysom events list.
        events = []
        for key, value in registry.state_action_rules[context].items():
            for allowed_states_tuple in value:
                event = dict(name=key.encode('utf-8'), src=allowed_states_tuple[0], dst=allowed_states_tuple[1])
                events.append(event)

        # Create and register the machine.
        machine = self.machine_cls(events=events)
        registry.state_action_machines[context] = machine

class IncludeMe(object):
    """Setup the action registry and provide the `add_engine_action` directive."""

    def __init__(self, **kwargs):
        self.add_action = kwargs.get('add_action', AddEngineAction())
        self.get_state_changer = kwargs.get('get_state_changer', get_state_changer)
        self.get_state_machine = kwargs.get('get_state_machine', get_state_machine)

    def __call__(self, config):
        """Expose route and provide directive."""

        # Unpack.
        add_action = self.add_action
        get_state_changer = self.get_state_changer
        get_state_machine = self.get_state_machine

        # Provide `request.get_state_machine()` and ``request.state_changer``.
        config.add_request_method(get_state_machine, 'get_state_machine')
        config.add_request_method(get_state_changer, 'state_changer', reify=True)

        # Provide `register_action` directive.
        config.registry.state_action_machines = {}
        config.registry.state_action_rules = defaultdict(dict)
        config.add_directive('add_engine_action', add_action)

includeme = IncludeMe().__call__
