import re
import abc
import ctypes
import typing
import operator
from collections import defaultdict


_COMMENT_START_RE = re.compile(r"^/\*\s*")
_COMMENT_END_RE = re.compile(r"\s*\*/$")

UnitType = typing.Tuple[str, typing.Tuple[str]]
UnitsType = typing.List[UnitType]

UnitValues = tuple
UnitValuesList = typing.List[UnitValues]


BASE_C_TYPES = {
    "void": None,

    "uint8": ctypes.c_uint8,
    "uint16": ctypes.c_uint16,
    "uint32": ctypes.c_uint32,
    "uint64": ctypes.c_uint64,
    "int8": ctypes.c_int8,
    "int16": ctypes.c_int16,
    "int32": ctypes.c_int32,
    "int64": ctypes.c_int64,

    "bool": ctypes.c_bool,
    "char": ctypes.c_char,
    "wchar": ctypes.c_wchar,
    "uchar": ctypes.c_ubyte,
    "short": ctypes.c_short,
    "ushort": ctypes.c_ushort,
    "int": ctypes.c_int,
    "uint": ctypes.c_uint,
    "long": ctypes.c_long,
    "ulong": ctypes.c_ulong,
    "longlong": ctypes.c_longlong,
    "ulonglong": ctypes.c_ulonglong,

    "string": ctypes.c_char_p,

    "size": ctypes.c_size_t,
    "ssize": ctypes.c_ssize_t,

    "double": ctypes.c_double,
    "long_double": ctypes.c_longdouble,
    "float": ctypes.c_float
}


class NamespaceError(Exception):
    pass


_ARRAY_TYPE_RE = re.compile(r"(\w+)\[(\d+)\]")


