import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from websmith import rule_source


class RuleSourceTests(unittest.TestCase):
    def archive(self, revision, files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, text in files.items():
                archive.writestr(f'websmith-cli-{revision}/{rule_source.SOURCE_PATHS[name]}', text)
        return stream.getvalue()

    def test_commit_pinning_cache_and_offline(self):
        revision = 'a' * 40
        files = {name: '# Updated\n' for name in rule_source.FILES}
        with tempfile.TemporaryDirectory() as folder, patch.object(rule_source, 'cache_root', return_value=Path(folder)), patch.dict('os.environ', {}, clear=True):
            replies = [json.dumps({'sha': revision}).encode(), self.archive(revision, files)]
            with patch.object(rule_source, 'download', side_effect=replies) as fetch:
                self.assertEqual(rule_source.load(), (files, revision))
                self.assertIn(revision, fetch.call_args.args[0])
            with patch.object(rule_source, 'download', side_effect=AssertionError('offline network')):
                self.assertEqual(rule_source.load(offline=True), (files, revision))

    def test_dry_run_and_incomplete_archive_never_change_cache(self):
        revision = 'b' * 40
        files = {name: '# Rules\n' for name in rule_source.FILES}
        with tempfile.TemporaryDirectory() as folder, patch.object(rule_source, 'cache_root', return_value=Path(folder)):
            cache = Path(folder) / 'current.json'
            cache.write_bytes(b'previous')
            for missing in [False, True]:
                source = dict(files)
                if missing:
                    source.pop('skills/editor/references/EDITORIAL_RULES.md')
                with patch.object(rule_source, 'download', side_effect=[json.dumps({'sha': revision}).encode(), self.archive(revision, source)]):
                    if missing:
                        with self.assertRaises(ValueError):
                            rule_source.load()
                    else:
                        rule_source.load(persist=False)
                self.assertEqual(cache.read_bytes(), b'previous')

    def test_rule_only_online_update_without_binary_release_preserves_local(self):
        from websmith.initialize import agent_files, install_files, starter
        from websmith.update import command_update
        from websmith import __version__
        resources = rule_source.local_files(Path(__file__).parents[1])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = agent_files('none', resources)
            files.update(starter('Site', 'site', 'https://example.test', 'it'))
            files['.websmith/project.json'] = json.dumps({'format_version': 1, 'agent': 'none', 'websmith_version': __version__})
            files['.websmith/installed-files.json'] = '{}'
            files['TONE_OF_VOICE.local.md'] = 'Keep my voice\n'
            install_files(root, files)
            resources['skills/editor/references/EDITORIAL_RULES.md'] = '# New rules without a binary release\n'
            args = SimpleNamespace(site_root=root, offline=False, dry_run=True)
            with patch('websmith.self_update.update_program', return_value=None), patch.object(rule_source, 'load', return_value=(resources, 'c' * 40)) as load:
                before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
                self.assertEqual(command_update(args), 0)
                load.assert_called_with(offline=False, persist=False)
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
                args.dry_run = False
                self.assertEqual(command_update(args), 0)
            self.assertEqual((root / 'EDITORIAL_RULES.md').read_text(), resources['skills/editor/references/EDITORIAL_RULES.md'])
            self.assertEqual((root / 'skills/editor/references/EDITORIAL_RULES.md').read_bytes(), (root / 'EDITORIAL_RULES.md').read_bytes())
            self.assertEqual((root / 'TONE_OF_VOICE.local.md').read_text(), 'Keep my voice\n')
            self.assertEqual(json.loads((root / '.websmith/project.json').read_text())['instructions_revision'], 'c' * 40)
