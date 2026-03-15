import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def get_python_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        if not value:
            return "List[Any]"
        # Simple list type inference
        types = {get_python_type(v) for v in value}
        if len(types) == 1:
            return f"List[{list(types)[0]}]"
        return "List[Any]"
    if isinstance(value, dict):
        return "dict"
    return "Any"

def generate_models(data: dict[str, Any], root_name: str) -> str:
    lines = [
        "from typing import Any, List, Optional",
        "from pydantic import BaseModel, Field",
        "",
    ]

    generated_classes = []

    def process_dict(d: dict[str, Any], class_name: str):
        class_lines = [f"class {class_name}(BaseModel, frozen=True):"]
        sub_classes = []

        for key, value in d.items():
            if isinstance(value, dict):
                sub_class_name = "".join(word.capitalize() for word in key.split("_")) + "Config"
                class_lines.append(f"    {key}: {sub_class_name}")
                sub_classes.append((value, sub_class_name))
            else:
                py_type = get_python_type(value)
                class_lines.append(f"    {key}: {py_type}")

        # Add subclasses first to maintain order
        for sub_data, sub_name in sub_classes:
            process_dict(sub_data, sub_name)

        generated_classes.append("\n".join(class_lines))

    process_dict(data, root_name)

    # Reverse to put subclasses above parents if they were nested in logic but Pydantic needs them defined first
    # Actually my recursive call is depth-first, so I should return them in correct order.
    # Let's collect them in a list and print them.

    return "\n".join(lines + generated_classes)

def main():
    parser = argparse.ArgumentParser(description="Generate Pydantic models from a YAML file.")
    parser.add_argument("--input", required=True, help="Path to input YAML file")
    parser.add_argument("--name", required=True, help="Name of the root Pydantic model class")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with input_path.open() as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading YAML: {e}", file=sys.stderr)
        sys.exit(1)

    model_code = generate_models(data, args.name)
    print(model_code)

if __name__ == "__main__":
    main()
