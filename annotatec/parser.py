import re
import typing


_COMMENT_START_RE = re.compile(r"^/\*\s*")
_COMMENT_END_RE = re.compile(r"\s*\*/$")

UnitType = typing.Tuple[str, typing.Tuple[str]]
UnitsType = typing.List[UnitType]


class Declaration:
    type_name: str = "declaration"
    singular_units: list = []
    plural_units: list = []

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def from_units(cls, units: UnitsType):
        print(f"units {str(units)}")
        return cls(name="abracadabra")


class FunctionDeclaration(Declaration):
    type_name: str = "function"
    singular_units = ["return"]
    plural_units = ["argument"]


class StructDeclaration(Declaration):
    type_name: str = "struct"
    plural_units = ["member"]


class EnumDeclaration(Declaration):
    type_name: str = "enum"
    plural_units = ["member"]


class FlagsDeclaration(Declaration):
    type_name: str = "flags"
    plural_units = ["flag"]


class VariableDeclaration(Declaration):
    type_name: str = "variable"
    singular_units = ["type"]


_DECLARATIONS = [
    FunctionDeclaration, StructDeclaration, EnumDeclaration, FlagsDeclaration,
    VariableDeclaration]


class FileParser:

    def __init__(self):
        self.declarations = dict()

    def parse_file(self, file: typing.TextIO):

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

        declaration = declaration_type.from_units(units)
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

        return units_type_name, units
