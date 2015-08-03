# -*- coding: utf-8 -*-

"""Test settings, overridable by env var."""

__all__ = [
    'TEST_SETTINGS',
]

import os

TEST_SETTINGS = {
    'mode': 'testing',
    'basemodel.should_bind_engine': False,
    'sqlalchemy.url': os.environ.get(
        'DATABASE_URL',
        'postgresql:///torque_engine_test'
    ),
    'handle_exceptions': os.environ.get(
        'HANDLE_EXCEPTIONS',
        False
    ),
    'engine.url': 'http://localhost/engine',
    'torque.url': 'http://localhost/ntorque',
    'webhooks.url': 'http://localhost/hooks',
}
