import datetime
from typing import Any

import polars as pl

# Mapping from Polars DataTypes to Python string representations (for code generation)
POLARS_TO_PY_STR = {
    pl.Int8: "int",
    pl.Int16: "int",
    pl.Int32: "int",
    pl.Int64: "int",
    pl.UInt8: "int",
    pl.UInt16: "int",
    pl.UInt32: "int",
    pl.UInt64: "int",
    pl.Float32: "float",
    pl.Float64: "float",
    pl.Boolean: "bool",
    pl.Utf8: "str",
    pl.String: "str",
    pl.Date: "date",
    pl.Datetime: "datetime",
    pl.Categorical: "str",
    pl.List: "list",
    pl.Struct: "dict",
    pl.Object: "Any",
    pl.Null: "Any",
}

# Mapping from Polars DataTypes to actual Python types (for runtime validation)
POLARS_TO_PY_TYPE = {
    pl.Int8: int,
    pl.Int16: int,
    pl.Int32: int,
    pl.Int64: int,
    pl.UInt8: int,
    pl.UInt16: int,
    pl.UInt32: int,
    pl.UInt64: int,
    pl.Float32: float,
    pl.Float64: float,
    pl.Boolean: bool,
    pl.Utf8: str,
    pl.String: str,
    pl.Date: datetime.date,
    pl.Datetime: datetime.datetime,
    pl.Categorical: str,
    pl.List: list,
    pl.Struct: dict,
    pl.Object: Any,
    pl.Null: type(None),
}
