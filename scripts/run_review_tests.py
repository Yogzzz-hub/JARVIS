"""Run the preserved release tests without restoring deleted working-tree files."""
from pathlib import Path
import shutil
import subprocess
import sys
import types


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    import jarvis
    import pytest

    baseline = root / '.runtime/review/baseline'
    commit = '454f79141d99af2ecea749b9ed487e0464531ac5'
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    prefix = git('rev-parse', '--show-prefix').decode().strip()
    for path in git('ls-tree', '-r', '--name-only', commit).decode().splitlines():
        if not path.startswith(('jarvis/tests/', 'tests/data/', 'scripts/', 'jarvis/scripts/')):
            continue
        destination = (baseline / path).resolve()
        if not destination.is_relative_to(baseline.resolve()):
            raise ValueError('Historical file escaped baseline directory')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(git('show', f'{commit}:{prefix}{path}'))
    migrations = baseline / 'jarvis/db/migrations'
    migrations.mkdir(parents=True, exist_ok=True)
    for source in (root / 'jarvis/db/migrations').glob('*.sql'):
        shutil.copy2(source, migrations / source.name)
    jarvis.__path__.append(str(baseline / 'jarvis'))
    package = types.ModuleType('scripts')
    package.__path__ = [str(baseline / 'scripts')]
    sys.modules['scripts'] = package
    return pytest.main([str(baseline / 'jarvis/tests'), str(root / 'tests'), '-q',
                        '--tb=short', f'--junitxml={root / ".runtime/review/all-results.xml"}'])


if __name__ == '__main__':
    raise SystemExit(main())
