"""Some basic nodes to be moved/merged with zodict

Everybody should once write a node from scratch...
"""
import os

from odict import odict
from zope.location import LocationIterator


class NotLoaded(object):
    """This is used to enable None as a value
    """

class LazyNode(object):
    """Stuff we expect from our base of all bases
    """

    def __init__(self, name=None):
        self.__name__ = name
        self.__parent__ = None
        self._keys = None

    def __getattr__(self, key):
        return self[key]

    def __getitem__(self, key):
        try:
            val = self._keys[key]
        except TypeError:
            self.keys() # this will load keys
            val = self._keys[key]
        # this is what makes this node Lazy
        if val is NotLoaded:
            val = self._lazyload_child(key)

        val.__parent__ = self
        self._keys[key] = val
        return val

    def __iter__(self):
        """wrt to ldap and secondary keys iterchildkeys should return a tuple
        (key, prelim_data) where we could do key postprocessing and use
        prelim_data to create stubs of NotLoaded with secondary key
        """
        try:
            return self._keys.__iter__()
        except AttributeError:
            self._keys = odict()
            def wrap(self):
                for key in self._lazyload_keys():
                    self._keys[key] = NotLoaded
                    yield key
            return wrap(self)


    def _lazyload_keys(self):
        """Iterate over the child keys.

        You have to at least ``self._keys[key] = NotLoaded``.

        (see also ``__iter__`` and ``__getitem__``).
        """
        raise NotImplemented

    def _lazyload_child(self, key):
        """factor a child for key

        (see also ``__getitem__``)
        """
        raise NotImplemented

    def itervalues(self):
        for key in self.__iter__():
            yield self.__getitem__(key)

    def items(self):
        return [(k, self.__getitem__(k)) for k in self.__iter__()]

    def keys(self):
        return [x for x in self.__iter__()]

    def values(self):
        return [self.__getitem__(x) for x in self.__iter__()]

    @property
    def path(self):
        path = list()
        for parent in LocationIterator(self):
            path.append(parent.__name__)
        path.reverse()
        if path[0] is None:
            path[0] = ''
        return '/'.join(path)

    @property
    def root(self):
        root = None
        for parent in LocationIterator(self):
            root = parent
        return root


class FSNode(LazyNode):
    """A directory or file on the local filesystem.
    """
    @property
    def abspath(self):
        """The path of a local filesystem node is a string.
        """
        return os.path.join(*self.path)


class File(FSNode):
    """A file in the filesystem.

    We break with nodethink, suggestions welcome.
    """
    def __iter__(self):
        handle = open(self.abspath)
        for line in handle:
            yield line
        handle.close()


class Directory(FSNode):
    """A directory with possibly blacklisted content
    """
    blacklist = ('.', '..')

    def _iterchildkeys(self):
        """The items in a directory are already unique
        """
        for key in os.listdir(self.abspath):
            if self.blacklisted(key):
                continue
            self._keys[key] = NotLoaded
            yield key

    def blacklisted(self, key):
        return key in self.blacklist

    def _createchild(self, key):
        path = os.path.join(self.abspath, key)
        if os.path.isdir(path):
            val = Directory(key)
        elif os.path.isfile(path):
            val = File(key)
        else:
            raise
        return val
