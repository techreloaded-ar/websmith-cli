import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from websmith import self_update as updater


def release(tag='v0.1.0a9'):
    names = ['websmith-darwin-arm64.zip', 'SHA256SUMS']
    return {'tag_name': tag, 'draft': False, 'prerelease': True,
            'assets': [{'name': name, 'browser_download_url': f'https://github.com/{updater.REPOSITORY}/releases/download/{tag}/{name}'} for name in names]}


class SelfUpdateTests(unittest.TestCase):
    def test_version_order_and_release_selection_including_prereleases(self):
        self.assertGreater(updater.version_key('0.1.0a10'), updater.version_key('v0.1.0a9'))
        self.assertGreater(updater.version_key('0.1.0'), updater.version_key('0.1.0rc2'))
        self.assertGreater(updater.version_key('0.2.0a1'), updater.version_key('0.1.0'))
        data = [release('v0.1.0a3'), release('v0.1.0a10'), dict(release('v9.0.0'), draft=True)]
        with patch.object(updater, 'download', return_value=json.dumps(data).encode()):
            self.assertEqual(updater.latest_release()['tag_name'], 'v0.1.0a10')
        with self.assertRaises(ValueError):
            updater.version_key('latest; arbitrary-command')

    def test_same_or_newer_local_version_never_downloads_or_installs(self):
        for local, remote in [('0.1.0a9', 'v0.1.0a9'), ('0.1.0a10', 'v0.1.0a9')]:
            with self.subTest(local=local), patch.object(updater, '__version__', local), patch.object(updater, 'latest_release', return_value=release(remote)), patch.object(updater, 'verified_binary') as fetch, patch.object(updater, 'install_binary') as install:
                self.assertIsNone(updater.update_program(SimpleNamespace(dry_run=False), Path('/site')))
                fetch.assert_not_called()
                install.assert_not_called()

    def test_dry_run_only_checks_release_metadata(self):
        with patch.object(updater, '__version__', '0.1.0a8'), patch.object(updater, 'latest_release', return_value=release()), patch.object(updater, 'platform_asset', return_value=('websmith-darwin-arm64.zip', 'websmith')), patch.object(updater, 'verified_binary') as fetch, patch.object(updater, 'install_binary') as install:
            self.assertIsNone(updater.update_program(SimpleNamespace(dry_run=True), Path('/site')))
            fetch.assert_not_called()
            install.assert_not_called()

    def test_checksum_archive_and_download_urls(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('websmith', b'new executable')
            archive.writestr('../outside', b'must never be extracted')
        payload = output.getvalue()
        checksum = hashlib.sha256(payload).hexdigest().encode() + b'  websmith-darwin-arm64.zip\n'
        with patch.object(updater, 'platform_asset', return_value=('websmith-darwin-arm64.zip', 'websmith')):
            with patch.object(updater, 'download', side_effect=[checksum, payload]):
                self.assertEqual(updater.verified_binary(release()), b'new executable')
            with patch.object(updater, 'download', side_effect=[b'0' * 64 + b'  websmith-darwin-arm64.zip\n', payload]):
                with self.assertRaisesRegex(ValueError, 'Checksum non valido'):
                    updater.verified_binary(release())
        bad = release()
        bad['assets'][0]['browser_download_url'] = 'https://untrusted.example/binary'
        with self.assertRaises(ValueError):
            updater.release_asset_url(bad, 'websmith-darwin-arm64.zip')

    @unittest.skipIf(os.name == 'nt', 'POSIX atomic replacement')
    def test_install_verifies_before_swap_and_restores_on_failed_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'websmith'
            target.write_bytes(b'original')
            target.chmod(0o755)
            with patch.object(updater, 'binary_version', return_value='0.1.0a9'):
                updater.install_binary(target, b'new', 'v0.1.0a9')
            self.assertEqual(target.read_bytes(), b'new')
            with patch.object(updater, 'binary_version', side_effect=['0.1.0a10', ValueError('restart failed')]):
                with self.assertRaises(ValueError):
                    updater.install_binary(target, b'broken restart', 'v0.1.0a10')
            self.assertEqual(target.read_bytes(), b'new')
            with patch.object(updater, 'binary_version', return_value='0.1.0a3'):
                with self.assertRaises(ValueError):
                    updater.install_binary(target, b'wrong', 'v0.1.0a10')
            self.assertEqual(target.read_bytes(), b'new')

    @unittest.skipIf(os.name == 'nt', 'POSIX executable verification')
    def test_real_candidate_startup_and_atomic_install(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'websmith'
            target.write_bytes(b'#!/bin/sh\nprintf "websmith 0.1.0a8\\n"\n')
            target.chmod(0o755)
            candidate = b'#!/bin/sh\nprintf "websmith 0.1.0a9\\n"\n'
            updater.install_binary(target, candidate, 'v0.1.0a9')
            self.assertEqual(updater.binary_version(target), '0.1.0a9')

    @unittest.skipIf(os.name == 'nt', 'POSIX handoff')
    def test_new_program_handoff_updates_rules_from_new_executable(self):
        with patch.object(updater, '__version__', '0.1.0a8'), patch.object(updater, 'latest_release', return_value=release()), patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater.sys, 'executable', '/tmp/websmith'), patch.object(updater, 'verified_binary', return_value=b'new'), patch.object(updater, 'install_binary') as install, patch.object(updater.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            root = Path('/tmp/site with spaces')
            self.assertEqual(updater.update_program(SimpleNamespace(dry_run=False), root), 0)
            install.assert_called_once_with(Path('/tmp/websmith').resolve(), b'new', 'v0.1.0a9')
            self.assertEqual(run.call_args.args[0], [str(Path('/tmp/websmith').resolve()), '--site-root', str(root), 'update'])
            self.assertEqual(run.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')

    def test_network_failure_does_not_touch_site(self):
        from websmith.initialize import agent_files, install_files, starter
        from websmith.update import command_update
        from websmith import __version__
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            files = agent_files('none')
            files.update(starter('Example', 'example', 'https://example.test', 'it'))
            files['.websmith/project.json'] = json.dumps({'format_version': 1, 'agent': 'none', 'websmith_version': __version__})
            files['.websmith/installed-files.json'] = json.dumps({name: hashlib.sha256(value.encode()).hexdigest() for name, value in files.items()})
            install_files(root, files)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(updater, 'latest_release', side_effect=OSError('network unavailable')):
                self.assertEqual(command_update(SimpleNamespace(site_root=root, offline=False, dry_run=False)), 2)
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})
