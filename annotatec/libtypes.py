import typing


UnitType = typing.Tuple[str, typing.Tuple[str]]
UnitsType = typing.List[UnitType]

UnitValues = tuple
UnitValuesList = typing.List[UnitValues]

AddressOrFile = typing.Union[str, typing.TextIO]


class AnnotatecError(Exception):
    pass
