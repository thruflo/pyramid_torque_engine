# -*- coding: utf-8 -*-

"""Provides an dummy model for ftesting."""

import transaction as tx
import zope.interface as zi

import pyramid_basemodel as bm

from pyramid_torque_engine import orm

class IModel(zi.Interface):
    pass

class IContainer(zi.Interface):
    pass

class IFoo(IModel):
    pass

class IFooContainer(IContainer):
    pass

class IBar(IModel):
    pass

class IBarContainer(IContainer):
    pass

@zi.implementer(IModel)
class Model(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'models'

    def __json__(self, request=None):
        return {}

@zi.implementer(IFoo)
class Foo(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'foos'

    def __json__(self, request=None):
        return {}

@zi.implementer(IBar)
class Bar(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'bars'

    def __json__(self, request=None):
        return {}

def factory(cls=Model, initial_state=orm.DEFAULT_STATE, **kwargs):
    with tx.manager:
        instance = cls(**kwargs)
        instance.set_work_status(initial_state)
        bm.Session.add(instance)
        bm.Session.flush()
        instance_id = instance.id
    return cls.query.get(instance_id)
