
import os
import json
import logging


logger = logging.getLogger("mrsd")

DEFAULT_CONFIG = {
    'default': ('.mrsd', {
        'extends': [],
        'config': {
            'default-buildout-eggs-dir': 'mrsd-eggs/',
            'default-buildout-sources-dir': 'mrsd-src/',
            'default-patches-dir': 'mrsd-patches/',
        },
    }),
    'buildout': ('.mrsd-buildout', {
        'buildout': {},
    }),
}


def resolve_config_path(config_file):
    config_file = os.path.abspath(config_file)
    logger.debug("Trying to load config from %s." % (config_file,))
    if os.path.isfile(config_file):
        try:
            f = open(config_file)
            config = f.read()
            f.close()
            return config, config_file
        except IOError:
            pass
    # check in parent dir
    head, tail = os.path.split(config_file)
    pardir = os.path.dirname(head)
    if head != pardir:
        config_file = os.path.join(pardir, tail)
        return resolve_config_path(config_file)


def save_config(new_config):
    config, config_file = resolve_config_path(DEFAULT_CONFIG['default'][0])
    config = json.loads(config)

    config = update_config(config, config_file, new_config)

def update_config(config, config_file, new_config):
    for key in config:
        if 'extends' == key:
            continue
        if key in new_config:
            config[key] = new_config[key]

    f = open(config_file, 'w')
    try:
        f.write(json.dumps(config, indent=4))
    except:
        import ipdb; ipdb.set_trace()
    f.close()

    if config and 'extends' in config:
        for extended_config_file in config['extends']:
            if not os.path.isabs(extended_config_file):
                extended_config_file = os.path.join(
                        os.path.dirname(config_file), extended_config_file)
            extended_config, extended_config_file = \
                        resolve_config_path(extended_config_file)
            extended_config = json.loads(extended_config)
            update_config(extended_config, extended_config_file, new_config)


def update_with_extended_config(config, config_file):
    if config and 'extends' in config:
        for extended_config_file in config['extends']:
            if not os.path.isabs(extended_config_file):
                extended_config_file = os.path.join(
                        os.path.dirname(config_file), extended_config_file)
            extended_config, extended_config_file = \
                        resolve_config_path(extended_config_file)
            try:
                if not os.path.isfile(extended_config_file):
                    raise
                f = open(extended_config_file)
                extended_config = f.read()
                f.close()
            except:
                logger.debug("Failed extending to: %s." % \
                             (extended_config_file,))
            extended_config = json.loads(extended_config)
            extended_config = update_with_extended_config(extended_config,
                                                          extended_config_file)
            if extended_config is None:
                continue
            extended_config.update(config)
            config = extended_config
            logger.debug("Loaded config from %s." % (extended_config_file,))
        del config['extends']
    return config


def load_config(config_file=DEFAULT_CONFIG['default'][0]):
    """Load config from curdir or parents
    """
    resolved = resolve_config_path(config_file)
    if resolved is None:
        return resolved
    config, config_file = json.loads(resolved[0]), resolved[1]
    logger.debug("Loaded config from %s." % (config_file,))
    return update_with_extended_config(config, config_file)
