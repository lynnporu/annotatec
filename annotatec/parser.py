import re
import typing
import operator
from collections import defaultdict


_COMMENT_START_RE = re.compile(r"^/\*\s*")
_COMMENT_END_RE = re.compile(r"\s*\*/$")

UnitType = typing.Tuple[str, typing.Tuple[str]]
UnitsType = typing.List[UnitType]

UnitValues = tuple
UnitValuesList = typing.List[UnitValues]


class Declaration:
    type_name: str = "declaration"
    singular_units: list = []
    plural_units: list = []

    def __init__(self, name: str):
        self.name = name


class FunctionDeclaration(Declaration):
    type_name: str = "function"
    singular_units = ["return"]
    plural_units = ["argument"]

    def __init__(
        self,
        name: str,
        return_unit: UnitValues, argument_units: UnitValuesList
    ):
        super().__init__(name)

        if len(return_unit) != 1:
            raise ParserError(
                "Function declaration have more than one values for return.")

        if any(len(argument) != 1 for argument in argument_units):
            raise ParserError(
                "Function declaration have more than one values for argument.")

        self.return_type = return_unit[0]
        self.argument_types = list(map(operator.itemgetter(0), argument_units))


class StructDeclaration(Declaration):
    type_name: str = "struct"
    plural_units = ["member"]

    def __init__(
        self,
        name: str,
        member_units: UnitValuesList
    ):
        super().__init__(name)

        if any(len(member) != 2 for member in member_units):
            raise ParserError(
                "Struct declaration must have exactly 2 values for member.")

        self.members = {
            name: type_name
            for name, type_name in member_units
        }


class EnumDeclaration(Declaration):
    type_name: str = "enum"
    singular_units = ["type"]
    plural_units = ["member"]

    def __init__(
        self,
        name: str,
        type_unit: UnitValues, member_units: UnitValuesList
    ):
        super().__init__(name)

        if any(len(member) != 2 for member in member_units):
            raise ParserError(
                "Struct declaration must have exactly 2 values for member.")

        self.enum_type = type_unit[0]
        self.members = {name: eval(value) for name, value in member_units}


class FlagsDeclaration(Declaration):
    type_name: str = "flags"
    singular_units = ["type"]
    plural_units = ["flag"]

    def __init__(
        self,
        name: str,
        type_unit: UnitValues, flag_units: UnitValuesList
    ):
        super().__init__(name)

        if len(type_unit) != 1:
            raise ParserError(
                "Flags declaration must have one value for type.")

        if any(len(member) != 2 for member in flag_units):
            raise ParserError(
                "Flags declaration must have exactly 2 values for flag.")

        self.flags_type = type_unit[0]
        self.members = {name: eval(value) for name, value in flag_units}


class VariableDeclaration(Declaration):
    type_name: str = "variable"
    singular_units = ["type"]

    def __init__(
        self,
        name: str,
        type_unit: UnitValues, flag_units: UnitValuesList
    ):
        super().__init__(name)

        if len(type_unit) != 1:
            raise ParserError(
                "Variable declaration must have one value for type.")

        self.variable_type = type_unit[0]


_DECLARATIONS = [
    FunctionDeclaration, StructDeclaration, EnumDeclaration, FlagsDeclaration,
    VariableDeclaration]


class ParserError(Exception):
    pass


class FileParser:

    def __init__(self):
        self.declarations = dict()
        self.live_objects = list()

    def parse_files(
        self, files: typing.List[typing.Union[str, typing.TextIO]]
    ):
        self.scrap_files(files)
        self.initialize_objects()

    def scrap_files(
        self, files: typing.List[typing.Union[str, typing.TextIO]]
    ):

        for file in files:
            if isinstance(file, str):
                with open(file, mode="r") as file_buffer:
                    self.scrap_file_declarations(self, file_buffer)
            else:
                self.scrap_file_declarations(self, file)

    def initialize_objects(self):
        self.live_objects = [
            declaration.initialize(self.declarations)
            for declaration
            in self.declarations.values()]

    def scrap_file_declarations(self, file: typing.TextIO):

        lines = "".join(file.readlines()).split("\n")

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

    def check_declaration(self, line) -> typing.Optional[Declaration]:

        for declaration in _DECLARATIONS:
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
                        f"Declaration {declaration_type} does not have a name")
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

        declaration = declaration_type(
            name=declaration_name, **singular_units, **plural_units)

        self.declarations[declaration.name] = declaration

    def parse_line_units(self, line: str) -> UnitsType:

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
