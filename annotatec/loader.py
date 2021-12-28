import ctypes
import libtypes

from . import parser


class Loader:
    """Base class for loading and parsing libraries.
    """

    def __init__(
        self,
        library: libtypes.AddressOrDLL, sources: libtypes.AddressOrFile,
        precompile: bool = True
    ):
        """Loads library and parse headers.

        Arguments:
            library: str or ctypes.CDLL - address of the shared objects (DLL)
                or opened library.
            headers: list of strings or list of files - files with declarations
                to parse.
            precompile: bool - if set to True, than all objects will be
                compiled immediately. This option allows to lazy compile
                only objects that are needed.

        """

        self.libc = (
            ctypes.cdll.LoadLibrary(library)
            if isinstance(library, str)
            else library)
        self.parser = parser.FileParser(lib=self.libc)

        self.parser.scrap_sources(sources)

        if precompile:
            self.parser.initialize_objects()

    def __getattr__(self, key):
        return self.parser.declarations.compile(key)

    @property
    def ref(self):
        """Get pointer of any next objects.

        Example:
            Support `loader.obj` evaluates to `int`. That means,
            `loader.ref.obj` will be evaluated to `ctypes.POINTER(int)`.
        """
        class referencer:
            def __init__(referencer_self, loader_self, depth: int = 1):
                referencer_self.depth = depth
                referencer_self.loader = loader_self

            def __getattr__(self, key):
                return self.loader.parser.declarations.compile(
                    key + ("*" * self.depth))

            @property
            def ref(self):
                return referencer(self.loader, self.depth + 1)

        return referencer(loader_self=self, depth=1)
