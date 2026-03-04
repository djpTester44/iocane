import argparse
import sys

import polars as pl
from type_mapping import POLARS_TO_PY_STR


def generate_model(parquet_path: str, model_name: str, nullable: bool = False) -> str:
    try:
        df = pl.scan_parquet(parquet_path)
        schema = df.schema
    except Exception as e:
        print(f"Error reading parquet file: {e}", file=sys.stderr)
        sys.exit(1)

    lines = [
        "from  datetime import date, datetime",
        "from typing import Any, List, Optional",
        "from pydantic import BaseModel",
        "",
        f"class {model_name}(BaseModel):",
    ]

    for name, dtype in schema.items():
        # Handle simple types
        py_type = POLARS_TO_PY_STR.get(type(dtype), "Any")

        # Handle Nullable (Polars doesn't explicitly mark nullable in simple schema dict,
        # but generally Arrow/Parquet fields are nullable.
        # For strict contracts, we might assume Optional unless specified otherwise?
        # For now, let's keep it strict and let user loosen it.)

        # If the type is not found directly (e.g. List(Int64)), we might defaults to Any
        # or implement recursive checking. For MVP, we stick to mapping classes.

        # Check if we need better matching for instances vs classes
        if py_type == "Any":
            # Try instance check for complex types
            if isinstance(dtype, pl.List):
                py_type = "list"
            elif isinstance(dtype, pl.Struct):
                py_type = "dict"

        if nullable:
            py_type = f"Optional[{py_type}]"

        lines.append(f"    {name}: {py_type}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Pydantic model from Parquet file."
    )
    parser.add_argument("--input", required=True, help="Path to input Parquet file")
    parser.add_argument(
        "--name", required=True, help="Name of the Pydantic model class"
    )
    parser.add_argument(
        "--nullable", action="store_true", help="Wrap all types in Optional[]"
    )

    args = parser.parse_args()

    model_code = generate_model(args.input, args.name, args.nullable)
    print(model_code)


if __name__ == "__main__":
    main()
