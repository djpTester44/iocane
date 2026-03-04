import re
from pathlib import Path


def extract_crc(md_content):
    components = {}
    current_comp = None
    in_responsibilities = False

    for line in md_content.split('\n'):
        if line.startswith('### '):
            current_comp = line[4:].strip()
            components[current_comp] = set()
            in_responsibilities = False
        elif '**Key Responsibilities:**' in line:
            in_responsibilities = True
        elif line.startswith('```') or line.startswith('**Responsibilities (CRC):**') or line.startswith('## '):
            in_responsibilities = False
        elif in_responsibilities and re.match(r'\s*\d+\.\s+`.*`', line):
            method_match = re.search(r'`([a-zA-Z_]\w*)\(.*?`', line)
            if method_match:
                components[current_comp].add(method_match.group(1))
            else:
                 prop_match = re.search(r'`([a-zA-Z_]\w*)`', line)
                 if prop_match:
                     components[current_comp].add(prop_match.group(1))
    return components

def extract_impl(file_path):
    if not Path(file_path).exists():
        return set()
    methods = set()
    content = Path(file_path).read_text(encoding='utf-8')
    for line in content.split('\n'):
        if line.strip().startswith('def '):
            method_name = line.strip()[4:].split('(')[0].strip()
            if not method_name.startswith('_'): # Filter out private methods
                 methods.add(method_name)
    return methods

specs = Path('plans/project-spec.md').read_text(encoding='utf-8')
crc_reqs = extract_crc(specs)

mapping = {
    'DataLoader': 'src/lib/io/loader.py',
    'BanditFactory': 'src/models/factory.py',
    'BanditTeam': 'src/models/team.py',
    'CreativeTeam': 'src/models/creative_team.py',
    'Orchestrator': 'src/models/orchestrator.py',
    'MetaBanditRouter': 'src/models/router.py',
    'ConstraintEngine': 'src/lib/constraints/engine.py',
    'BatchRunner': 'src/jobs/batch_runner.py',
    'MetricsEmitter': 'src/lib/metrics.py',
    'SchemaValidator': 'src/lib/schema_validator.py',
    'CLI': 'src/jobs/cli.py',
    'Entrypoint': 'src/jobs/entrypoint.py',
    'BanditLearner': 'src/models/factory.py',
    'StorageExporter': 'src/lib/storage/exporter.py',
    'ExporterFactory': 'src/lib/storage/factory.py'
}

print("--- Gap Analysis Report ---")
for comp, file_path in mapping.items():
    if comp not in crc_reqs:
        continue

    req_methods = crc_reqs[comp]
    impl_methods = extract_impl(file_path)

    missing = req_methods - impl_methods
    unanchored = impl_methods - req_methods

    # Exclude __init__ / built-ins
    missing = {m for m in missing if not m.startswith('__')}

    if missing or unanchored:
        print(f"\n{comp} ({file_path}):")
        if missing:
             print(f"  [Missing Implementation]: {', '.join(missing)}")
        if unanchored:
             print(f"  [Unanchored Code]: {', '.join(unanchored)}")
