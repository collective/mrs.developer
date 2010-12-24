import os
import subprocess

from mrs.developer.mrsd import CmdSet


MRSD_PART_ID = '_mrs.developer'


class Extension(object):
    """Super-class for LoadExtension and UnloadExtension

    Load the mrsd command set, stores reference to buildout.
    """
    def __init__(self, buildout=None):
        self.buildout = buildout
        self.cmdset = CmdSet()


class LoadExtension(Extension):
    """Will inject mrsd develop eggs, if buildout is run

    By this we enable changes to setup.py being picked up:
      - entry-points
      - requires

    This is currently not possible with simple customized eggs, as buildout
    does not know about them.
    """
    def __call__(self):
        # some wrangling to get a config file and have it loaded
        self.cmdset.cmds['init']()
        self.cmdset.cfg_file = self.cmdset._find_cfg()
        self.cmdset.load_config()
        if not self.mrsd_in_path():
            self.add_mrsd_part()
        #XXX: currently not used: self.dumpbuildoutinfo()
        self.dotdotsources()
        self.cmdset.save_config()
        return
        develop = self.buildout['buildout']['develop']
        ours = self.cmdset.cfg['develop'].values()
        self.buildout['buildout']['develop'] = str("\n".join([develop] + ours))

    def mrsd_in_path(self):
        try:
            return subprocess.call(['mrsd', 'dance']) == 17
        except (OSError, subprocess.CalledProcessError):
            return False
        else:
            return True

    def add_mrsd_part(self):
        if MRSD_PART_ID in self.buildout._raw:
            logger.error("The buildout already has a '%s' section, "
                         "this shouldn't happen" % MRSD_PART_ID)
            sys.exit(1)
        self.buildout._raw[MRSD_PART_ID] = dict(
            recipe='zc.recipe.egg',
            eggs='mrs.developer',
        )
        # insert the fake part
        parts = self.buildout['buildout']['parts'].split()
        parts.insert(0, MRSD_PART_ID)
        self.buildout['buildout']['parts'] = " ".join(parts)

    def dumpbuildoutinfo(self):
        # XXX: we always just override, next would be to save it for each run,
        # but probably only for things we want to know, like scm revisions.
        bo = self.cmdset.cfg['buildout'] = {}
        bo['sources'] = {}
        bo['sources'].update(self.buildout['sources'])
        bo['auto-checkout'] = self.buildout['buildout']['auto-checkout'].split()

    def dotdotsources(self):
        if not self.cmdset.cfg['dotdotsources']:
            return
        for src in self.buildout['sources']:
            dev = self.buildout['buildout']['develop']
            src = os.path.join(os.pardir, src)
            self.buildout['buildout']['develop'] = ' '.join((dev, src))


class UnloadExtension(Extension):
    """Called after config is parsed
    """
    def __call__(self):
        self.cmdset.load_config()
        self.cmdset.cmds['hookin']()
        self.cmdset.cmds['reload']._configure(self.buildout)
        self.cmdset.save_config()


def load(buildout=None):
    return LoadExtension(buildout)()


def unload(buildout=None):
    return UnloadExtension(buildout)()

