# -*- coding: utf-8 -*-

"""Provides an ``ActivityEvent`` model to store arbitrary event data and a
  ``WorkStatusMixin`` with generic association table that provides a
  ``work_status`` relationship when mixed into an ORM class.
"""

__all__ = [
    'ActivityEvent',
    'WorkStatus',
    'WorkStatusMixin',
]

import os

from datetime import datetime

from sqlalchemy import event
from sqlalchemy import orm
from sqlalchemy import schema
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext import associationproxy as proxy
from sqlalchemy.ext import declarative
from sqlalchemy.ext import hybrid

import pyramid_basemodel as bm
from pyramid_simpleauth import model as simpleauth_model

import zope.interface as zi
from . import interfaces

# XXX It may be better to require the code that creates a work status to
# explicitly set the value rather than relying on this abitrary default.
DEFAULT_STATE = os.environ.get('ENGINE_DEFAULT_STATE', u'state:CREATED')


class ActivityEventAssociation(bm.Base, bm.BaseMixin):
    """Polymorphic base that's used to associate a collection of
      ``ActivityEvent``s with a parent.
    """

    __tablename__ = 'activity_event_associations'
    discriminator = schema.Column(types.Unicode(64))
    __mapper_args__ = {'polymorphic_on': discriminator}

class ActivityEvent(bm.Base, bm.BaseMixin):
    """Something that happened. Has an event type made out of target
      and action (e.g.: `job:confirmed`) and an arbitrary JSON payload.
    """

    # Store all events in a single table...
    __tablename__ = 'activity_events'

    # ... whilst allowing sub classes to add fields by specifying a discriminator.
    discriminator = schema.Column(types.Unicode(64))
    __mapper_args__ = {'polymorphic_on': discriminator}

    # An event is normally -- but not always -- performed by a user.
    user_id = schema.Column(
        types.Integer,
        schema.ForeignKey('auth_users.id'),
    )
    user = orm.relationship(
        simpleauth_model.User,
        backref='activity_events',
    )

    # Can belong to a ``parent`` via a ``ActivityEventAssociation``.
    association_id = schema.Column(
        types.Integer,
        schema.ForeignKey('activity_event_associations.id'),
    )
    assocation = orm.relationship(ActivityEventAssociation, backref='activity_events')

    @property
    def parent(self):
        return self.assocation.parent

    @parent.setter
    def parent(self, value):
        self.assocation.parent = value

    # Has an arbitrary data payload.
    # data = schema.Column(postgresql.JSONB, default={}, nullable=False)
    data = schema.Column(postgresql.JSON, default={}, nullable=False)

    # Has a `target:action` as string identifiers of the event type, e.g.:
    # `message:created`, `job:confirmed`, etc.
    target = schema.Column(types.Unicode, nullable=False)
    action = schema.Column(types.Unicode, nullable=False)

    # These are exposed and can be managed using `type_`.
    @hybrid.hybrid_property
    def type_(self):
        return u'{0}:{1}'.format(self.target, self.action)

    @type_.setter
    def type_(self, value):
        self.target, self.action = value.split(u':')

    def __json__(self, request=None):
        """Represent the event as a JSON serialisable dict."""

        data = {
            'type': self.class_slug,
            'id': self.id,
            'created_at': self.created.isoformat(),
            'modified_at': self.modified.isoformat(),
            'type': self.type_,
            'data': self.data,
        }
        if self.parent:
            data['parent'] = {
                'type': self.parent.class_slug,
                'id': self.parent.id,
            }
        if self.user:
            data['user'] = {
                'type': self.user.class_slug,
                'id': self.user_id,
            }
        return data




class WorkStatusAssociation(bm.Base, bm.BaseMixin):
    """Polymorphic base that's used to associate a collection of
      ``WorkStatus``s with a parent.
    """

    __tablename__ = 'work_status_associations'
    discriminator = schema.Column(types.Unicode(64))
    __mapper_args__ = {'polymorphic_on': discriminator}


class WorkStatus(bm.Base, bm.BaseMixin):
    """Define the properties provided by a work status entry."""

    # Store in `work_statuses`.
    __tablename__ = 'work_statuses'

    # Must have a string status value
    value = schema.Column(
        types.Unicode(64),
        default=DEFAULT_STATE,
        nullable=False,
    )

    # Can belong to a ``parent`` via a ``WorkStatusAssociation``.
    association_id = schema.Column(
        types.Integer,
        schema.ForeignKey('work_status_associations.id'),
    )
    assocation = orm.relationship(WorkStatusAssociation, backref='work_statuses')

    @property
    def parent(self):
        return self.assocation.parent

    # Can have an event (i.e.: the change to this state was triggered by).
    event_id = schema.Column(
        types.Integer,
        schema.ForeignKey('activity_events.id'),
    )
    event = orm.relationship(
        ActivityEvent,
        backref=orm.backref(
            'work_status',
            lazy='joined',
            single_parent=True,
            uselist=False,
        ),
        lazy='joined',
        uselist=False,
    )

    def __json__(self, request=None):
        data = {
            'type': self.class_slug,
            'id': self.id,
            'value': self.value,
        }
        return data

class ReadStatusAssociation(bm.Base, bm.BaseMixin):
    """Polymorphic base that's used to associate a collection of
      ``ReadStatus``s with a parent.
    """

    __tablename__ = 'read_status_associations'
    discriminator = schema.Column(types.Unicode(64))
    __mapper_args__ = {'polymorphic_on': discriminator}


