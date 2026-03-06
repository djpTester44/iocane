# Python Security Pitfalls

## Dangerous Functions

### Deserialization

| Dangerous | Safe Alternative |
|-----------|------------------|
| `pickle.load()` | `json.load()` |
| `yaml.load()` | `yaml.safe_load()` |
| `marshal.load()` | Avoid or validate |

### Command Execution

| Dangerous | Safe Alternative |
|-----------|------------------|
| `os.system(cmd)` | `subprocess.run([...], shell=False)` |
| `subprocess.run(cmd, shell=True)` | `subprocess.run([...], shell=False)` |
| `eval(user_input)` | Never use with untrusted input |
| `exec(user_input)` | Never use with untrusted input |

## Common Mistakes

### Timing Attacks

```python
# Vulnerable
if user_token == stored_token:
    ...

# Safe
import hmac
if hmac.compare_digest(user_token, stored_token):
    ...
```

### Path Traversal

```python
# Vulnerable
open(f"uploads/{filename}")

# Safe
from pathlib import Path
safe_path = Path("uploads").resolve() / filename
if not safe_path.is_relative_to(Path("uploads").resolve()):
    raise ValueError("Path traversal detected")
```

### Hardcoded Secrets

```python
# Vulnerable
API_KEY = "sk-abc123..."

# Safe
import os
API_KEY = os.environ["API_KEY"]
```

## Secure Defaults

| Task | Secure Default |
|------|----------------|
| Random tokens | `secrets.token_urlsafe(32)` |
| Password hashing | `bcrypt` or `argon2` |
| Temp files | `tempfile.mkstemp()` |
| HTTP requests | Verify SSL (`verify=True`) |