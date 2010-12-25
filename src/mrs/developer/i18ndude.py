from mrs.developer.base import Cmd, check_call
import os
import subprocess


class I18ndude(Cmd):
    """Updated locales using `i18ndude`.
    """

    def init_argparser(self, parser):
        """Configure argument parser. Run this command with a package.
        You can put a foo.bar-manual.pot in your locales directory which
        will be merged into your regular foo.bar.pot when running with
        --build.
        """

        mutual = parser.add_mutually_exclusive_group(required=True)
        mutual.add_argument(
            '--build', '-b',
            dest='build',
            action='store_true',
            help='Build .pot-file.')

        mutual.add_argument(
            '--sync', '-s',
            dest='sync',
            action='store_true',
            help='Sync .po-files with .pot-file.')

        # # other arguments
        parser.add_argument(
            '--domain', '-d',
            dest='domain',
            action='store',
            default=self.get_default_domain(),
            help='i18n domain to build or sync.')

        parser.add_argument(
            '--languages', '-l',
            dest='languages',
            action='store',
            default=self.get_default_languages(),
            help='Languages to sync with.')

    def __call__(self, dists=None, pargs=None):
        pkgname, pkgdir = self.find_pkg_name_and_directory()
        i18ndude = self.find_executable('i18ndude')
        locales_dir = self.get_locales_dir()

        potfile = os.path.join(locales_dir, '%s.pot' % pargs.domain)

        if pargs.build:
            # build pot files
            cmd = [i18ndude, 'rebuild-pot', '--pot', potfile]
            manual_potfile = self.get_manual_potfile(pargs.domain)
            if manual_potfile:
                cmd.extend(('--merge', manual_potfile))
            cmd.extend(('--create', pargs.domain))
            cmd.append(pkgdir)
            check_call(cmd)

        elif pargs.sync:
            # sync po files
            for lang in pargs.languages.split(','):
                lang = lang.strip()
                pofile = os.path.join(locales_dir, lang, 'LC_MESSAGES',
                                      '%s.po' % pargs.domain)
                # create the directory, if needed
                if not os.path.isfile(pofile):
                    dir = os.path.dirname(pofile)
                    if not os.path.isdir(dir):
                        check_call(('mkdir', '-p', dir))
                    # touch the file, if needed
                    open(pofile, 'w').close()
                cmd = [i18ndude, 'sync', '--pot', potfile, pofile]
                check_call(cmd)

    def get_default_domain(self):
        pkgname, path = self.find_pkg_name_and_directory()
        return pkgname

    def get_default_languages(self):
        """The default languages are the languages which are already existing
        for the default domain.
        """
        domain = self.get_default_domain()
        locales_dir = self.get_locales_dir()
        languages = []

        if not os.path.isdir(locales_dir):
            return 'en'

        for dir in os.listdir(locales_dir):
            if os.path.isdir(os.path.join(locales_dir, dir)):
                if os.path.isfile(os.path.join(
                        locales_dir, dir, 'LC_MESSAGES', '%s.po' % domain)):
                    languages.append(dir)
        return ','.join(languages)

    def get_manual_potfile(self, domain):
        """Returns the path to the manual potfile or None if there
        is none.
        """
        locales_dir = self.get_locales_dir()
        path = os.path.join(locales_dir, '%s-manual.pot' % domain)
        if os.path.isfile(path):
            return path
        else:
            return None

    def get_locales_dir(self):
        """Returns the path to the locales dir - even if it's not existing yet.
        """
        pkgname, path = self.find_pkg_name_and_directory()
        return os.path.join(path, 'locales')

    def find_pkg_name_and_directory(self):
        """Returns the package name (e.g. foo.bar) and the path to the
        namespace directory (e.g. .../src/foo.bar/foo/bar
        or .../src/foo.bar/src/foo/bar).
        """

        if hasattr(self, '_pkg_name_and_directory'):
            return self._pkg_name_and_directory

        # find the egg-info directory by walking up
        egginfo = None
        path = os.getcwd()
        while path != '/':
            dirs = filter(lambda f: os.path.isdir(os.path.join(path, f)) and \
                              f.endswith('.egg-info'),
                          os.listdir(path))

            if len(dirs) > 1:
                RuntimeError('Found multiple *.egg-info directories in %s' % \
                                 path)

            elif len(dirs) == 1:
                egginfo = os.path.join(path, dirs[0])
                break

            else:
                path, foo = os.path.split(path)
                if not path or path == '/':
                    RuntimeError('Couldn\'t find any *.egg-info directory.')

        # read the PKG-INFO file in the egg-info directory
        pkginfo = os.path.join(egginfo, 'PKG-INFO')
        if not os.path.isfile(pkginfo):
            RuntimeError('Couldn\'t find file %s' % pkginfo)

        data = open(pkginfo).read().split('\n')
        pkgname = None
        for row in data:
            if row.startswith('Name:'):
                pkgname = row.split(':', 1)[1].strip()
                break

        # guess the namespace directory name
        path, foo = os.path.split(egginfo)
        path = os.path.join(path, *pkgname.split('.'))
        if not os.path.isdir(path):
            RuntimeError('Package layout not supported: expected ' + \
                             '%s to be a directory.' % path)

        self._pkg_name_and_directory = pkgname, path
        return self._pkg_name_and_directory

    def find_executable(self, name='i18ndude'):
        """Finds an executable in various places.
        """

        # if rooted, check the bin directory
        if self.root:
            path = os.path.join(self.root, 'bin', name)
            if os.access(path, os.R_OK | os.X_OK):
                return path

        # try to find with "which" (for OS X)
        code, path = self._call(('which', name))
        path = path and path.strip() or path
        if code == 0 and os.access(path, os.R_OK | os.X_OK):
            return path.strip()

        # try to find it with "whereis"
        code, output = self._call(('whereis', name))
        if code == 0:
            output = output.split(' ')
            if len(output) > 1:
                for path in output[1:]:
                    if os.access(path, os.R_OK | os.X_OK):
                        return path

        # finally, look in the bin directory of mrsd buildout
        if name != 'mrsd':
            mpath = self.find_executable(name='mrsd')
            # follow symlink, if it's one
            try:
                mpath = os.readlink(mpath)
            except OSError:
                pass

            if mpath:
                dir = os.path.dirname(mpath.strip())
                path = os.path.join(dir, name)
                if os.access(path, os.R_OK | os.X_OK):
                    return path

        raise Exception('Could not find executable "%s" in PATH ' % name + \
                            'nor in this buildout.')

    def _call(self, *args, **kwargs):
        """Run a command and return the exitcode and
        the output.
        """
        kwargs['stdout'] = subprocess.PIPE
        p = subprocess.Popen(*args, **kwargs)
        response, response_error = p.communicate()
        exitcode = p.poll()
        if exitcode:
            exitcode = p.wait()
        return (exitcode, response)
