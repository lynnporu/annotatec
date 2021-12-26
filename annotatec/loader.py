import ctypes
import typing

from . import parser


class Loader:
    """Base class for loading and parsing libraries.
    """

    def __init__(
        self,
        library: typing.Union[str, ctypes.CDLL],
        headers: typing.List[typing.Union[str, typing.TextIO]],
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

        if precompile:
            self.parser.parse_files(headers)
        else:
            self.parser.scrap_files(headers)

    def __getattr__(self, key):
        return self.parser.declarations.compile(key)
