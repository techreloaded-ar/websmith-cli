import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InitTests(unittest.TestCase):
    def cli(self, root, *args, input=None):
        command = [os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY') else [sys.executable, '-m', 'websmith']
        return subprocess.run([*command, *args], cwd=root, input=input, text=True, capture_output=True)

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_new_site_complete_flow_and_reinitialization(self):
        with tempfile.TemporaryDirectory(prefix='sito con spazi ') as directory:
            root = Path(directory)
            self.ok(self.cli(root, 'init', '--yes', '--name', 'Caffè & Studio', '--agent', 'codex'))
            self.assertTrue((root / '.agents/skills/websmith-site/SKILL.md').is_file())
            self.ok(self.cli(root, 'validate-site'))
            self.ok(self.cli(root, 'validate-pages'))
            source = root / 'contents/it/pages/home.md'
            source.write_text(source.read_text().replace('Sostituisci questo testo con i contenuti del tuo sito.', 'Contenuto scritto da me.'))
            self.ok(self.cli(root, 'render-page', 'home'))
            self.ok(self.cli(root, 'render-root-index'))
            html = (root / 'web/it/index.html').read_text()
            self.assertIn('Contenuto scritto da me.', html)
            self.assertNotIn('Anteprima del contenuto.', html)
            self.assertTrue((root / 'web/shared/css/main.css').is_file())
            before = self.snapshot(root)
            self.ok(self.cli(root, 'init', '--yes'))
            self.assertEqual(before, self.snapshot(root))

    def test_english_and_invalid_initialization_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.ok(self.cli(root, 'init', '--yes', '--language', 'en', '--agent', 'none'))
            self.assertIn('Example page', (root / 'contents/en/pages/home.md').read_text())
            self.ok(self.cli(root, 'render-page', 'home'))
            self.assertTrue((root / 'web/en/index.html').is_file())
            (root / '.websmith/project.json').write_text('{broken')
            before = self.snapshot(root)
            self.assertNotEqual(self.cli(root, 'init', '--yes').returncode, 0)
            self.assertEqual(before, self.snapshot(root))

    def test_existing_site_preserves_guide_and_agent_instructions(self):
        from test_package import make_site
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_site(root)
            (root / 'AGENTS.md').write_text('Existing instructions')
            before = self.snapshot(root)
            self.ok(self.cli(root, 'init', '--yes', '--agent', 'claude'))
            for name, content in before.items():
                self.assertEqual((root / name).read_bytes(), content)
            self.assertTrue((root / '.claude/skills/websmith-site/SKILL.md').is_file())

    def test_nonempty_and_invalid_input_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertNotEqual(self.cli(root, 'init', '--yes', '--id', '../bad').returncode, 0)
            self.assertEqual(list(root.iterdir()), [])
            (root / 'index.html').write_text('Legacy site')
            before = self.snapshot(root)
            self.assertNotEqual(self.cli(root, 'init', '--yes').returncode, 0)
            self.assertEqual(before, self.snapshot(root))

    def test_conflicting_file_and_invalid_manifest_do_not_write(self):
        from test_package import make_site
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_site(root)
            (root / '.websmith').mkdir()
            (root / '.websmith/rules.md').write_text('Local changes')
            before = self.snapshot(root)
            self.assertNotEqual(self.cli(root, 'init', '--yes').returncode, 0)
            self.assertEqual(before, self.snapshot(root))
            (root / '.websmith/rules.md').unlink()
            (root / 'websmith.yaml').write_text('bad: manifest')
            before = self.snapshot(root)
            self.assertNotEqual(self.cli(root, 'init', '--yes').returncode, 0)
            self.assertEqual(before, self.snapshot(root))

    def test_without_tty_requires_explicit_yes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertNotEqual(self.cli(directory, 'init', input='').returncode, 0)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipIf(os.name == 'nt', 'Symlink permissions differ on Windows')
    def test_existing_site_rejects_symlinked_instruction_directory(self):
        from test_package import make_site
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'site'
            root.mkdir()
            make_site(root)
            outside = Path(directory) / 'outside'
            outside.mkdir()
            (root / '.websmith').symlink_to(outside, target_is_directory=True)
            self.assertNotEqual(self.cli(root, 'init', '--yes').returncode, 0)
            self.assertEqual(list(outside.iterdir()), [])
