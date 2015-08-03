# -*- coding: utf-8 -*-

"""Provides an dummy model for ftesting."""

__all__ = [
    'IModel', 'IFoo', 'IBar',
    'Model', 'Foo', 'Bar'
]

import zope.interface as zi
import pyramid_basemodel as bm

from pyramid_torque_engine import orm

class IModel(zi.Interface):
    pass

class IFoo(IModel):
    pass

class IBar(IModel):
    pass

@zi.implementer(IModel)
class Model(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'models'

@zi.implementer(IFoo)
class Foo(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'foos'

@zi.implementer(IBar)
class Bar(bm.Base, bm.BaseMixin, orm.WorkStatusMixin):
    __tablename__ = 'bars'

def factory(cls, initial_state=orm.DEFAULT_STATE):
    instance = cls()
    instance.set_work_status(initial_state)
    bm.Session.add(instance)
    bm.Session.flush()
    return instance
