import winnow

DEFAULTS = {
    "sqlalchemy.json_serializer" : winnow.utils.json_dumps,
    "sqlalchemy.json_deserializer" : winnow.utils.json_loads
}

def includeme(config):
    settings = config.get_settings()
    for key, value in DEFAULTS.items():
        settings.setdefault(key, value)

