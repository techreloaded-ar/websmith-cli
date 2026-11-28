import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from websmith import collaboration as c


@unittest.skipUnless(shutil.which('git'), 'Git is required for collaboration')
class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='websmith team ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'websmith-sites.git'
        self.catalog = self.remote
        c.init_repo(self.remote)
        self.giovanni = self.root / 'Giovanni'
        self.marta = self.root / 'Marta'
        self.giovanni.mkdir()
        self.config_g = self.root / 'giovanni.json'
        self.config_m = self.root / 'marta.json'
        self.ok_cli(self.giovanni, 'init', '--yes', '--id', 'miosito', '--name', 'Il mio sito',
                    '--url', 'https://miosito.it', '--agent', 'codex', '--offline')
        self.page = 'contents/it/pages/home.md'
        source = self.giovanni / self.page
        source.write_text(source.read_text().split('## Pagina di esempio')[0] +
                          '## Un sito condiviso\n\n' + '\n'.join(f'Riga {i}.' for i in range(30)) + '\n')
        (self.giovanni / 'TONE_OF_VOICE.local.md').write_text('Voce comune del gruppo.\n')
        (self.giovanni / 'media/shared.bin').write_bytes(b'original\x00image')
        for config, name in [(self.config_g, 'Giovanni'), (self.config_m, 'Marta')]:
            self.ok('configure', config=config, catalog=str(self.catalog), name=name, email=name.lower() + '@example.test')
        self.ok('connect', self.giovanni)
        self.ok('share', self.giovanni)
        self.ok('register', self.giovanni)
        self.ok('open', config=self.config_m, site_id='miosito.it', destination=self.marta)

    def invoke(self, action, root=None, **options):
        values = dict(collaboration_action=action, site_root=root, config=self.config_g,
                      branch='main', name=None, email=None, remote=None, catalog=None,
                      site_id='miosito', destination=None, agent='codex', offline=True,
                      dry_run=False, message=None)
        values.update(options)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = c.command_collaboration(SimpleNamespace(**values))
        return result, output.getvalue()

    def ok(self, *args, **kwargs):
        result, output = self.invoke(*args, **kwargs)
        self.assertEqual(result, 0, output)
        return output

    def ok_cli(self, root, *args):
        command = ([os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY')
                   else [sys.executable, '-m', 'websmith'])
        result = subprocess.run([*command, *map(str, args)], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def head(self, remote=None):
        return c.git('rev-parse', 'refs/heads/main', repo=remote or self.remote).stdout

    def working_files(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
                if p.is_file() and '.websmith' not in p.relative_to(root).parts and '.git' not in p.relative_to(root).parts}

    def edit(self, root, old, new):
        path = root / self.page
        path.write_text(path.read_text().replace(old, new))

    def conflict(self):
        self.edit(self.giovanni, 'Riga 5.', 'Testo di Giovanni.')
        self.edit(self.marta, 'Riga 5.', 'Testo di Marta.')
        self.ok('share', self.giovanni)

    def test_catalog_open_cli_and_noop_sharing(self):
        output = self.ok_cli(self.root, 'collaboration', '--config', self.config_m, 'list')
        self.assertIn('miosito', output)
        self.assertIn('miosito.it', output)
        self.assertEqual((self.marta / 'TONE_OF_VOICE.local.md').read_text(), 'Voce comune del gruppo.\n')
        self.assertTrue((self.marta / '.agents/skills/collaboration/SKILL.md').is_file())
        before = self.head()
        self.ok('share', self.marta)
        self.assertEqual(before, self.head())
        self.assertIn('allineata', self.ok('status', self.marta))
        before = self.working_files(self.marta)
        result, _ = self.invoke('open', config=self.config_m, destination=self.marta)
        self.assertEqual(result, 2)
        self.assertEqual(before, self.working_files(self.marta))

    def test_two_authors_automatic_text_merge_and_dry_run(self):
        self.edit(self.giovanni, 'Riga 2.', 'Giovanni aggiorna l’apertura.')
        self.edit(self.marta, 'Riga 25.', 'Marta aggiorna la chiusura.')
        self.ok('share', self.giovanni)
        before = self.working_files(self.marta)
        old_state = (self.marta / c.STATE).read_bytes()
        remote = self.head()
        self.ok('sync', self.marta, dry_run=True)
        self.assertEqual(before, self.working_files(self.marta))
        self.assertEqual(old_state, (self.marta / c.STATE).read_bytes())
        self.ok('sync', self.marta)
        text = (self.marta / self.page).read_text()
        self.assertIn('Giovanni aggiorna l’apertura.', text)
        self.assertIn('Marta aggiorna la chiusura.', text)
        self.assertEqual(remote, self.head())  # Receiving never sends local edits.
        self.ok('share', self.marta, message='Testo aggiornato insieme')
        self.ok('sync', self.giovanni)
        self.assertEqual((self.giovanni / self.page).read_bytes(), (self.marta / self.page).read_bytes())

    def test_conflict_preserves_all_sources_and_requires_explicit_choice(self):
        self.conflict()
        before = self.working_files(self.marta)
        state = (self.marta / c.STATE).read_bytes()
        remote = self.head()
        result, output = self.invoke('share', self.marta)
        self.assertEqual(result, 1, output)
        self.assertIn(self.page, output)
        self.assertEqual(before, self.working_files(self.marta))
        self.assertEqual(state, (self.marta / c.STATE).read_bytes())
        self.assertEqual(remote, self.head())
        versions = list((self.marta / '.websmith/collaboration/conflicts').glob('*/versions.json'))
        self.assertEqual(len(versions), 1)
        self.assertIn(b'Testo di Marta.', (versions[0].parent / 'local').read_bytes())
        self.assertIn(b'Testo di Giovanni.', (versions[0].parent / 'shared').read_bytes())
        self.ok('resolve', self.marta, path=self.page, use='shared')
        self.ok('sync', self.marta)
        self.assertEqual((self.giovanni / self.page).read_bytes(), (self.marta / self.page).read_bytes())
        backups = list((self.marta / '.websmith/collaboration/backups').glob('*/files/' + self.page))
        self.assertTrue(any(b'Testo di Marta.' in path.read_bytes() for path in backups))

    def test_resolution_is_invalidated_if_either_version_changes(self):
        self.conflict()
        self.ok('resolve', self.marta, path=self.page, use='local')
        self.edit(self.giovanni, 'Testo di Giovanni.', 'Nuovo testo di Giovanni.')
        self.ok('share', self.giovanni)
        before = self.working_files(self.marta)
        result, _ = self.invoke('sync', self.marta)
        self.assertEqual(result, 1)
        self.assertEqual(before, self.working_files(self.marta))

    def test_binary_conflicts_and_deletion_are_handled_without_markers(self):
        (self.giovanni / 'media/shared.bin').unlink()
        (self.marta / 'media/shared.bin').write_bytes(b'Marta\x00binary')
        self.ok('share', self.giovanni)
        result, _ = self.invoke('sync', self.marta)
        self.assertEqual(result, 1)
        self.assertEqual((self.marta / 'media/shared.bin').read_bytes(), b'Marta\x00binary')
        self.ok('resolve', self.marta, path='media/shared.bin', use='shared')
        self.ok('sync', self.marta)
        self.assertFalse((self.marta / 'media/shared.bin').exists())

    def test_generated_output_machine_state_and_secrets_are_not_shared(self):
        (self.giovanni / 'media/.env.local').write_text('NOT-A-REAL-SECRET')
        (self.giovanni / 'media/private.key').write_text('NOT-A-REAL-KEY')
        (self.giovanni / '.websmith/private.json').write_text('personal data')
        (self.giovanni / 'web').mkdir(exist_ok=True)
        (self.giovanni / 'web/index.html').write_text('local preview')
        (self.giovanni / 'media/new.webp').write_bytes(b'new image')
        self.ok('share', self.giovanni)
        tracked = c.git('ls-tree', '-r', '--name-only', 'refs/heads/main', repo=self.remote).stdout.decode()
        self.assertIn('media/new.webp', tracked)
        self.assertNotIn('.env', tracked)
        self.assertNotIn('.key', tracked)
        self.assertNotIn('.websmith/', tracked)
        self.assertNotIn('web/index.html', tracked)
        self.ok('sync', self.marta)
        self.assertEqual((self.marta / 'media/new.webp').read_bytes(), b'new image')
        self.assertFalse((self.marta / 'media/.env.local').exists())

    def test_validation_blocks_invalid_content_before_upload(self):
        before = self.head()
        source = self.marta / self.page
        source.write_text(source.read_text().replace('slug: home\n', ''))
        content = source.read_bytes()
        state = (self.marta / c.STATE).read_bytes()
        result, output = self.invoke('share', self.marta)
        self.assertEqual(result, 2, output)
        self.assertIn('correzioni', output)
        self.assertEqual(before, self.head())
        self.assertEqual(content, source.read_bytes())
        self.assertEqual(state, (self.marta / c.STATE).read_bytes())

    def test_existing_user_git_index_and_branch_are_untouched(self):
        subprocess.run(['git', 'init', str(self.giovanni)], capture_output=True, check=True)
        subprocess.run(['git', '-C', str(self.giovanni), 'add', self.page], capture_output=True, check=True)
        index = (self.giovanni / '.git/index').read_bytes()
        head = (self.giovanni / '.git/HEAD').read_bytes()
        self.edit(self.giovanni, 'Riga 5.', 'Un’altra revisione.')
        self.ok('share', self.giovanni)
        self.assertEqual(index, (self.giovanni / '.git/index').read_bytes())
        self.assertEqual(head, (self.giovanni / '.git/HEAD').read_bytes())

    def test_concurrent_remote_upload_is_rejected_without_changing_local_files(self):
        self.edit(self.marta, 'Riga 20.', 'Marta condivide.')
        before = self.working_files(self.marta)
        state = (self.marta / c.STATE).read_bytes()
        original_git = c.git
        injected = False
        def racing_git(*args, **kwargs):
            nonlocal injected
            if args and args[0] == 'push' and not injected:
                injected = True
                self.edit(self.giovanni, 'Riga 1.', 'Giovanni arriva prima.')
                self.ok('share', self.giovanni)
            return original_git(*args, **kwargs)
        with patch.object(c, 'git', side_effect=racing_git):
            result, output = self.invoke('share', self.marta)
        self.assertEqual(result, 2, output)
        self.assertIn('cambiata', output)
        self.assertEqual(before, self.working_files(self.marta))
        self.assertEqual(state, (self.marta / c.STATE).read_bytes())
        self.ok('share', self.marta)
        self.ok('sync', self.giovanni)
        self.assertIn('Marta condivide.', (self.giovanni / self.page).read_text())
        self.assertIn('Giovanni arriva prima.', (self.marta / self.page).read_text())

    def test_open_does_not_overwrite_existing_destination(self):
        before = self.working_files(self.marta)
        result, output = self.invoke('open', config=self.config_m, destination=self.marta)
        self.assertEqual(result, 2, output)
        self.assertEqual(before, self.working_files(self.marta))

    def test_failed_application_restores_sources_and_state(self):
        (self.giovanni / 'media/shared.bin').unlink()
        self.edit(self.giovanni, 'Riga 2.', 'Nuova apertura.')
        self.ok('share', self.giovanni)
        before = self.working_files(self.marta)
        state = (self.marta / c.STATE).read_bytes()
        original_unlink = Path.unlink
        failed = False
        def fail_once(path, *args, **kwargs):
            nonlocal failed
            if path == (self.marta / 'media/shared.bin').resolve() and not failed:
                failed = True
                raise OSError('simulated write failure')
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_once):
            result, output = self.invoke('sync', self.marta)
        self.assertEqual(result, 2, output)
        self.assertTrue(failed)
        self.assertEqual(before, self.working_files(self.marta))
        self.assertEqual(state, (self.marta / c.STATE).read_bytes())
        self.ok('sync', self.marta)
        self.assertFalse((self.marta / 'media/shared.bin').exists())
        self.assertIn('Nuova apertura.', (self.marta / self.page).read_text())

    def test_files_outside_site_sources_remain_in_remote_repository(self):
        remote = self.head().decode().strip()
        commit = c.commit_snapshot(self.remote, remote, {}, {'README.txt': b'Team notes'},
                                   name='Admin', email='admin@example.test', message='Repository notes')
        c.git('update-ref', 'refs/heads/main', commit, repo=self.remote)
        self.edit(self.marta, 'Riga 15.', 'Contenuto aggiornato.')
        self.ok('share', self.marta)
        head = self.head().decode().strip()
        self.assertEqual(c.blob(self.remote, head, 'README.txt'), b'Team notes')
        self.assertFalse((self.marta / 'README.txt').exists())

    def test_two_sites_share_one_repository_without_overwriting_each_other(self):
        other = self.root / 'Altro sito'
        other.mkdir()
        self.ok_cli(other, 'init', '--yes', '--id', 'altro', '--name', 'Altro sito',
                    '--url', 'https://altro.test', '--agent', 'none', '--offline')
        self.ok('connect', other)
        site_tree = c.git('rev-parse', 'refs/heads/main:sites/miosito', repo=self.remote).stdout
        self.ok('share', other)
        self.assertEqual(c.git('rev-parse', 'refs/heads/main:sites/miosito', repo=self.remote).stdout, site_tree)
        self.ok('register', other)
        output = self.ok('list')
        self.assertIn('miosito', output)
        self.assertIn('altro', output)
        catalog_before = c.git('show', 'refs/heads/main:sites.json', repo=self.remote).stdout
        other_tree = c.git('rev-parse', 'refs/heads/main:sites/altro', repo=self.remote).stdout
        self.assertIn('allineata', self.ok('status', self.marta))
        self.edit(self.marta, 'Riga 9.', 'Marta modifica solo miosito.')
        self.ok('share', self.marta)
        self.assertEqual(c.git('rev-parse', 'refs/heads/main:sites/altro', repo=self.remote).stdout, other_tree)
        self.assertEqual(c.git('show', 'refs/heads/main:sites.json', repo=self.remote).stdout, catalog_before)
        self.assertFalse((self.marta / 'sites').exists())
        self.assertFalse((self.marta / 'sites.json').exists())
        opened = self.root / 'Marta altro'
        self.ok('open', config=self.config_m, site_id='altro', destination=opened)
        self.assertEqual(c.state_for(opened)['path'], 'sites/altro')
        self.assertNotIn('Marta modifica solo miosito.', (opened / self.page).read_text())
        content = c.git('show', 'refs/heads/main:sites/miosito/' + self.page, repo=self.remote).stdout.decode()
        self.assertIn('Marta modifica solo miosito.', content)

    def test_source_deletion_in_one_site_preserves_sibling_site(self):
        remote = self.head().decode().strip()
        marker = {'sites/altro/marker.txt': b'Keep the other site'}
        commit = c.commit_snapshot(self.remote, remote, {}, marker, name='Admin',
                                   email='admin@example.test', message='Other site')
        c.git('update-ref', 'refs/heads/main', commit, repo=self.remote)
        (self.giovanni / 'media/shared.bin').unlink()
        self.ok('share', self.giovanni)
        self.assertEqual(c.git('show', 'refs/heads/main:sites/altro/marker.txt', repo=self.remote).stdout,
                         b'Keep the other site')
        self.assertFalse(c.has_blob(self.remote, self.head().decode().strip(), 'sites/miosito/media/shared.bin'))

    @unittest.skipIf(os.name == 'nt', 'POSIX symlinks')
    def test_symlink_and_remote_failure_preserve_sources(self):
        outside = self.root / 'outside.txt'
        outside.write_text('Outside source')
        (self.marta / 'media/link.txt').symlink_to(outside)
        before = self.head()
        result, _ = self.invoke('share', self.marta)
        self.assertEqual(result, 2)
        self.assertEqual(before, self.head())
        self.assertEqual(outside.read_text(), 'Outside source')
        (self.marta / 'media/link.txt').unlink()
        c.git('config', 'remote.unused.url', 'https://example.test', repo=self.marta / c.REPO)
        state = json.loads((self.marta / c.STATE).read_text())
        state['remote'] = str(self.root / 'absent.git')
        (self.marta / c.STATE).write_bytes(c.encoded(state))
        before = self.working_files(self.marta)
        result, output = self.invoke('sync', self.marta)
        self.assertEqual(result, 2, output)
        self.assertEqual(before, self.working_files(self.marta))


class CollaborationInputTests(unittest.TestCase):
    def test_site_paths_cannot_overlap_or_escape_their_site(self):
        self.assertEqual(c.site_directory('miosito'), 'sites/miosito')
        for path in ('sites/altro', 'sites', '../outside', '/outside', 'sites/miosito/child', ''):
            with self.subTest(path=path), self.assertRaises(c.CollaborationError):
                c.site_directory('miosito', path)

    def test_remote_helpers_inline_credentials_and_path_traversal_are_rejected(self):
        for value in ('ext::sh -c something', '--upload-pack=anything',
                      'https://user:secret@example.test/repo', 'https://example.test/repo?token=secret'):
            with self.subTest(value=value), self.assertRaises(c.CollaborationError):
                c.remote_address(value)
        for value in ('../outside', '/outside', '.git/config', 'a/../../outside', 'a\\b', 'a\nfile'):
            with self.subTest(value=value):
                if value == '.git/config':
                    self.assertTrue(c.private_path(value))
                else:
                    with self.assertRaises(c.CollaborationError):
                        c.relative_name(value)
