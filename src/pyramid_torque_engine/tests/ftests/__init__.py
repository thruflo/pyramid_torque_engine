# -*- coding: utf-8 -*-

"""This package contains functional tests that use webtest.TestApp to simulate
  requests to a minimal WSGI app that uses the work engine.

  This requires the WSGI app to be setup, which requires the database to be
  setup. This takes time (largely because of the tables and relations we inherit
  from fabhub). So... in order to make the tests run reasonablly fast we:

  * create a fresh db once per test run
  * create the necessary db tables in the test setup_class method
  * run tests within a setup:begin teardown:rollback transaction
"""

import os

from sqlalchemy import engine_from_config

from pyramid_basemodel import Base
from pyramid_basemodel import Session

from . import settings

# Only run this setup once, even if running tests in parallel.
_multiprocess_shared_ = True

def setup():
    """Drop and recreate a vanilla db."""

    test_settings = settings.TEST_SETTINGS
    db_url = test_settings['sqlalchemy.url']
    db_name = db_url.split('/')[-1]
    os.system('dropdb {0}'.format(db_name))
    os.system('createdb -T template0 -E UTF8 {0}'.format(db_name))

    engine = engine_from_config(test_settings, prefix='sqlalchemy.')
    Base.metadata.create_all(engine)
