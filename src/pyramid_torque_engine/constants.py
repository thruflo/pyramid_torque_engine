# -*- coding: utf-8 -*-

from . import util as _util

ASTERIX = '*'

# Registration "constants" -- open to being populated during configuration,
# closed afterwards in the `includeme` function below.
ACTIONS = _util.DeclaredNamespacedNamedTuple(u'Action')
OPERATIONS = _util.DeclaredNamespacedNamedTuple(u'Operation')
RESULTS = _util.DeclaredNamespacedNamedTuple(u'Result')
STATES = _util.DeclaredNamespacedNamedTuple(u'State')
STATES.register('CREATED')

# Environment variable names.
ENGINE_API_KEY = 'ENGINE_API_KEY'
ENGINE_URL = 'ENGINE_URL'
TORQUE_API_KEY = 'TORQUE_API_KEY'
TORQUE_URL = 'TORQUE_URL'
WEBHOOKS_API_KEY = 'WEBHOOKS_API_KEY'
WEBHOOKS_URL = 'WEBHOOKS_URL'

# Legacy environment variable names -- to be depreciated.
LEGACY_ENGINE_API_KEY = 'WORKFLOW_ENGINE_API_KEY'
LEGACY_ENGINE_URL = 'WORKFLOW_ENGINE_URL'
LEGACY_WEBHOOKS_API_KEY = 'FABBED_HOOKS_API_KEY'
LEGACY_WEBHOOKS_URL = 'FABBED_HOOKS_URL'

# Group the names so we can check them in order.
ENGINE_API_KEY_NAMES = (ENGINE_API_KEY, LEGACY_ENGINE_API_KEY)
ENGINE_URL_NAMES = (ENGINE_URL, LEGACY_ENGINE_URL)
WEBHOOKS_API_KEY_NAMES = (WEBHOOKS_API_KEY, LEGACY_WEBHOOKS_API_KEY)
WEBHOOKS_URL_NAMES = (WEBHOOKS_URL, LEGACY_WEBHOOKS_URL)
