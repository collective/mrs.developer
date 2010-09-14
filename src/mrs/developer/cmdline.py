
import os
import sys
import json
import ConfigParser
import pprint

#from mrs.developer.core import ConfigNode
#from mrs.developer.buildout import BuildoutNode

from mrs.developer.utils import logger
from mrs.developer.utils import load_config
from mrs.developer.utils import save_config
from mrs.developer.utils import DEFAULT_CONFIG
from mrs.developer.node import LazyNode






class InitBuildoutNode(LazyNode):

    def __call__(self):
        if not os.path.exists('.installed.cfg'):
            return # FIXME: maybe i should raise error

        config = self.root._config
        config.setdefault('buildout', {'parts': {}, 'eggs': {}, 'sources': {}})

        # read sources
        cp = ConfigParser.ConfigParser()
        self.extend(cp, 'sources.cfg')
        if cp.has_section('buildout') and \
           cp.has_option('buildout', 'sources'):
            sources = cp._sections[cp._sections['buildout']['sources']]
            sources.pop('__name__')
            self.root._config['buildout']['sources'] = sources

        # read parts, fill eggs and list scripts per part
        cp = ConfigParser.ConfigParser()
        cp.read('.installed.cfg')
        import ipdb; ipdb.set_trace()
        for part in cp._sections['buildout']['parts'].split():
            if cp.has_option(part, '__buildout_installed__'):
                for file_ in cp._sections[part]['__buildout_installed__'].split():
                    self.hookin(file_)
                    self.root._config['buildout']['parts'].setdefault(part, {})


        save_config(config)

    def hookin(self, path):
        pass
    def extend(self, cp, cp_file):
        cp2 = ConfigParser.ConfigParser()
        cp2.read(cp_file)
        if cp2.has_section('buildout') and \
           cp2.has_option('buildout', 'extends'):
            for file_ in cp2._sections['buildout']['extends'].split():
                self.extend(cp, file_)
        cp.read(cp_file)







class CommandError(Exception):
    pass


class Cmd(LazyNode):

    def __getitem__(self, key):
        if not self._subnodes or key not in self._subnodes:
            raise CommandError("Node/Command not implemented.")
        if type(self._subnodes[key]) == dict:
            class WrappedCmd(Cmd):
                _subnodes = self._subnodes[key]
            self._subnodes[key] = WrappedCmd(key)
        item = super(Cmd, self).__getitem__(key)
        item.__name__ = key
        return item

    def __call__(self, args=None):
        default_cmd = self._subnodes.get('__default__', None)
        if default_cmd is None:
            raise CommandError("Command not implemented.")
        return getattr(self, default_cmd)(args)

    def __repr__(self):
        return "%s for '%s'" % (self.__class__, ' '.join(self.path))


def simple_cmd(cmd):
    class SimpleCmd(Cmd):
        __call__ = cmd
    return SimpleCmd()


def config_add(node, args=None):
    config = node.root._config
    if config is None:
        raise CommandError('Mrsd not rooted.')
    if not args or len(args) != 2:
        raise CommandError('Please provide config name and value as parameters.')
    config = config['config']
    if args[0] not in config:
        config[args[0]] = args[1]
        save_config(node.root._config)
        return call_cmd(node.root, ['config'])
    else:
        raise CommandError('Configuration with key "' + args[0] + \
                            '" already exists. Aborting...')


def config_edit(node, args=None):
    config = node.root._config
    if config is None:
        raise CommandError('Mrsd not rooted.')
    if not args or len(args) != 2:
        raise CommandError('Please provide config name and value as parameters.')
    config = config['config']
    if args[0] in config:
        config[args[0]] = args[1]
        save_config(node.root._config)
        return call_cmd(node.root, ['config'])
    else:
        raise CommandError('Configuration with key "' + args[0] + \
                            '" not existing. Aborting...')


def config_list(node, args=None):
    config = node.root._config
    if config is None:
        raise CommandError('Mrsd not rooted.')
    return json.dumps(config['config'], indent=4)


def config_remove(node, args=None):
    config = node.root._config
    if config is None:
        raise CommandError('Mrsd not rooted.')
    if not args or len(args) != 1:
        raise CommandError('Please provide config key as parameter.')
    config = config['config']
    if args[0] in config:
        del config[args[0]]
        save_config(node.root._config)
        return call_cmd(node.root, ['config'])
    else:
        raise CommandError('Configuration with key "' + args[0] + \
                            '" not existing. Aborting...')


def core_help(node, args=None):
    return 'Available commands: %s' % ', '.join([
        x for x in node.root._subnodes.keys()
            if x != '__default__'])


def core_init(node, args=None):
    mode = 'buildout' # TODO: this should be passed as argument
    if node.root._config is not None:
        return 'mrsd already rooted.'
    else:
        config = DEFAULT_CONFIG['default'][1]
        if mode in DEFAULT_CONFIG:
            f = open(DEFAULT_CONFIG[mode][0], 'w+')
            f.write(json.dumps(DEFAULT_CONFIG[mode][1], indent=4))
            f.close()
            config.setdefault('extends', [])
            config['extends'].append(DEFAULT_CONFIG[mode][0])

        f = open(DEFAULT_CONFIG['default'][0], 'w+')
        f.write(json.dumps(config, indent=4))
        f.close()

    #if mode == 'buildout':
    #    ['buildout']['init']()

    return 'mrsd rooted.'


COMMANDS = dict(
    __default__ = 'help',
    init = simple_cmd(core_init),
    help = simple_cmd(core_help),
    config = dict(
            __default__ = 'list',
            add = simple_cmd(config_add),
            edit = simple_cmd(config_edit),
            list = simple_cmd(config_list),
            remove = simple_cmd(config_remove),
        ),
)


def call_cmd(node, arg):
    if len(arg) == 0:
        return node()
    # FIXME: this should be done better in Cmd
    subnode = None
    try:
        subnode = getattr(node, arg[0], None)
    except CommandError:
        pass
    if subnode is None:
        return node(arg)
    return call_cmd(subnode, arg[1:])


def main():
    root = Cmd(sys.argv[0])
    root._subnodes = COMMANDS
    root._config = load_config()
    result = ''
    try:
        result = call_cmd(root, sys.argv[1:])
    except CommandError, e:
        print(e)
    else:
        # XXX: not really sure what to do with result
        #      for now i will just print it
        print(result)


if __name__ == "__main__":
    main()
