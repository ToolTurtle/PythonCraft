"""Tests for PythonCraft. Run them all with:   python3 -m unittest discover -s tests -t .      (or: python3 run_tests.py)

The tests never touch your saves, progress or submissions: everything they write goes into a throwaway folder."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(tempfile.mkdtemp(prefix='pythoncraft_tests_'))
for name, folder in (('PYTHONCRAFT_SAVES', 'saves'), ('PYCRAFT_MODCACHE', 'modcache'), ('PYCRAFT_SUBMISSIONS', 'submissions'),
                     ('PYCRAFT_LANWORLDS', 'lanworlds'), ('PYCRAFT_CLASSES', 'classes')):
    os.environ[name] = str(SCRATCH / folder)
os.environ['PYCRAFTWORLD_PROGRESS'] = str(SCRATCH / 'progress.json')
os.environ['PYCRAFT_NAME'] = 'Tester'
sys.path.insert(0, str(ROOT))


def make_png(path, color=(200, 100, 50, 255), size=(16, 16)):
    from PIL import Image
    Image.new('RGBA', size, color).save(path)
    return str(path)


def scratch(name):
    """A new empty folder for one test."""
    folder = SCRATCH / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder
