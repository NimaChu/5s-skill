"""Exercise 5S helpers against isolated disposable fixtures; no real project mutations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import workspace_5s as w


class WorkspaceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='5s-safety-')
        self.root = Path(self.temp.name).resolve() / '示例 workspace'
        self.root.mkdir()
        self.source = self.root / 'old build'
        self.source.mkdir()
        (self.source / '空目录').mkdir()
        (self.source / 'a.txt').write_text('original 原文', encoding='utf8')
        (self.source / 'z.bin').write_bytes(bytes(range(256)))
        self.archive = self.root / 'archive' / 'run.zip'

    def tearDown(self):
        self.temp.cleanup()

    def capture(self, remove=False):
        return w.archive_project(self.root, self.source, self.archive, apply=True, remove_source=remove)

    def test_preview_is_read_only_and_reports_optional_root_policy(self):
        (self.root / 'README.md').write_text('keep',encoding='utf8')
        (self.root / '.gitignore').write_text('keep',encoding='utf8')
        (self.root / 'loose.txt').write_text('keep',encoding='utf8')
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        report = w.inventory(self.root, root_allow=['README.md'], allow_dotfiles=True)
        self.assertEqual(report['root_policy_violations'], ['loose.txt'])
        self.assertFalse(w.inventory(self.root)['root_policy_checked'])
        self.assertFalse(w.archive_project(self.root, self.source, self.archive, remove_source=True)['applied'])
        self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')))

    def test_roundtrip_preserves_unicode_binary_and_empty_directory(self):
        result = self.capture(remove=True)
        self.assertTrue(result['source_removed'])
        self.assertFalse(self.source.exists())
        self.assertFalse(w.restore_project(self.root,self.archive)['applied'])
        self.assertFalse(self.source.exists())
        w.restore_project(self.root,self.archive,apply=True)
        self.assertEqual((self.source/'a.txt').read_text(encoding='utf8'),'original 原文')
        self.assertEqual((self.source/'z.bin').read_bytes(),bytes(range(256)))
        self.assertTrue((self.source/'空目录').is_dir())

    def test_conflict_preflight_writes_nothing_else(self):
        self.capture(remove=True)
        self.source.mkdir();(self.source/'z.bin').write_bytes(b'live changed data')
        with self.assertRaises(w.FiveSError):w.restore_project(self.root,self.archive,apply=True)
        self.assertFalse((self.source/'a.txt').exists())
        self.assertEqual((self.source/'z.bin').read_bytes(),b'live changed data')

    def test_parent_file_collision_is_detected_before_writes(self):
        self.capture(remove=True)
        self.source.write_text('existing file',encoding='utf8')
        with self.assertRaises((w.FiveSError,OSError)):w.restore_project(self.root,self.archive,apply=True)
        self.assertEqual(self.source.read_text(encoding='utf8'),'existing file')

    def test_changed_source_is_retained_and_archive_survives(self):
        original = w.snapshot
        calls = 0
        def changing(root,source):
            nonlocal calls
            calls += 1
            if calls == 2:(source/'late.txt').write_text('new live file',encoding='utf8')
            return original(root,source)
        with patch.object(w,'snapshot',side_effect=changing):
            with self.assertRaisesRegex(w.FiveSError,'Source changed'):self.capture(remove=True)
        self.assertTrue((self.source/'late.txt').exists())
        self.assertTrue(self.archive.is_file())
        w.restore_project(self.root,self.archive)  # Old capture itself remains valid.

    def test_existing_archive_and_nested_destination_are_not_mutated(self):
        with self.assertRaises(w.FiveSError):w.archive_project(self.root,self.source,self.source/'out.zip',apply=True,remove_source=True)
        self.capture()
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(w.FiveSError):self.capture(remove=True)
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(),digest)
        self.assertTrue(self.source.is_dir())
        with self.assertRaises(w.FiveSError):w.archive_project(self.root,self.root,self.archive)

    def test_traversal_extra_duplicate_and_corruption_rejected_without_writes(self):
        self.capture()
        with zipfile.ZipFile(self.archive) as bundle:
            entries={n:bundle.read(n) for n in bundle.namelist()}
        for case in ('traversal','extra','duplicate','corrupt'):
            with self.subTest(case=case):
                archive=self.root/'archive'/f'{case}.zip'
                values=dict(entries)
                if case=='traversal':
                    values['../outside.txt']=b'bad'
                    manifest=json.loads(values[w.MANIFEST]);manifest['source']='..';manifest['files']['../outside.txt']={'sha256':hashlib.sha256(b'bad').hexdigest(),'bytes':3,'mode':0o600}
                    values[w.MANIFEST]=json.dumps(manifest).encode()
                elif case=='extra':values['unlisted.txt']=b'bad'
                elif case=='corrupt':values['old build/a.txt']=b'bad changed content'
                with zipfile.ZipFile(archive,'w') as bundle:
                    for n,data in values.items():bundle.writestr(n,data)
                    if case=='duplicate':
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore');bundle.writestr(w.MANIFEST,values[w.MANIFEST])
                before=(self.source/'a.txt').read_bytes()
                with self.assertRaises(w.FiveSError):w.restore_project(self.root,archive,apply=True)
                self.assertEqual((self.source/'a.txt').read_bytes(),before)
                self.assertFalse((self.root.parent/'outside.txt').exists())

    def test_links_are_skipped_by_inventory_and_rejected_by_archive(self):
        external=Path(self.temp.name)/'external';external.mkdir();(external/'private.txt').write_text('outside',encoding='utf8')
        link=self.source/'linked'
        try:link.symlink_to(external,target_is_directory=True)
        except OSError as error:self.skipTest('Host did not allow creation of a symlink fixture: '+str(error))
        report=w.inventory(self.root);self.assertIn('old build/linked',report['skipped_links'])
        with self.assertRaises(w.FiveSError):self.capture(remove=True)
        self.assertEqual((external/'private.txt').read_text(encoding='utf8'),'outside')
        link.unlink()

    def test_cli_defaults_do_not_create_archive_or_remove_source(self):
        script=Path(w.__file__).resolve()
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        run=subprocess.run([sys.executable,'-B',str(script),'archive',str(self.root),'old build','archive/cli.zip','--remove-source'],capture_output=True,text=True,encoding='utf8',env=env)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertFalse(json.loads(run.stdout)['applied'])
        self.assertFalse((self.root/'archive/cli.zip').exists());self.assertTrue(self.source.exists())


if __name__=='__main__':unittest.main(verbosity=2)