class DeclarationsNamespace(dict):

    def __init__(self, lib: ctypes.CDLL, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib = lib

    def compile(self, name: str):

        if name[-1] == "*":
            return ctypes.POINTER(self.compile(name[:-1]))

        if "[" in name and "]" in name:
            type_name, amount = _ARRAY_TYPE_RE.match(name).groups()

        if name in BASE_C_TYPES:
            return BASE_C_TYPES[name]

        if name not in self:
            raise NamespaceError(
                f"Trying to get `{name}` object, but there's no objects with "
                "such name in the namespace")
        else:
            return self[name].compile()

    def compile_all(self):
        for name, declaration in self.items():
            if isinstance(declaration, VariableDeclaration):
                continue
            self.compile(name)


class Declaration(metaclass=abc.ABCMeta):
    type_name: str = "declaration"
    singular_units: list = []
    plural_units: list = []

    def __init__(self, namespace: DeclarationsNamespace, name: str):

        self.namespace = namespace
        self.name = name
        namespace[name] = self

        self.compiled = False
        self.compilation_result = None

    @abc.abstractmethod
    def compile(self):
        pass


class MembersDeclaration:

    def __getattr__(self, key):
        return self.members[key]


class FunctionDeclaration(Declaration):
    type_name: str = "function"
    singular_units = ["return"]
    plural_units = ["argument"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        return_unit: UnitValues, argument_units: UnitValuesList = None
    ):
        super().__init__(namespace, name)

        if len(return_unit) != 1:
            raise ParserError(
                "Function declaration have more than one values for @return.")

        if (
            argument_units and
            any(len(argument) != 1 for argument in argument_units)
        ):
            raise ParserError(
                "Function declaration have more than one values "
                "for @argument.")

        self.return_type = return_unit[0]
        self.argument_types = list(map(
            operator.itemgetter(0),
            argument_units or []
        ))

    def compile(self):

        if not self.compiled:

            prototype = ctypes.CFUNCTYPE(*list(map(
                self.namespace.compile,
                [self.return_type] + self.argument_types
            )))

            self.compilation_result = prototype(
                (self.name, self.namespace.lib))
            self.compiled = True

        return self.compilation_result


class StructDeclaration(Declaration, MembersDeclaration):
    type_name: str = "struct"
    plural_units = ["member"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        member_units: UnitValuesList
    ):
        super().__init__(namespace, name)

        if any(len(member) != 2 for member in member_units):
            raise ParserError(
                "Struct declaration must have exactly 2 values for @member.")

        self.members = {
            name: type_name
            for type_name, name in member_units
        }

    def compile(self):

        if not self.compiled:

            class compiled_struct(ctypes.Structure):
                _fields_ = [
                    (field_name, self.namespace.compile(field_type))
                    for field_name, field_type
                    in self.members.items()
                ]

            self.compilation_result = compiled_struct
            self.compiled = True

        return self.compilation_result


class EnumDeclaration(Declaration, MembersDeclaration):
    type_name: str = "enum"
    singular_units = ["type"]
    plural_units = ["member"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        type_unit: UnitValues, member_units: UnitValuesList
    ):
        super().__init__(namespace, name)

        if any(len(member) != 2 for member in member_units):
            raise ParserError(
                "Struct declaration must have exactly 2 values for @member.")

        self.enum_type = type_unit[0]
        self.members = {name: eval(value) for name, value in member_units}

    def compile(self):

        if not self.compiled:
            self.compilation_result = self.namespace.compile(self.enum_type)
            self.compiled = True

        return self.compilation_result


class FlagsDeclaration(Declaration, MembersDeclaration):
    type_name: str = "flags"
    singular_units = ["type"]
    plural_units = ["flag"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        type_unit: UnitValues, flag_units: UnitValuesList
    ):
        super().__init__(namespace, name)

        if len(type_unit) != 1:
            raise ParserError(
                "Flags declaration must have one value for @type.")

        if any(len(member) != 2 for member in flag_units):
            raise ParserError(
                "Flags declaration must have exactly 2 values for @flag.")

        self.flags_type = type_unit[0]
        self.members = {name: eval(value) for name, value in flag_units}

    def compile(self):

        if not self.compiled:
            self.compilation_result = self.namespace.compile(self.flags_type)
            self.compiled = True

        return self.compilation_result


class VariableDeclaration(Declaration):
    type_name: str = "variable"
    singular_units = ["type"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        type_unit: UnitValues
    ):
        super().__init__(namespace, name)

        if len(type_unit) != 1:
            raise ParserError(
                "Variable declaration must have one value for @type.")

        self.variable_type = type_unit[0]

    def compile(self):
        raise TypeError(
            f"Tried to compile variable `{self.name}`. Variables cannot be "
            "used like type names. Use @typedef instead.")


class TypedefDeclaration(Declaration):
    type_name: str = "typedef"
    singular_units = ["from_type"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        from_type_unit: UnitValues
    ):
        super().__init__(namespace, name)

        if len(from_type_unit) != 1:
            raise ParserError(
                "TypedefDeclaration declaration must have one value "
                "for @from_type.")

        self.old_type = from_type_unit[0]

    def compile(self):

        if not self.compiled:
            self.compilation_result = self.namespace.compile(self.old_type)
            self.compiled = True

        return self.compilation_result


_DECLARATIONS = [
    FunctionDeclaration, StructDeclaration, EnumDeclaration, FlagsDeclaration,
    VariableDeclaration, TypedefDeclaration]


class ParserError(Exception):
    pass


AddressOrFile = typing.Union[str, typing.TextIO]


class FileParser:

    def __init__(self, lib: ctypes.CDLL):
        self.declarations = DeclarationsNamespace(lib=lib)
        self.live_objects = list()

    def parse_files(
        self, files: typing.List[AddressOrFile]
    ):
        self.scrap_files(files)
        self.initialize_objects()

    def scrap_files(
        self, files: typing.List[AddressOrFile]
    ):

        for file in files:
            self.scrap_file_declarations(file)

    def initialize_objects(self):
        self.declarations.compile_all()

    def scrap_file_declarations(self, file: AddressOrFile):

        if isinstance(file, str):
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

        declaration_type(
            namespace=self.declarations, name=declaration_name,
            **singular_units, **plural_units)

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
