
* the hook dispatched uses `from winnow.utils import json_dumps`
  ^ really there's no need to be directly serialising the data
    in the dispatcher -- better to delegate to the registered
    utilities?

* the activity event class has a relationship to a user table -- this needs
  to be patched onto the class post settings but pre basemodel config.commit

* replace the tree boilerplate with a "register_traversable_resource"
  directive that naturally handles traversal

* `'workflow_engine.url': os.environ.get('WORKFLOW_ENGINE_URL', '/engine'),`
  `'workflow_engine.api_key': os.environ.get('WORKFLOW_ENGINE_API_KEY', None),`
  ^ these should be renamed `torque_engine.*` and should look *first* in the
  `TORQUE_ENGINE_*` env vars, falling back on the `WORKFLOW_ENGINE_*` for
  backwards compatibility

* port the whole client and make sure the client is includable seperately
