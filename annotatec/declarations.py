import re
import abc
import ctypes
import operator

from . import libtypes


DEBUG_SHOW_COMPILATION = False


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


class DeclarationError(libtypes.AnnotatecError):
    pass


class NamespaceError(libtypes.AnnotatecError):
    pass


_ARRAY_TYPE_RE = re.compile(r"(\w+)\[(\d+)\]")


class DeclarationsNamespace(dict):

    def __init__(self, lib: ctypes.CDLL, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib = lib

    def unwrap(self, wrapped):
        if isinstance(wrapped, MembersWrapper):
            return wrapped.subject
        else:
            return wrapped

    def compile(self, name: str, unwrap: bool = False):
        """
        Arguments:
            unwrap: bool, default = False; By default enums, flags and
                structs are being wrapped by MembersWrapper, so you can access
                their members. Setting this to True you enfore to return C
                type instead of the wrapper.
        """

        if DEBUG_SHOW_COMPILATION:
            print(f"parse type {name}")

        if name[-1] == "*":
            compiled = self.compile(name[:-1])
            return ctypes.POINTER(self.unwrap(compiled))

        if "[" in name and "]" in name:
            type_name, amount = _ARRAY_TYPE_RE.match(name).groups()
            compiled = self.compile(type_name) * amount
            return (
                self.unwrap(compiled)
                if unwrap
                else compiled
            )

        if name in BASE_C_TYPES:
            return BASE_C_TYPES[name]

        if name not in self:
            raise NamespaceError(
                f"Trying to get `{name}` object, but there's no objects with "
                "such name in the namespace")
        else:
            obj = self[name]

        if isinstance(obj, VariableDeclaration):
            return obj
        else:
            compiled = obj.compile()
            return (
                self.unwrap(compiled)
                if unwrap
                else compiled
            )

    def compile_unwrap(self, name: str):
        """Is equivalent to self.compile(name, unwrap=True)
        """
        return self.compile(name=name, unwrap=True)

    def compile_all(self):
        for name, declaration in self.items():
            if isinstance(declaration, VariableDeclaration):
                continue
            self.compile(name)

    def reset_compilation(self, name: str):
        if isinstance(self[name], VariableDeclaration):
            return
        self[name].compiled = False
        self[name].compilation_result = None

    def reset_compilations(self):
        for name in self.keys():
            self.reset_compilation(name)


class Declaration(metaclass=abc.ABCMeta):
    type_name: str = "declaration"
    singular_units: list = []
    plural_units: list = []

    def __init__(self, namespace: DeclarationsNamespace, name: str):

        if DEBUG_SHOW_COMPILATION:
            print(
                f"process declaration @{self.type_name} {name}")

        self.namespace = namespace
        self.name = name
        namespace[name] = self

        self.compiled = False
        self.compilation_result = None

    @abc.abstractmethod
    def compile(self):
        pass


class FunctionDeclaration(Declaration):
    type_name: str = "function"
    singular_units = ["return"]
    plural_units = ["argument"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        return_unit: libtypes.UnitValues,
        argument_units: libtypes.UnitValuesList = None
    ):
        super().__init__(namespace, name)

        if len(return_unit) != 1:
            raise DeclarationError(
                "Function declaration have more than one values for @return.")

        if (
            argument_units and
            any(len(argument) != 1 for argument in argument_units)
        ):
            raise DeclarationError(
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
                self.namespace.compile_unwrap,
                [self.return_type] + self.argument_types
            )))

            self.compilation_result = prototype(
                (self.name, self.namespace.lib))
            self.compiled = True

        return self.compilation_result


class MembersDeclaration:

    def __getattr__(self, key):
        return self.members[key]


