"""Create a source-only folder that can be uploaded as a GitHub repository."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'github-upload' / 'RF-Traffic-Monitor'
TOP_LEVEL = (
    '.gitignore', 'DESIGN.md', 'LICENSE', 'LICENSE-STATUS.md', 'PUBLISHING.md',
    'README.md', 'THIRD-PARTY.md', 'setup.ps1',
)
SOURCE_TREES = ('app', 'tests', 'third_party', 'tools')


def excluded(relative: Path) -> bool:
    parts = relative.parts
    if '__pycache__' in parts or relative.suffix in ('.pyc', '.pyo'):
        return True
    if parts[:2] in (
        ('app', 'vendor'), ('app', 'runtime'), ('app', 'data'),
        ('app', 'maps'), ('tests', 'fixtures'),
    ):
        return True
    if parts[:3] == ('app', 'native', 'target'):
        return True
    return relative == Path('app/config.json')


def main() -> None:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True)
    for name in TOP_LEVEL:
        shutil.copy2(ROOT / name, DESTINATION / name)
    for tree in SOURCE_TREES:
        for source in (ROOT / tree).rglob('*'):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            if excluded(relative):
                continue
            target = DESTINATION / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(DESTINATION)


if __name__ == '__main__':
    main()
