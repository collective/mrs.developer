try:
    import cmd2 as cmd
except:
    import cmd

import os
import sys
import json
import ConfigParser

#from mrs.developer.core import ConfigNode
#from mrs.developer.buildout import BuildoutNode

from mrs.developer.utils import logger
from mrs.developer.utils import load_config
from mrs.developer.utils import save_config
from mrs.developer.utils import DEFAULT_CONFIG
from mrs.developer.node import LazyNode


class TraverseCommandNode(LazyNode):

    _subcommands = {}
    _params = None

    def __init__(self, name=None):
        if name:
            name_list = name.split()
            name = name_list[0]
            self._params = name_list[1:]
        super(TraverseCommandNode, self).__init__(name)
        self._keys = {}

    def _lazyload_keys(self):
        return self._subcommands.keys()

    def _lazyload_child(self, key):
        return self._get_subcommand(key)

    def __getitem__(self, key):
        node = self._get_subcommand(key)
        node.__parent__ = self
        return node

    def _get_subcommand(self, command):
        subcommand = command.split(' ')[0]
        if subcommand in self._subcommands:
            return self._subcommands[subcommand](
                            ' '.join(command[1:].split()))


class RemoveNode(TraverseCommandNode):

    def __call__(self):
        config = self.root._config
        for key in self.path.split('/')[1:-1]:
            config = config[key]
        if self._params[0] in config:
            del config[self._params[0]]
            save_config(self.root._config)
            return self.__parent__['list']()
        else:
            raise Exception('Configuration with key "' + self._params[0] + \
                            '" not existing. Aborting...')


class AddNode(TraverseCommandNode):

    def __call__(self):
        config = self.root._config
        for key in self.path.split('/')[1:-1]:
            config = config[key]
        if self._params[0] not in config:
            config[self._params[0]] = self._params[1]
            save_config(self.root._config)
            return self.__parent__['list']()
        else:
            raise Exception('Configuration with key "' + self._params[0] + \
                            '" already existing. Aborting...')


class EditNode(TraverseCommandNode):

    def __call__(self):
        # TODO: how to accept data, for now like,
        #       % mrsd config edit <name> <value>"
        config = self.root._config
        for key in self.path.split('/')[1:-1]:
            config = config[key]
        if self._params[0] in config:
            config[self._params[0]] = self._params[1]
            save_config(self.root._config)
            return self.__parent__['list']()
        else:
            raise Exception('Configuration with key "' + self._params[0] + \
                            '" not existing. Aborting...')


class ListNode(TraverseCommandNode):

    def __call__(self):
        config = self.root._config
        for key in self.path.split('/')[1:-1]:
            config = config[key]
        return json.dumps(config, indent=4)

class ConfigNode(TraverseCommandNode):

    _subcommands = {
        'list':     ListNode,
        'edit':     EditNode,
        'add':      AddNode,
        'remove':   RemoveNode,
    }

    def __call__(self):
        return self._subcommands('list')()

class InitBuildoutNode(TraverseCommandNode):

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

    def hookin(self, path)
    def extend(self, cp, cp_file):
        cp2 = ConfigParser.ConfigParser()
        cp2.read(cp_file)
        if cp2.has_section('buildout') and \
           cp2.has_option('buildout', 'extends'):
            for file_ in cp2._sections['buildout']['extends'].split():
                self.extend(cp, file_)
        cp.read(cp_file)


class BuildoutNode(TraverseCommandNode):

    _subcommands = {
        'init':     InitBuildoutNode,
    }


class InitNode(TraverseCommandNode):

    def __call__(self):
        """Create a default configuration in the current directory.
        """
        mode = 'buildout' # TODO: this should be passed as argument
        if self.root._config is not None:
            logger.error('mrsd already rooted.')
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
            logger.info('mrsd rooted.')

        if mode == 'buildout':
            self.root['buildout']['init']()

        return ''

class RootNode(TraverseCommandNode):

    _subcommands = {
        'init':     InitNode,
        'list':     ListNode,
        'config':   ConfigNode,
        'buildout': BuildoutNode,
    }


class App(cmd.Cmd):
    """
    """

    def __init__(self, name=None):
        """Load config and make root nodes avaliable as commands
        """
        self._root = RootNode()
        self._root._config = load_config()

        # make root nodes avaliable as commands
        for key in self._root._subcommands.keys():
            node = self._root[key]
            setattr(self, 'do_'+key, self._do_wrap(node))

        cmd.Cmd.__init__(self)

    def _do_wrap(self, node):
        class Wrapped(object):
            def __init__(self, node):
                self.node = node
            def __call__(self, arg):
                if arg:
                    try:
                        node = self.node[arg]
                    except:
                        raise Exception('Command have wrong parameters: ' + arg)
                    print node()
                else:
                    print self.node()
        return Wrapped(node)

    def do_interactive(self, arg):
        pass


def main():
    """
    """
    app = App()
    if len(sys.argv) == 1:
        sys.argv += ['--help', 'quit']
    elif sys.argv[1] != 'interactive':
        sys.argv = [sys.argv[0], ' '.join(sys.argv[1:]), 'quit']
    app.cmdloop()

if __name__ == "__main__":
    main()
