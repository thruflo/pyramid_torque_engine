# -*- coding: utf-8 -*-

"""Standard operation boilerplate."""

__all__ = [
    'Dispatch',
    'Perform',
    'Result',
    'get_targets',
]

import logging
logger = logging.getLogger(__name__)

import fysom
import pyramid_basemodel as bm

from . import repo

def get_targets(context, attr):
    """Get context.attr as a list of targets.

      If context was a Job and self.attr was 'user' then targets would be
      `[job.user]`. If the context was a Job and self.attr was `maker_jobs` then
      targets would be `job.maker_jobs`.

      If attr is None than targets = [context]
    """

    relation = getattr(context, attr) if attr else context
    if relation is None:
        targets = []
    elif hasattr(relation, '__iter__'):
        targets = relation
    else:
        targets = [relation]
    return targets

class Dispatch(object):
    """Standard boilerplate for an operation that dispatches to a hook."""

    def __init__(self, path=None, extract=None):
        """By default an operation called `o.DO_FOO` will dispatch to
          `/hooks/do_foo`, unless a path.
        """

        self.path = path
        self.extract = extract

    def __call__(self, request, context, event, op, **kwargs):
        """Dispatch a task to the hook by path, with a standard set of data
          optionally augemented with extra data extracted by the ``pliers``.
        """

        # Get the hook path.
        path = self.path if self.path else op.split(':')[-1].lower()

        # Build the generic data.
        event_id = event.id if event else None
        data = {
            'event_id': event_id,
            'operation': op,
        }
        instance_id_key = '{0}_id'.format(context.singular_class_slug)
        data[instance_id_key] = context.id

        # Patch it with any extra specific data for this operation.
        if self.extract:
            extra = self.extract(context, event=event)
            if extra:
                data.update(extra)

        # Dispatch to the hook.
        dispatch = request.torque.dispatch(path, data, **kwargs)
        return {op: [dispatch]}

class Perform(object):
    """Boilerplate for an operation that performs an action on a relation."""

    def __init__(self, *args):
        """If only passed one arg, it's the action and attr is None. If passed
          two args, the first one is the attr and the second is the action.
        """

        if len(args) == 1:
            self.attr = None
            self.action = args[0]
        else:
            self.attr = args[0]
            self.action = args[1]

    def __call__(self, request, context, event, op):
        """Notify either the context or its relation that this operation has had
          the given result.
        """

        # Get the targets.
        targets = get_targets(context, self.attr)

        # For each target, validate and perform the action.
        all_dispatched = []
        action = self.action
        session = bm.Session()
        session.add(event)
        user = event.user
        data = event.data
        state_changer = request.state_changer
        event_factory = repo.ActivityEventFactory(request)
        for target in targets:
            if state_changer.can_perform(target, action):
                action_event = event_factory(target, user, action=action)
                try:
                    _, _, dispatched = state_changer.perform(target, action,
                            action_event)
                except fysom.FysomError as err:
                    logger.warn(err)
                else:
                    all_dispatched.extend(dispatched)
        return {op: all_dispatched}

class Result(object):
    """Boilerplate for an operation that notifies a relation about a result."""

    def __init__(self, *args):
        """If only passed one arg, it's the result and attr is None. If passed
          two args, the first one is the attr and the second is the result.
        """

        attr, result = args if len(args) > 1 else None, args[0]
        self.result = result
        self.attr = attr

    def __call__(self, request, context, event, op):
        """Notify either the context or its relation that this operation has had
          the given result.
        """

        # Get the targets.
        targets = get_targets(context, self.attr)

        # Tell them about the result of the operation.
        dispatched = []
        engine = request.torque.engine
        for target in targets:
            dispatch = engine.result(target, op, self.result, event_id=event.id)
            dispatched.append(dispatch)
        return {op: dispatched}
