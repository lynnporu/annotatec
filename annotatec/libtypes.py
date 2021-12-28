import typing
import pathlib


UnitType = typing.Tuple[str, typing.Tuple[str]]
UnitsType = typing.List[UnitType]

UnitValues = tuple
UnitValuesList = typing.List[UnitValues]

Directory = typing.Union[str, pathlib.Path]
AddressOrFile = typing.Union[str, typing.TextIO, pathlib.Path]


class AnnotatecError(Exception):
    pass