class MembersWrapper:

    def __init__(self, subject, wrapper):
        self.subject = subject
        self.wrapper = wrapper

    def __getattr__(self, key):
        try:
            return getattr(self.wrapper, key)
        except KeyError:
            return getattr(self.subject, key)

    def __call__(self, *args, **kwargs):
        return self.subject(*args, **kwargs)

    def __mul__(self, amount):
        return MembersWrapper(
            subject=(self.subject * amount),
            wrapper=self.wrapper
        )


class StructDeclaration(Declaration, MembersDeclaration):
    type_name: str = "struct"
    plural_units = ["member"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        member_units: libtypes.UnitValuesList
    ):
        super().__init__(namespace, name)

        if any(len(member) != 2 for member in member_units):
            raise DeclarationError(
                "Struct declaration must have exactly 2 values for @member.")

        self.members = {
            name: type_name
            for type_name, name in member_units
        }

    def compile(self):

        if not self.compiled:

            class compiled_struct(ctypes.Structure):
                _fields_ = [
                    (field_name, self.namespace.compile_unwrap(field_type))
                    for field_name, field_type
                    in self.members.items()
                ]

            self.compilation_result = MembersWrapper(
                subject=compiled_struct, wrapper=self)
            self.compiled = True

        return self.compilation_result


class EnumDeclaration(Declaration, MembersDeclaration):
    type_name: str = "enum"
    singular_units = ["type"]
    plural_units = ["member"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        member_units: libtypes.UnitValuesList,
        type_unit: libtypes.UnitValues = None
    ):
        super().__init__(namespace, name)

        if any(len(member) != 2 for member in member_units):
            raise DeclarationError(
                "Struct declaration must have exactly 2 values for @member.")

        self.enum_type = (
            BASE_C_TYPES["int"] if not type_unit else type_unit[0]
        )

        self.members = {name: eval(value) for name, value in member_units}

    def compile(self):

        if not self.compiled:
            result = self.namespace.compile_unwrap(self.enum_type)
            self.compilation_result = MembersWrapper(
                subject=result, wrapper=self)
            self.compiled = True

        return self.compilation_result


class FlagsDeclaration(Declaration, MembersDeclaration):
    type_name: str = "flags"
    singular_units = ["type"]
    plural_units = ["flag"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        type_unit: libtypes.UnitValues, flag_units: libtypes.UnitValuesList
    ):
        super().__init__(namespace, name)

        if any(len(member) != 2 for member in flag_units):
            raise DeclarationError(
                "Flags declaration must have exactly 2 values for @flag.")

        self.flags_type = (
            BASE_C_TYPES["int"] if not type_unit else type_unit[0]
        )

        self.members = {name: eval(value) for name, value in flag_units}

    def compile(self):

        if not self.compiled:
            result = self.namespace.compile_unwrap(self.flags_type)
            self.compilation_result = MembersWrapper(
                subject=result, wrapper=self)
            self.compiled = True

        return self.compilation_result


class VariableDeclaration(Declaration):
    type_name: str = "variable"
    singular_units = ["type"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        type_unit: libtypes.UnitValues
    ):
        super().__init__(namespace, name)

        if len(type_unit) != 1:
            raise DeclarationError(
                "Variable declaration must have one value for @type.")

        self.variable_type = type_unit[0]

    def compile(self):
        raise TypeError(
            f"Tried to compile variable `{self.name}`. Variables cannot be "
            "used like type names. Use @typedef instead.")

    @property
    def var_type(self):

        if not self.compiled:
            self.compilation_result = \
                self.namespace.compile(self.variable_type)
            self.compiled = True

        return self.compilation_result

    @property
    def value(self):
        return self.var_type.in_dll(self.namespace.lib, self.name)


class TypedefDeclaration(Declaration):
    type_name: str = "typedef"
    singular_units = ["from_type"]

    def __init__(
        self,
        namespace: DeclarationsNamespace, name: str,
        from_type_unit: libtypes.UnitValues
    ):
        super().__init__(namespace, name)

        if len(from_type_unit) != 1:
            raise DeclarationError(
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