class ReadStatus(bm.Base, bm.BaseMixin):
    """
    """

    # Store all read statuses in a single table...
    __tablename__ = 'read_statuses'

    # Must have a read value
    read = schema.Column(
        types.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Can belong to a ``parent`` via a ``WorkStatusAssociation``.
    association_id = schema.Column(
        types.Integer,
        schema.ForeignKey('read_status_associations.id'),
    )
    assocation = orm.relationship(ReadStatusAssociation, backref='read_statuses')

    @property
    def parent(self):
        return self.assocation.parent

    # has a user
    user_id = schema.Column(
        types.Integer,
        schema.ForeignKey('auth_users.id'),
    )

    user = orm.relationship(
        simpleauth_model.User,
        backref='read_statuses',
    )

    def __json__(self, request=None):
        data = {
            'type': self.class_slug,
            'id': self.id,
            'read': self.read,
        }
        return data

@zi.implementer(interfaces.IWorkStatus)
class WorkStatusMixin(object):
    """Mixin a collection of work_statuses and activity_events to each target
      ORM class.

      - `activity_events` is a collection of `ActivityEvent` instances
      - `work_statuses` is a collection of `WorkStatusEntry` instances
      - use the `parent.work_status` property to get the most recent entry
      - use `set_work_status(value, event)` to update the work status
    """

    @declarative.declared_attr
    def activity_event_association_id(cls):
        return schema.Column(
            types.Integer,
            schema.ForeignKey('activity_event_associations.id'),
        )

    @declarative.declared_attr
    def activity_event_association(cls):
        """Dynamically defined association table relationship."""

        class_name = '{0}ActivityEventAssociation'.format(cls.__name__)
        bases = (ActivityEventAssociation,)
        mapping = {
            '__mapper_args__': {
                'polymorphic_identity': cls.singular_class_slug,
            }
        }
        association_cls = type(class_name, bases, mapping)
        cls.ActivityEventAssociation = association_cls
        cls.activity_events = proxy.association_proxy(
            'activity_event_association',
            'activity_events',
            creator=lambda x: association_cls(activity_events=x)
        )
        return orm.relationship(
            association_cls,
            backref=orm.backref('parent', uselist=False),
        )

    @declarative.declared_attr
    def work_status_association_id(cls):
        return schema.Column(
            types.Integer,
            schema.ForeignKey('work_status_associations.id'),
        )

    @declarative.declared_attr
    def work_status_association(cls):
        """Dynamically defined association table relationship."""

        class_name = '{0}WorkStatusAssociation'.format(cls.__name__)
        bases = (WorkStatusAssociation,)
        mapping = {
            '__mapper_args__': {
                'polymorphic_identity': cls.singular_class_slug,
            }
        }
        association_cls = type(class_name, bases, mapping)
        cls.WorkStatus = WorkStatus # <!-- just for backwards compatibility
        cls.WorkStatusAssociation = association_cls
        cls.work_statuses = proxy.association_proxy(
            'work_status_association',
            'work_statuses',
            creator=lambda work_statuses: association_cls(work_statuses=work_statuses)
        )
        return orm.relationship(
            association_cls,
            backref=orm.backref('parent', uselist=False),
        )

    @declarative.declared_attr
    def read_status_association_id(cls):
        return schema.Column(
            types.Integer,
            schema.ForeignKey('read_status_associations.id'),
        )

    @declarative.declared_attr
    def read_status_association(cls):
        """Dynamically defined association table relationship."""

        class_name = '{0}ReadStatusAssociation'.format(cls.__name__)
        bases = (ReadStatusAssociation,)
        mapping = {
            '__mapper_args__': {
                'polymorphic_identity': cls.singular_class_slug,
            }
        }
        association_cls = type(class_name, bases, mapping)
        cls.ReadStatus = ReadStatus # <!-- just for backwards compatibility
        cls.ReadStatusAssociation = association_cls
        cls.read_statuses = proxy.association_proxy(
            'read_status_association',
            'read_statuses',
            creator=lambda read_statuses: association_cls(read_statuses=read_statuses)
        )
        return orm.relationship(
            association_cls,
            backref=orm.backref('parent', uselist=False),
        )

    def set_read_status(self, user_id):
        """Append a new read status to the entry list."""

        # Add a new entry to the status collection.
        status = ReadStatus(read=datetime.utcnow(), user_id=user_id)
        if self.read_statuses:
            self.read_statuses.append(status)
        else:
            self.read_statuses = [status]

        # Update timestamps.
        self.modified = datetime.utcnow()

        # Make sure everything gets saved.
        bm.Session.add_all([self, status])
        bm.Session.flush()

        # Return the new status instance.
        return status


    def get_read_status(self, user_id):
        """Return the read status for a user"""

        query = ReadStatus.query
        query = query.filter_by(association_id=self.read_status_association_id)
        query = query.filter_by(user_id=user_id)
        query = query.order_by(ReadStatus.created.desc())
        return query.first()


    def set_work_status(self, value, event=None, model_cls=WorkStatus):
        """Append a new work status to the entry list."""

        # Make sure we're not detatched o_O.
        bm.Session.add(self)

        # Add a new entry to the status collection.
        status = model_cls(value=value, event=event)
        if self.work_statuses:
            self.work_statuses.append(status)
        else:
            self.work_statuses = [status]

        # Update timestamps.
        self.modified = datetime.utcnow()

        # Make sure everything gets saved.
        bm.Session.add_all([self, status])
        bm.Session.flush()

        # Return the new status instance.
        return status


    def get_work_status(self, value=None, model_cls=WorkStatus):
        """Return the most recent work status, optionally filtered by value."""

        query = model_cls.query
        query = query.filter_by(association_id=self.work_status_association_id)
        if value is not None:
            query = query.filter_by(value=value)
        query = query.order_by(model_cls.created.desc())
        return query.first()


    @property
    def work_status(self):
        return self.get_work_status()
