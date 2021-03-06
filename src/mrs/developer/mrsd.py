#!/usr/bin/env python

import os
import shutil
from subprocess import PIPE
from subprocess import Popen
try:
    import json
except ImportError:
    import simplejson as json

from odict import odict
from pkg_resources import iter_entry_points

from mrs.developer.base import Cmd
from mrs.developer.base import CmdWrapper
from mrs.developer.base import check_call
from mrs.developer.base import logger

import mrs.developer.distributions

DEFAULT_CFG_FILE = '.mrsd'


class Init(Cmd):
    """Create a default configuration in the current directory.

    This defines a mrsd root, commands in the subtree will find and use it.
    """
    def __call__(self, path=None, pargs=None):
        cfg_file = os.path.abspath(DEFAULT_CFG_FILE)
        reinit = os.path.isfile(cfg_file)
        self.cmds.save_config(cfg_file)
        if reinit:
            logger.info(u"Reinitialized mrsd root at %s." % \
                    (os.path.abspath(os.curdir)))
        else:
            logger.info(u"Initialized mrsd root at %s." % \
                    (os.path.abspath(os.curdir)))


class HookCmd(Cmd):
    start_indicator = '\n### mrs.developer'
    stop_indicator = '### mrs.developer: end.\n'

    def _initialize(self):
        self.cfg.setdefault('scripts_dir', 'bin')

    def __call__(self, pargs=None):
        """If no arguments are specified, we hook into all known scripts

        except buildout and mrsd
        """
        scriptdir = os.path.join(
                self.root or os.curdir,
                self.cfg['scripts_dir']
                )
        for name in os.listdir(scriptdir):
            script = os.path.join(scriptdir, name)
            if name in ('buildout', 'mrsd'):
                logger.debug("Ignoring %s." % (script,))
                continue
            if name[0] == '.':
                logger.debug("Ignoring %s." % (script,))
                continue
            # Will be either hookin or hookout
            self._cmd(script)


class Hookin(HookCmd):
    """Hook into a script's sys.path generation, renew if hooked already.
    """
    start_str = 'sys.path[0:0] = ['

    hook = \
"""%s: inject our paths upfront
try:
    import json
except ImportError:
    import simplejson as json
import subprocess

try:
    mrsdpaths = subprocess.Popen(
           ["./bin/mrsd", "list", "cloned"],
           stdout=subprocess.PIPE,
           ).communicate()[0]
except OSError:
    try:
        mrsdpaths = subprocess.Popen(
               ["mrsd", "list", "cloned"],
               stdout=subprocess.PIPE,
               ).communicate()[0]
    except OSError:
        import os
        print "Please make mrsd available in ./bin/ or anywhere in your PATH:"
        print os.environ['PATH']
        sys.exit(1)
if mrsdpaths:
    sys.path[0:0] = json.loads(mrsdpaths).values()
%s"""

    def _hookin(self, script):
        """This command will be called by HookCmd.__call__
        """
        f = open(script, 'r')
        content = f.read()
        f.close()
        if self.start_indicator in content:
            self.cmds.hookout()
            f = open(script, 'r')
            content = f.read()
            f.close()
        if self.start_str not in content:
            logger.debug("Not hooking into %s." % (script,))
            return
        idx = content.find(self.start_str) + len(self.start_str)
        idx = content.find(']', idx)+2
        hooked = content[:idx]
        hooked += self.hook % \
                (self.start_indicator, self.stop_indicator)
        hooked += content[idx:]
        f = open(script, 'w')
        f.write(hooked)
        f.close()
        logger.info("Hooked in: %s." % (script,))

    _cmd = _hookin


class Hookout(HookCmd):
    """Remove our hook from scripts.
    """
    def _hookout(self, script):
        """This command will be called by HookCmd.__call__
        """
        f = open(script, 'r')
        content = f.read()
        f.close()
        if not self.start_indicator in content:
            return
        start = content.find(self.start_indicator)
        stop = content.rfind(self.stop_indicator) + len(self.stop_indicator)
        content = content[:start] + content[stop:]
        f = open(script, 'w')
        f.write(content)
        f.close()
        logger.info("Hooked out: %s." % (script,))

    _cmd = _hookout


