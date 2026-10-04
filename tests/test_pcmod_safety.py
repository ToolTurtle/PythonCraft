"""A .pcmod is data only. These try to make a bad one do something: every one must be turned away, and nothing may change."""
import io
import json
import unittest
import zipfile

import tests
import blocks
import mobtypes
import mods
from PIL import Image
from tests import make_png, scratch


def png_bytes(size=(16, 16)):
    buffer = io.BytesIO()
    Image.new('RGBA', size, (1, 2, 3, 255)).save(buffer, 'PNG')
    return buffer.getvalue()


def good_spec(**changes):
    spec = {'format': 'pcmod', 'version': 1, 'name': 'sm_test', 'ops': [
        {'op': 'addblock', 'name': 'sm_block', 'faces': {'all': {'file': 'files/a.png'}}, 'like': None, 'props': {}}]}
    spec.update(changes)
    return spec


def write(name, spec=None, files=None, extra=None, raw_json=None):
    """Make a zip in the scratch folder. files: {name: bytes}; extra: more raw entries."""
    path = scratch('pcmod_bad') / name
    files = {'files/a.png': png_bytes()} if files is None else files
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('mod.json', raw_json if raw_json is not None else json.dumps(spec if spec is not None else good_spec()))
        for entry, data in files.items():
            archive.writestr(entry, data)
        for entry, data in (extra or {}).items():
            archive.writestr(entry, data)
    return str(path)


class Rejected(unittest.TestCase):
    def reject(self, path, words=''):
        names_before, types_before = list(blocks.NAMES), set(mobtypes.TYPES)
        with self.assertRaisesRegex(mods.ModFileError, words):
            mods.load_pcmod(path)
        self.assertEqual(list(blocks.NAMES), names_before, 'a rejected mod changed the game')
        self.assertEqual(set(mobtypes.TYPES), types_before)

    def test_the_good_one_loads(self):
        mods.load_pcmod(write('good.pcmod'))
        self.assertIn('sm_block', blocks.BLOCKS)

    def test_not_a_zip(self):
        path = scratch('pcmod_bad') / 'text.pcmod'
        path.write_text('hello')
        self.reject(str(path), 'not a mod file')

    def test_missing_file(self):
        self.reject(str(scratch('pcmod_bad') / 'nothing.pcmod'), 'Could not read')

    def test_code_or_other_files_are_not_allowed(self):
        self.reject(write('py.pcmod', extra={'evil.py': 'import os'}), 'not allowed')
        self.reject(write('sh.pcmod', extra={'files/run.sh': 'rm -rf /'}), 'not allowed')
        self.reject(write('hidden.pcmod', extra={'files/.x.png': png_bytes()}), 'not allowed')

    def test_path_tricks_are_not_allowed(self):
        for name in ('../escape.png', 'files/../../escape.png', '/etc/passwd', 'files/sub/a.png', 'C:\\x.png'):
            self.reject(write('trick.pcmod', extra={name: png_bytes()}), 'not allowed')

    def test_no_mod_json_or_bad_json(self):
        path = scratch('pcmod_bad') / 'nojson.pcmod'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('files/a.png', png_bytes())
        self.reject(str(path), 'no mod.json')
        self.reject(write('badjson.pcmod', raw_json='{not json'), 'cannot be read')
        self.reject(write('list.pcmod', raw_json='[1, 2]'), 'not a PythonCraft mod')

    def test_wrong_format_or_version(self):
        self.reject(write('fmt.pcmod', good_spec(format='other')), 'not a PythonCraft mod')
        self.reject(write('ver.pcmod', good_spec(version=99)), 'version')

    def test_unknown_or_extra_steps(self):
        spec = good_spec(ops=[{'op': 'exec', 'code': 'import os'}])
        self.reject(write('exec.pcmod', spec), 'not something a mod can do')
        op = good_spec()['ops'][0] | {'run': 'import os'}
        self.reject(write('extra.pcmod', good_spec(ops=[op])), 'unknown parts')

    def test_pictures_must_be_pictures(self):
        self.reject(write('notpng.pcmod', files={'files/a.png': b'GIF89a not a png'}), 'not a PNG')
        self.reject(write('huge.pcmod', files={'files/a.png': png_bytes((600, 600))}), 'not a PNG')
        self.reject(write('missing.pcmod', files={}), 'not in the mod')

    def test_a_file_reference_cannot_point_outside(self):
        op = good_spec()['ops'][0]
        op['faces'] = {'all': {'file': '../../etc/passwd'}}
        self.reject(write('ref.pcmod', good_spec(ops=[op])), 'picture file inside')
        op['faces'] = {'all': '/etc/passwd'}
        self.reject(write('ref2.pcmod', good_spec(ops=[op])), 'picture file inside')

    def test_too_big_or_a_zip_bomb(self):
        self.reject(write('big.pcmod', files={'files/a.png': b'\0' * 3_000_000}), 'too big')
        self.reject(write('bomb.pcmod', files={'files/a.png': png_bytes()}, extra={'files/b.png': b'\0' * 1_900_000}), 'too big')

    def test_too_many_steps_or_nesting(self):
        op = good_spec()['ops'][0]
        self.reject(write('many.pcmod', good_spec(ops=[op] * 1001)), 'very long list')
        deep = good_spec(ops=[])
        value = 'x'
        for _ in range(12):
            value = [value]
        deep['description'] = value
        self.reject(write('deep.pcmod', deep), 'nested')

    def test_bad_names_and_values_are_caught_when_loading(self):
        op = good_spec()['ops'][0] | {'name': '../../x'}
        self.reject(write('name.pcmod', good_spec(ops=[op])), 'did not work')
        op = good_spec()['ops'][0] | {'props': {'hardness': 'very'}}
        self.reject(write('prop.pcmod', good_spec(ops=[op])), 'did not work')
        self.reject(write('modname.pcmod', good_spec(name='Bad Name!')), 'small letters')

    def test_a_creature_cannot_make_up_a_change_or_condition(self):
        base = {'op': 'mob', 'name': 'sm_mob', 'base': 'zombie', 'calls': [], 'conditions': []}
        self.reject(write('call.pcmod', good_spec(ops=[base | {'calls': [['__class__', 1]]}])), 'not allowed')
        self.reject(write('cond.pcmod', good_spec(ops=[base | {'conditions': [{'type': 'run_code'}]}])), 'not allowed')
        self.reject(write('cond2.pcmod', good_spec(ops=[base | {'conditions': [{'type': 'at_night', 'cmd': 'x'}]}])), 'not allowed')

    def test_a_creature_from_nothing(self):
        base = {'op': 'mob', 'name': 'sm_mob2', 'base': 'no_such_creature', 'calls': [], 'conditions': []}
        self.reject(write('nobase.pcmod', good_spec(ops=[base])), 'no creature')


if __name__ == '__main__':
    unittest.main()
