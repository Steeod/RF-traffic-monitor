"""Create a source-only folder that can be uploaded as a GitHub repository."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = ROOT / 'github-upload' / 'RF-Traffic-Monitor'
TOP_LEVEL = (
    '.gitattributes', '.gitignore', 'DESIGN.md', 'LICENSE', 'LICENSE-STATUS.md', 'PUBLISHING.md',
    'README.md', 'THIRD-PARTY.md', 'setup.ps1',
)
SOURCE_TREES = ('app', 'images', 'tests', 'third_party', 'tools')


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


def main(destination: Path) -> None:
    destination = destination.resolve()
    upload_root = (ROOT / 'github-upload').resolve()
    if destination.parent != upload_root:
        raise ValueError(f'Destination must be directly inside {upload_root}')
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in TOP_LEVEL:
        shutil.copy2(ROOT / name, destination / name)
    for tree in SOURCE_TREES:
        for source in (ROOT / tree).rglob('*'):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            if excluded(relative):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    main(args.destination)
