"""Regression coverage for skill distribution and migration of existing sites."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

from websmith import rule_source
from websmith.instruction_bundle import (
    GUIDE_SOURCES, LEGACY_FILES, SKILL_FILES, SKILL_NAMES, legacy_projections,
)

ROOT = Path(__file__).resolve().parents[1]


class SkillTests(unittest.TestCase):
    def cli(self, root, *args):
        command = ([os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY')
                   else [sys.executable, '-m', 'websmith'])
        return subprocess.run([*command, *args], cwd=root, capture_output=True, text=True)

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def test_skill_metadata_references_and_agent_discovery(self):
        resources = rule_source.local_files(ROOT)
        for agent, directory in [('codex', '.agents'), ('claude', '.claude'), ('none', None)]:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                self.ok(self.cli(root, 'init', '--yes', '--agent', agent, '--offline'))
                for name in SKILL_NAMES:
                    canonical = root / f'skills/{name}/SKILL.md'
                    self.assertEqual(canonical.read_text(), resources[f'skills/{name}/SKILL.md'])
                    metadata = yaml.safe_load(canonical.read_text().split('---', 2)[1])
                    self.assertEqual(set(metadata), {'name', 'description'})
                    self.assertEqual(metadata['name'], name)
                    self.assertTrue(metadata['description'].strip())
                    documents = [canonical]
                    if directory:
                        entry = root / f'{directory}/skills/{name}/SKILL.md'
                        self.assertEqual(yaml.safe_load(entry.read_text().split('---', 2)[1]), metadata)
                        documents.append(entry)
                    for document in documents:
                        for link in re.findall(r'\]\(([^)]+)\)', document.read_text()):
                            self.assertTrue((document.parent / link).is_file(), f'{document}: {link}')
                for name, source in GUIDE_SOURCES.items():
                    self.assertEqual((root / name).read_bytes(), (root / source).read_bytes())
                    self.assertFalse((root / name.replace('.md', '.local.md')).exists())
                if directory:
                    self.assertTrue((root / f'{directory}/skills/websmith-site/SKILL.md').is_file())
                else:
                    self.assertFalse((root / '.agents').exists())
                    self.assertFalse((root / '.claude').exists())

    def test_existing_site_migrates_without_changing_sources_or_local_preferences(self):
        with tempfile.TemporaryDirectory(prefix='legacy site ') as folder:
            root = Path(folder)
            self.ok(self.cli(root, 'init', '--yes', '--agent', 'codex', '--offline'))
            # Reproduce the previous install layout, including known original hashes.
            shutil.rmtree(root / 'skills')
            for name in SKILL_NAMES:
                shutil.rmtree(root / f'.agents/skills/{name}')
            (root / 'AGENTS.md').write_bytes((ROOT / 'src/websmith/resources/rules/AGENTS.md').read_bytes())
            inventory_path = root / '.websmith/installed-files.json'
            inventory = json.loads(inventory_path.read_text())
            inventory = {name: digest for name, digest in inventory.items()
                         if not name.startswith('skills/') and not any(
                             name.startswith(f'.agents/skills/{skill}/') for skill in SKILL_NAMES)}
            inventory['AGENTS.md'] = hashlib.sha256((root / 'AGENTS.md').read_bytes()).hexdigest()
            inventory_path.write_text(json.dumps(inventory))
            for name in GUIDE_SOURCES:
                (root / name.replace('.md', '.local.md')).write_text(f'Preferenze locali: {name}\n')
            self.ok(self.cli(root, 'render-page', 'home'))
            before = self.snapshot(root)
            self.ok(self.cli(root, 'update', '--offline', '--dry-run'))
            self.assertEqual(before, self.snapshot(root))
            self.ok(self.cli(root, 'update', '--offline'))
            after = self.snapshot(root)
            for name, content in before.items():
                if (name.startswith(('contents/', 'templates/', 'web/'))
                        or name == 'websmith.yaml' or name.endswith('.local.md')):
                    self.assertEqual(after[name], content, name)
            for name in SKILL_FILES:
                self.assertEqual(after[name], (ROOT / name).read_bytes())
            self.assertEqual(json.loads((root / '.websmith/project.json').read_text())['pending_instruction_updates'], [])
            self.ok(self.cli(root, 'update', '--offline'))
            self.assertEqual(after, self.snapshot(root))

    def test_custom_skill_is_preserved_and_managed_rules_are_backed_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.ok(self.cli(root, 'init', '--yes', '--agent', 'claude', '--offline'))
            skill = root / 'skills/editor/SKILL.md'
            reference = root / GUIDE_SOURCES['EDITORIAL_RULES.md']
            skill.write_text('Procedura personalizzata da conservare\n')
            reference.write_text('Vecchie regole di base\n')
            self.ok(self.cli(root, 'update', '--offline'))
            self.assertEqual(skill.read_text(), 'Procedura personalizzata da conservare\n')
            proposals = list((root / '.websmith/update-proposals').glob('*/skills/editor/SKILL.md'))
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0].read_bytes(), (ROOT / 'skills/editor/SKILL.md').read_bytes())
            self.assertEqual(reference.read_bytes(), (ROOT / GUIDE_SOURCES['EDITORIAL_RULES.md']).read_bytes())
            backups = list((root / '.websmith/update-backups').glob('*/*/skills/editor/references/EDITORIAL_RULES.md'))
            self.assertEqual([p.read_text() for p in backups], ['Vecchie regole di base\n'])

    def test_legacy_download_paths_remain_complete_and_generated(self):
        resources = ROOT / 'src/websmith/resources'
        for name in LEGACY_FILES:
            self.assertTrue((resources / name).is_file(), name)
        for name, expected in legacy_projections(ROOT).items():
            self.assertEqual((resources / name).read_text(), expected, name)
        # Older agents have no skills/ directory: mail instructions must be inline.
        instructions = (resources / 'rules/AGENTS.md').read_text()
        self.assertIn('.venv/bin/python scripts/check-mail.py --all-messages', instructions)
        self.assertIn('BODY.PEEK', instructions)

    def test_offline_repository_legacy_env_path_and_portable_bundle(self):
        expected = rule_source.local_files(ROOT)
        self.assertEqual(rule_source.local_files(ROOT / 'src/websmith/resources'), expected)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in expected.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
            self.assertEqual(rule_source.local_files(root), expected)

    def test_old_offline_cache_reports_missing_skills_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / 'current.json'
            cache.write_text(json.dumps({'revision': 'old', 'files': {name: '# Old\n' for name in LEGACY_FILES}}))
            before = cache.read_bytes()
            with patch.dict('os.environ', {}, clear=True), patch.object(rule_source, 'cache_root', return_value=root), patch.object(rule_source, 'download') as download:
                with self.assertRaisesRegex(ValueError, 'scaricare anche le skill'):
                    rule_source.load(offline=True)
                download.assert_not_called()
            self.assertEqual(cache.read_bytes(), before)

    def test_both_mail_entry_points_report_missing_credentials_as_json(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder) / 'missing-credentials')
            for script in ('scripts/check-mail.py', 'skills/mail/scripts/check-mail.py'):
                result = subprocess.run([sys.executable, str(ROOT / script), '--all-messages',
                                         '--credentials-file', missing], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output['status'], 'error')
                self.assertEqual(output['error']['code'], 'credentials_unavailable')

    @unittest.skipIf(os.name == 'nt', 'Symlink permissions differ on Windows')
    def test_symlinked_skill_directory_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'site'
            root.mkdir()
            self.ok(self.cli(root, 'init', '--yes', '--agent', 'codex', '--offline'))
            outside = Path(folder) / 'outside'
            outside.mkdir()
            shutil.rmtree(root / 'skills/editor')
            (root / 'skills/editor').symlink_to(outside, target_is_directory=True)
            before = self.snapshot(root)
            result = self.cli(root, 'update', '--offline')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(before, self.snapshot(root))
            self.assertEqual(list(outside.iterdir()), [])
