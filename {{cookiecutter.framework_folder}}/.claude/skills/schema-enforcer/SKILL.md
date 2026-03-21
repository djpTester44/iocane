---
name: schema-enforcer
description: Tools for generating and validating Pydantic models and dataframe schemas. Use this skill to ensure data contracts are respected in data-heavy pipelines.
---

# Schema Enforcer

Provides utilities to generate Pydantic models from data files and enforce schema validity on DataFrames.

## Usage

### 1. Generate Pydantic Model from Parquet
Auto-detects schema from a parquet file and generates a Pydantic model definition.

```bash
uv run python .claude/skills/schema-enforcer/scripts/generate_model.py --input <parquet_path> --name <ModelName> [--nullable]
```
Use the `--nullable` flag to wrap all generated types in `Optional[...]`.

### 2. Generate Pydantic Model from YAML
Auto-detects schema from a YAML file and generates Pydantic model definitions.

```bash
uv run python .claude/skills/schema-enforcer/scripts/generate_yaml_model.py --input <yaml_path> --name <ModelName>
```

### 3. Validate DataFrame against Model
Validates a Polars DataFrame against a Pydantic model at runtime. The validator performs strict type checking and will raise a `ValueError` on type mismatch or missing columns.

```python
from .claude.skills.schema_enforcer.scripts.validator import validate_schema
from interfaces.models import InferenceSchema

# In your code:
df = pl.read_parquet(...)
try:
    validate_schema(df, InferenceSchema)
except ValueError as e:
    print(f"Validation failed: {e}")
```

## Resources

- [scripts/generate_model.py](scripts/generate_model.py): CLI tool for model generation
- [scripts/validator.py](scripts/validator.py): Runtime validation utility