class Test(CmdWrapper):
    """Run the tests, from anywhere in your project, without the need to know
    where your testrunner lives.
    """
    cmdline = ["./bin/test"]


class Run(CmdWrapper):
    """Run scripts from ``bin/`` from anywhere in your project.
    """
    def _cmdline(self, args):
        cmd = args.pop(0)
        cmd = os.path.join('.', 'bin/', cmd)
        return [cmd] + args


class DotDotSources(Cmd):
    """DotDotSources, assumes all sources listed in buildout are available in
    the parent directory and injects them before all other develop eggs.

    XXX: temporary cmd with stupid name in need for proper sources management.
    """
    def _initialize(self):
        self.cfg.setdefault('dotdotsources', False)
        self.cmds.save_config()

    def init_argparser(self, parser):
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument(
                '--status',
                dest='action',
                action='store_const',
                const=self.status,
                help=self.status.__doc__,
                )
        actions.add_argument(
                '--toggle',
                dest='action',
                action='store_const',
                const=self.toggle,
                help=self.toggle.__doc__,
                )
        parser.set_defaults(action=self.status)

    def status(self):
        """Show status of dotdotsources
        """
        return self.cfg['dotdotsources']

    def toggle(self):
        """Toggle status of dotdotsources
        """
        self.cfg['dotdotsources'] = not self.cfg['dotdotsources']
        self.cmds.save_config()
        return self.cfg['dotdotsources']

    def __call__(self, pargs=None):
        return pargs.action()


class CmdSet(object):
    """The mrsd command set.
    """

    entry_point_keys = {
        'commands': 'mrs.developer.commands',
        'aliases': 'mrs.developer.aliases'
    }

    @property
    def root(self):
        try:
            return os.path.dirname(self.cfg_file)
        except AttributeError:
            return None

    def __init__(self):
        self.cfg = dict()
        self.cfg_file = self._find_cfg()
        self.load_config()
        self.cmds = odict()
        self.aliases = odict()
        for ep in iter_entry_points(self.entry_point_keys['commands']):
            self.cmds[ep.name] = ep.load()(ep.name, self)
        for ep in iter_entry_points(self.entry_point_keys['aliases']):
            self.aliases[ep.name] = ep.load()()
        self.cmds.sort()
        self.aliases.sort()

    def _find_cfg(self, cfg_file=os.path.abspath(DEFAULT_CFG_FILE)):
        if os.path.isfile(cfg_file):
            return cfg_file
        # check in parent dir
        head, tail = os.path.split(cfg_file)
        pardir = os.path.dirname(head)
        if head == pardir:
            logger.info('Running rootless, ``mrsd init`` would define a root.')
            return None
        return self._find_cfg(os.path.join(pardir, tail))

    def __getattr__(self, name):
        try:
            cmds = object.__getattribute__(self, 'cmds')
        except AttributeError:
            return object.__getattribute__(self, name)
        if name in cmds:
            return cmds[name]

    def __getitem__(self, name):
        return self.cmds[name]

    def __iter__(self):
        return self.cmds.__iter__()

    def iteritems(self):
        return self.cmds.iteritems()

    def load_config(self):
        """Load config from curdir or parents
        """
        if self.cfg_file is None:
            logger.debug("No config to load, we are rootless.")
            return
        logger.debug("Trying to load config from %s." % (self.cfg_file,))
        f = open(self.cfg_file)
        self.cfg = json.load(f)
        logger.debug("Loaded config from %s." % (self.cfg_file,))
        f.close()

    def save_config(self, cfg_file=None):
        cfg_file = cfg_file or self.cfg_file
        cfg_file = os.path.abspath(cfg_file)
        f = open(cfg_file, 'w')
        json.dump(self.cfg, f, indent=4, sort_keys=True)
        f.close()
        logger.debug("Wrote config to %s." % (cfg_file,))
