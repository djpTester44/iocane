from typing import Any, Union, get_args, get_origin

import polars as pl
from pydantic import BaseModel

from .type_mapping import POLARS_TO_PY_TYPE  # type: ignore


def _get_allowed_types(annotation: Any) -> tuple:
    """Unwrap Optional and Union annotations to get a tuple of allowed types."""
    origin = get_origin(annotation)
    if origin is Union or str(origin) == "types.UnionType":
        return get_args(annotation)
    return (annotation,)


def validate_schema(df: pl.DataFrame, model: type[BaseModel]) -> bool:
    """
    Validate a Polars DataFrame against a Pydantic Model.

    Checks:
    1. All fields required by the model are present in the DataFrame.
    2. Column types in DataFrame are compatible with model fields.

    Does NOT currently validate every row value for performance reasons,
    but performs strict schema checking.

    Args:
        df: Polars DataFrame to validate.
        model: Pydantic BaseModel class definition.

    Returns:
        True if valid.

    Raises:
        ValueError: If schema mismatch found.
    """
    schema = df.schema
    model_fields = model.model_fields

    missing_columns = []
    type_mismatches = []

    for name, field_info in model_fields.items():
        if field_info.is_required() and name not in schema:
            missing_columns.append(name)
            continue

        if name in schema:
            # Get the base Polars data type to safely strip inner types (like List nesting or timezones)
            polars_dtype = schema[name]
            base_polars_type = polars_dtype.base_type()

            # Map Polars type to Python type
            mapped_py_type = POLARS_TO_PY_TYPE.get(base_polars_type, Any)

            # If Polars type maps to Any, bypass strict checking for that column
            if mapped_py_type is Any:
                continue

            expected_annotation = field_info.annotation
            if expected_annotation is Any:
                continue

            # Unwrap Union/Optional from Pydantic annotation
            allowed_types = _get_allowed_types(expected_annotation)

            # Check if the mapped Python type matches any of the allowed types
            if mapped_py_type not in allowed_types:
                # Handle edge cases where mapped type is a valid subclass of an allowed type
                is_valid_subclass = any(
                    isinstance(mapped_py_type, type)
                    and isinstance(t, type)
                    and issubclass(mapped_py_type, t)
                    for t in allowed_types
                )

                if not is_valid_subclass:
                    type_mismatches.append(
                        f"'{name}' (Expected: {expected_annotation}, Found: {polars_dtype})"
                    )

    errors = []
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
    if type_mismatches:
        errors.append(f"Type mismatches: {type_mismatches}")

    if errors:
        raise ValueError("Schema Validation Failed. " + " | ".join(errors))

    return True
