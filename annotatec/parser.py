import re
import ctypes
import typing
import pathlib
import itertools
from collections import defaultdict

from . import declarations
from . import libtypes


_COMMENT_START_RE = re.compile(r"^/\*\s*")
_COMMENT_END_RE = re.compile(r"\s*\*/$")


class ParserError(libtypes.AnnotatecError):
    pass


class FileParser:

    def __init__(self, lib: ctypes.CDLL):
        self.declarations = declarations.DeclarationsNamespace(lib=lib)
        self.live_objects = list()

    def parse_files(
        self, files: typing.List[libtypes.AddressOrFile]
    ):
        self.scrap_files(files)
        self.initialize_objects()

    def scrap_files(
        self, files: typing.List[libtypes.AddressOrFile],
        c_extensions: bool = False, h_extensions: bool = True
    ):

        source_files = list()

        extensions = {
            "c": c_extensions,
            "h": h_extensions
        }

        include_extensions = [
            extension
            for extension, include in extensions
            if include]

        for file in files:

            if isinstance(file, typing.TextIO):
                source_files.append(file)

            source_path = pathlib.Path(file)

            if source_path.is_file():
                source_files.append(source_path)
            else:
                source_files.extend(self.get_path_files(
                    source_path, include_extensions
                ))

        for file in source_files:
            self.scrap_file_declarations(file)

    def get_path_files(self, path: pathlib.Path, extensions: typing.List[str]):

        def files_generator():
            for file in itertools.chain(*[
                path.glob(f"*.{ext}")
                for ext in extensions
            ]):
                if file.is_file():
                    yield file

        return list(files_generator())

    def initialize_objects(self):
        self.declarations.compile_all()

    def scrap_file_declarations(self, file: libtypes.AddressOrFile):

        if not isinstance(file, typing.TextIO):
            with open(file, mode="r") as file_buffer:
                file_lines = file_buffer.readlines()
        else:
            file_lines = file.readlines()

        lines = "".join(file_lines).split("\n")

        declaration_buffer = list()
        inside_declaration = False

        for line in lines:

            if _COMMENT_START_RE.match(line):
                inside_declaration = True

            if inside_declaration:
                declaration_buffer.append(line)

            if _COMMENT_END_RE.match(line):
                inside_declaration = False
                # strip end of the comment
                declaration_buffer[-1] = re.sub(
                    _COMMENT_END_RE,
                    repl="",
                    string=declaration_buffer[-1])
                self.parse_declaration(declaration_buffer)
                declaration_buffer.clear()

    def check_declaration(
        self, line
    ) -> typing.Optional[declarations.Declaration]:

        for declaration in declarations._DECLARATIONS:
            if f"@{declaration.type_name}" in line:
                return declaration

        return None

    def parse_declaration(self, lines: typing.List[str]):

        units = list()
        start_parsing = False

        for line in lines:

            stripped = line.lstrip("/* ")
            if not stripped:
                continue

            if not start_parsing:
                declaration_type = self.check_declaration(line)
                if declaration_type:
                    start_parsing = True

            if start_parsing:
                units.append(self.parse_line_units(stripped))

        if not declaration_type:
            return

        self.add_declaration(declaration_type, units)

    def add_declaration(self, declaration_type, units):

        singular_units = dict()
        plural_units = defaultdict(list)

        declaration_name = None

        for unit_name, unit_values in units:

            stripped = unit_name.lstrip("@")

            if stripped == declaration_type.type_name:
                if not unit_values:
                    raise ParserError(
                        f"declaration {declaration_type} does not have a name")
                declaration_name = unit_values[0]
                continue

            elif stripped in declaration_type.singular_units:
                singular_units[stripped + "_unit"] = unit_values

            elif stripped in declaration_type.plural_units:
                plural_units[stripped + "_units"].append(unit_values)

            else:
                raise ParserError(
                    f"Unknown unit type {unit_name} in "
                    f"declaration {declaration_type}")

        declaration_type(
            namespace=self.declarations, name=declaration_name,
            **singular_units, **plural_units)

    def parse_line_units(self, line: str) -> libtypes.UnitsType:

        units_type_name = ""
        units = list()
        char_buffer = list()

        bracket_prev_stack_counter = 0
        bracket_stack_counter = 0

        parsing_unit_type_name = False

        def flush_buffer():
            if not char_buffer:
                return
            units.append("".join(char_buffer))
            char_buffer.clear()

        for char in line + "\n":

            if char == "@":
                parsing_unit_type_name = True

            if char in [" ", "\n"]:

                # end of name
                if parsing_unit_type_name:
                    parsing_unit_type_name = False
                    units_type_name = "".join(char_buffer)
                    char_buffer.clear()
                    continue

                # end of bracket-enclosed token
                elif not bracket_stack_counter and bracket_prev_stack_counter:
                    flush_buffer()
                    bracket_prev_stack_counter = bracket_stack_counter
                    continue

                # end of regular token
                elif not (bracket_stack_counter or bracket_prev_stack_counter):
                    flush_buffer()
                    continue

            if char == "(":
                bracket_prev_stack_counter = bracket_stack_counter
                bracket_stack_counter += 1

            if char == ")":
                bracket_prev_stack_counter = bracket_stack_counter
                bracket_stack_counter -= 1

            char_buffer.append(char)

        return units_type_name, tuple(units)
