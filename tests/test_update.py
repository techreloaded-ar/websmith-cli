import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class UpdateTests(unittest.TestCase):
    def cli(self, root, *args):
        executable = [os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY') else [sys.executable, '-m', 'websmith']
        if args and args[0] == 'update':
            args = (*args, '--offline')
        return subprocess.run([*executable, *args], cwd=root, capture_output=True, text=True)

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def init(self, root):
        self.ok(self.cli(root, 'init', '--yes', '--agent', 'codex'))

    def test_legacy_update_preserves_site_and_installs_missing_guides(self):
        from websmith import __version__
        from websmith.initialize import RULES_ROOT
        with tempfile.TemporaryDirectory(prefix='update sito con spazi ') as directory:
            root = Path(directory)
            self.init(root)
            # Reproduce older, unmodified generated entry points and inventory.
            (root / 'AGENTS.md').write_text('Leggere .websmith/rules.md.\n')
            (root / '.agents/skills/websmith-site/SKILL.md').write_text('Vecchie istruzioni.\n')
            for name in ('EDITORIAL_RULES.md', 'TONE_OF_VOICE.md'):
                (root / name).unlink()
            (root / '.websmith/rules.md').write_text('Regole precedenti.')
            inventory_path = root / '.websmith/installed-files.json'
            inventory = json.loads(inventory_path.read_text())
            for name in ('AGENTS.md', '.agents/skills/websmith-site/SKILL.md'):
                inventory[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            inventory_path.write_text(json.dumps(inventory))
            before = self.snapshot(root)
            output = self.ok(self.cli(root / 'contents', 'update', '--dry-run'))
            self.assertIn('Nessun file modificato', output)
            self.assertEqual(before, self.snapshot(root))
            self.ok(self.cli(root / 'contents', 'update'))
            for name in ('AGENTS.md', 'EDITORIAL_RULES.md', 'TONE_OF_VOICE.md'):
                self.assertEqual((root / name).read_bytes(), (RULES_ROOT / name).read_bytes())
            for name, content in before.items():
                if name.startswith(('contents/', 'templates/')) or name == '.websmith/rules.md':
                    self.assertEqual((root / name).read_bytes(), content)
            marker = json.loads((root / '.websmith/project.json').read_text())
            self.assertEqual(marker['instructions_version'], __version__)
            before = self.snapshot(root)
            self.ok(self.cli(root, 'update'))
            self.assertEqual(before, self.snapshot(root))

    def test_bases_are_refreshed_and_optional_local_files_are_preserved(self):
        from websmith.initialize import BASE_GUIDES, RULES_ROOT
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init(root)
            old_bases = {}
            local_files = {}
            for name in BASE_GUIDES:
                old_bases[name] = f'Vecchia base {name}'.encode()
                (root / name).write_bytes(old_bases[name])
                local_name = name.replace('.md', '.local.md')
                local_files[local_name] = f'Personalizzazione del sito: {name}'.encode()
                (root / local_name).write_bytes(local_files[local_name])
            # Updating bases does not depend on whether an old hash is known.
            inventory_path = root / '.websmith/installed-files.json'
            inventory = json.loads(inventory_path.read_text())
            inventory.pop('TONE_OF_VOICE.md')
            inventory_path.write_text(json.dumps(inventory))
            before = self.snapshot(root)
            self.ok(self.cli(root, 'update', '--dry-run'))
            self.assertEqual(before, self.snapshot(root))
            self.ok(self.cli(root, 'update'))
            for name in BASE_GUIDES:
                self.assertEqual((root / name).read_bytes(), (RULES_ROOT / name).read_bytes())
            for name, content in local_files.items():
                self.assertEqual((root / name).read_bytes(), content)
            backups = list((root / '.websmith/update-backups').rglob('*.md'))
            self.assertEqual({p.name: p.read_bytes() for p in backups}, old_bases)
            self.assertFalse((root / '.websmith/update-proposals').exists())
            before = self.snapshot(root)
            self.ok(self.cli(root, 'update'))
            self.assertEqual(before, self.snapshot(root))

    def test_no_local_files_are_required_or_created(self):
        from websmith.initialize import BASE_GUIDES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init(root)
            self.ok(self.cli(root, 'update'))
            for name in BASE_GUIDES:
                self.assertFalse((root / name.replace('.md', '.local.md')).exists())
            self.assertIn('EDITORIAL_RULES.local.md', (root / 'AGENTS.md').read_text())

    def test_custom_agent_entry_points_still_get_proposals(self):
        from websmith import __version__
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init(root)
            (root / 'AGENTS.md').write_text('Le mie istruzioni')
            output = self.ok(self.cli(root, 'update'))
            self.assertIn('Integrazione manuale necessaria', output)
            self.assertEqual((root / 'AGENTS.md').read_text(), 'Le mie istruzioni')
            proposal = root / f'.websmith/update-proposals/{__version__}/AGENTS.md'
            self.assertTrue(proposal.is_file())
            before = self.snapshot(root)
            self.ok(self.cli(root, 'update'))
            self.assertEqual(before, self.snapshot(root))
            (root / 'AGENTS.md').write_bytes(proposal.read_bytes())
            self.ok(self.cli(root, 'update'))
            marker = json.loads((root / '.websmith/project.json').read_text())
            self.assertNotIn('AGENTS.md', marker['pending_instruction_updates'])
            (root / 'AGENTS.md').write_text('Altra personalizzazione')
            proposal.write_text('La proposta modificata')
            before = self.snapshot(root)
            self.assertEqual(self.cli(root, 'update').returncode, 2)
            self.assertEqual(before, self.snapshot(root))

    def test_bad_metadata_and_uninitialized_site_never_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertNotEqual(self.cli(root, 'update').returncode, 0)
            self.assertEqual(list(root.iterdir()), [])
            self.init(root)
            for value in ('{broken', '[]', '{"format_version": 99, "agent": "codex"}'):
                (root / '.websmith/project.json').write_text(value)
                before = self.snapshot(root)
                self.assertEqual(self.cli(root, 'update').returncode, 2)
                self.assertEqual(before, self.snapshot(root))

    @unittest.skipIf(os.name == 'nt', 'Symlink permissions differ on Windows')
    def test_symlink_targets_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'site'
            root.mkdir()
            self.init(root)
            outside = Path(directory) / 'outside.md'
            outside.write_text('Outside')
            (root / 'TONE_OF_VOICE.md').unlink()
            (root / 'TONE_OF_VOICE.md').symlink_to(outside)
            before = self.snapshot(root)
            self.assertEqual(self.cli(root, 'update').returncode, 2)
            self.assertEqual(before, self.snapshot(root))
            self.assertEqual(outside.read_text(), 'Outside')

    def test_write_failure_restores_files(self):
        from websmith.update import write_plan
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'AGENTS.md').write_text('Original')
            before = self.snapshot(root)
            real_replace = os.replace
            calls = []
            def fail_second(source, target):
                calls.append(target)
                if len(calls) == 2:
                    raise OSError('Simulated failure')
                return real_replace(source, target)
            with patch('websmith.update.os.replace', side_effect=fail_second):
                with self.assertRaises(OSError):
                    write_plan(root, {'AGENTS.md': b'New', 'nested/NEW.md': b'New'})
            self.assertEqual(before, self.snapshot(root))
            self.assertFalse((root / 'nested').exists())
