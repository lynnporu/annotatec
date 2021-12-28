import ctypes
import typing
import libtypes

from . import parser


class Loader:
    """Base class for loading and parsing libraries.
    """

    def __init__(
        self,
        library: libtypes.AddressOrDLL,
        sources: typing.List[libtypes.AddressOrFile],
        c_extensions: bool = False, h_extensions: bool = True,
        precompile: bool = True
    ):
        """Loads library and parse headers.

        Arguments:
            library: str or ctypes.CDLL - address of the shared objects (DLL)
                or opened library.
            sources: list of strings or list of files - files or directories
                with files with declarations to parse.
            precompile: bool - if set to True, than all objects will be
                compiled immediately. This option allows to lazy compile
                only objects that are needed.
            c_extension: bool - if set to True and a directory given, then all
                `.c` files in this directory will be parsed.
            h_extensions: bool - parse all .h files in given directory.

        """

        self.libc = (
            ctypes.cdll.LoadLibrary(library)
            if isinstance(library, str)
            else library)
        self.parser = parser.FileParser(lib=self.libc)

        self.parse_sources(
            sources,
            c_extensions=c_extensions, h_extensions=h_extensions)

        if precompile:
            self.compile()

    def __getattr__(self, key):
        return self.parser.declarations.compile(key)

    def parse_sources(
        self,
        sources: typing.Union[
            libtypes.AddressOrFile,
            typing.List[libtypes.AddressOrFile]
        ],
        *args, **kwargs
    ):
        """Parse a single source, which can be a file or directory.
        """
        if not isinstance(sources, list):
            sources = [sources]

        self.parser.scrap_sources(sources, *args, **kwargs)

    def compile(self):
        """Compile given sources.
        """
        self.parser.initialize_objects()

    def reset(self):
        """This reset the compilation.
        """
        self.parser.reset_compilations()

    def recompile(self):
        """This will recompile the namespace.
        """
        self.parser.reset_compilations()
        self.parser.initialize_objects()

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
