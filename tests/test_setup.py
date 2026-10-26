import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipIf(os.name == "nt", "Bash installer targets macOS and Linux")
class SetupTests(unittest.TestCase):
    def run_setup(self, corrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools = root / 'tools'
            tools.mkdir()
            fixtures = root / 'fixtures'
            fixtures.mkdir()
            archive = fixtures / 'websmith-darwin-arm64.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('websmith', '#!/bin/sh\necho "websmith test"\n')
            digest = 'bad' if corrupt else hashlib.sha256(archive.read_bytes()).hexdigest()
            (fixtures / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
            commands = {
                'uname': '#!/bin/sh\nif [ "$1" = -s ]; then echo Darwin; else echo arm64; fi\n',
                'gh': '#!/bin/sh\nexit 1\n',
                'curl': '#!/bin/bash\nurl=""; out=""\nwhile [ "$#" -gt 0 ]; do\ncase "$1" in https:*) url="$1";; -o) shift; out="$1";; esac\nshift\ndone\ncp "$FIXTURES/${url##*/}" "$out"\n',
            }
            for name, content in commands.items():
                p = tools / name
                p.write_text(content)
                p.chmod(0o755)
            destination = root / 'destination with spaces'
            destination.mkdir()
            binary = destination / 'websmith'
            binary.write_text('previous version')
            result = subprocess.run(['bash', str(ROOT / 'setup.sh')], env={**os.environ, 'PATH': f'{tools}:{os.environ["PATH"]}', 'FIXTURES': str(fixtures), 'WEBSMITH_INSTALL_DIR': str(destination)}, capture_output=True, text=True)
            if corrupt:
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(binary.read_text(), 'previous version')
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('websmith test', binary.read_text())

    def test_install(self):
        self.run_setup()

    def test_bad_checksum_preserves_previous_version(self):
        self.run_setup(corrupt=True)
