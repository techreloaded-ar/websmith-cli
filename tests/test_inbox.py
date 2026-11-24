import contextlib
from email.message import EmailMessage
import imaplib
import io
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from websmith import engine, inbox
from test_package import make_site


def mail(subject='[websmith:example] Bozza', attachments=None):
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = 'writer@example.test'
    message['Message-ID'] = '<draft@example.test>'
    message.set_content('Bozza in allegato.')
    for filename, payload in (attachments if attachments is not None else [('story.md', '# Caffè\n\nTesto.'.encode())]):
        message.add_attachment(payload, maintype='text', subtype='markdown', filename=filename)
    return message.as_bytes()


class Mailbox:
    """Return even substring false positives, as an IMAP server can do."""
    def __init__(self, messages, validity=b'123'):
        self.messages = messages
        self.validity = validity
        self.calls = []
        self.logged_out = False

    def login(self, username, password):
        self.credentials = (username, password)
        return 'OK', []

    def select(self, folder, readonly=False):
        self.selected = (folder, readonly)
        return 'OK', [str(len(self.messages)).encode()]

    def response(self, name):
        return name, [self.validity]

    def uid(self, operation, *args):
        self.calls.append((operation, *args))
        if operation == 'SEARCH':
            return 'OK', [' '.join(self.messages).encode()]
        uid, query = args
        raw = self.messages[uid]
        if 'HEADER.FIELDS' in query:
            header = raw.split(b'\n\n', 1)[0] + b'\n\n'
            return 'OK', [(f'1 (UID {uid} RFC822.SIZE {len(raw)} BODY[HEADER.FIELDS (SUBJECT)]'.encode(), header), b')']
        assert 'BODY.PEEK[]' in query, query
        maximum = int(re.search(r'<0\.(\d+)>', query)[1])
        return 'OK', [(f'1 (UID {uid} BODY[]'.encode(), raw[:maximum]), b')']

    def logout(self):
        self.logged_out = True


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        make_site(self.root)
        self.settings = dict(version=1, site_id='example', host='imap.example.test', port=993,
                             username='drafts@example.test', folder='INBOX', password_env='TEST_INBOX_PASSWORD')
        self.write_settings()
        self.args = SimpleNamespace(limit=50, max_message_bytes=10_000_000, timeout=30, dry_run=False)
        self.environment = patch.dict(os.environ, {'TEST_INBOX_PASSWORD': 'not-a-real-secret'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        engine.load_site_config.cache_clear()

    def write_settings(self):
        path = self.root / inbox.CONFIG_PATH
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.settings))

    def fetch(self, box, **overrides):
        args = SimpleNamespace(**(vars(self.args) | overrides))
        output = io.StringIO()
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=box) as factory, contextlib.redirect_stdout(output):
            code = inbox.fetch(self.root, 'example', args)
        return code, output.getvalue(), factory

    def test_site_filter_tls_readonly_and_repeat_download(self):
        box = Mailbox({'1': mail(), '2': mail('[websmith:other] Altro sito'),
                       '3': mail('[websmith:example-old] Altro'),
                       '4': mail('[websmith:example] [websmith:other] Ambiguo'),
                       '5': mail('Senza tag')})
        code, output, factory = self.fetch(box)
        self.assertEqual(code, 0, output)
        self.assertEqual(box.selected, ('"INBOX"', True))
        self.assertEqual(box.credentials, ('drafts@example.test', 'not-a-real-secret'))
        context = factory.call_args.kwargs['ssl_context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertIn(('SEARCH', None, 'SUBJECT', '"[websmith:example]"'), box.calls)
        bodies = [call[1] for call in box.calls if call[0] == 'FETCH' and 'BODY.PEEK[]' in call[2]]
        self.assertEqual(bodies, ['1'])
        files = list((self.root / 'drafts').rglob('*.md'))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), '# Caffè\n\nTesto.')
        files[0].write_text('Modifica editoriale locale')
        self.assertEqual(self.fetch(box)[0], 0)
        self.assertEqual(files[0].read_text(), 'Modifica editoriale locale')
        self.assertEqual(len(list((self.root / 'drafts').rglob('*.md'))), 1)
        self.assertTrue(box.logged_out)
        self.assertNotIn('not-a-real-secret', output)

    def test_same_site_id_in_different_roots_has_no_shared_state(self):
        self.assertEqual(self.fetch(Mailbox({'1': mail()}))[0], 0)
        other = self.root / 'copy'
        other.mkdir()
        make_site(other)
        (other / '.websmith').mkdir()
        (other / inbox.CONFIG_PATH).write_text(json.dumps(self.settings))
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=Mailbox({'1': mail()})), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inbox.fetch(other, 'example', self.args), 0)
        self.assertEqual(len(list((other / 'drafts').rglob('*.md'))), 1)

    def test_account_folder_and_uidvalidity_isolation(self):
        self.fetch(Mailbox({'1': mail()}))
        self.fetch(Mailbox({'1': mail()}, validity=b'124'))
        self.settings['username'] = 'second@example.test'
        self.write_settings()
        self.fetch(Mailbox({'1': mail()}))
        self.settings['folder'] = 'Drafts "quoted"'
        self.write_settings()
        box = Mailbox({'1': mail()})
        self.fetch(box)
        self.assertEqual(box.selected, ('"Drafts \\"quoted\\""', True))
        self.assertEqual(len(list((self.root / 'drafts').rglob('*.md'))), 4)

    def test_filenames_are_contained_unique_and_only_markdown_is_saved(self):
        box = Mailbox({'1': mail(attachments=[('../../escape.md', b'first'), ('..\\escape.md', b'second'),
                                               ('story.md', b'third'), ('story.md', b'fourth'), ('script.sh', b'danger')])})
        self.assertEqual(self.fetch(box)[0], 0)
        files = list((self.root / 'drafts').rglob('*.md'))
        self.assertEqual(len(files), 4)
        self.assertEqual({path.read_text() for path in files}, {'first', 'second', 'third', 'fourth'})
        self.assertFalse((self.root / 'escape.md').exists())
        self.assertFalse(list((self.root / 'drafts').rglob('*.sh')))

    def test_markdown_body_and_encoded_attachment(self):
        message = EmailMessage()
        message['Subject'] = '[websmith:example] Novità'
        message.set_content('# È una bozza', subtype='markdown')
        self.assertEqual(self.fetch(Mailbox({'1': message.as_bytes()}))[0], 0)
        files = list((self.root / 'drafts').rglob('*.md'))
        self.assertIn('# È una bozza', files[0].read_text())
        other = EmailMessage()
        other['Subject'] = '[websmith:example] Charset'
        other.set_content('Testo allegato')
        other.add_attachment('Caffè', subtype='markdown', charset='iso-8859-1', filename='test.markdown')
        self.assertEqual(self.fetch(Mailbox({'2': other.as_bytes()}))[0], 0)
        self.assertIn('Caffè', next((self.root / 'drafts').rglob('*test.md')).read_text())

    def test_oversized_and_broken_attachment_are_retried_without_partial_files(self):
        box = Mailbox({'1': mail()})
        code, output, _ = self.fetch(box, max_message_bytes=10)
        self.assertEqual(code, 1)
        self.assertFalse(any('BODY.PEEK[]' in call[-1] for call in box.calls))
        self.assertFalse((self.root / 'drafts').exists())
        box = Mailbox({'1': mail(attachments=[('good.md', b'good'), ('bad.md', b'\xff\xfe')])})
        self.assertEqual(self.fetch(box)[0], 1)
        self.assertFalse((self.root / 'drafts').exists())
        box.messages['1'] = mail()
        self.assertEqual(self.fetch(box)[0], 0)
        self.assertEqual(len(list((self.root / 'drafts').rglob('*.md'))), 1)

    def test_dry_run_does_not_write_or_fetch_bodies_and_limit_can_resume(self):
        box = Mailbox({'1': mail(), '2': mail()})
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(self.fetch(box, dry_run=True, limit=1)[0], 0)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertFalse(any('BODY.PEEK[]' in call[-1] for call in box.calls))
        self.assertEqual(self.fetch(box, limit=1)[0], 0)
        self.assertEqual(len(list((self.root / 'drafts').rglob('*.md'))), 1)
        self.assertEqual(self.fetch(box, limit=1)[0], 0)
        self.assertEqual(len(list((self.root / 'drafts').rglob('*.md'))), 2)

    def test_invalid_config_and_missing_password_do_not_connect(self):
        for change in ({'site_id': 'other'}, {'port': 0}, {'host': 'https://imap.example.test'},
                       {'folder': 'INBOX\r\nLOGOUT'}, {'password': 'secret'}):
            (self.root / inbox.CONFIG_PATH).write_text(json.dumps(self.settings | change))
            with patch.object(inbox.imaplib, 'IMAP4_SSL') as connect:
                with self.assertRaises(ValueError):
                    inbox.fetch(self.root, 'example', self.args)
                connect.assert_not_called()
        self.write_settings()
        with patch.dict(os.environ, {'TEST_INBOX_PASSWORD': ''}), patch.object(sys.stdin, 'isatty', return_value=False), patch.object(inbox.imaplib, 'IMAP4_SSL') as connect:
            with self.assertRaises(ValueError):
                inbox.fetch(self.root, 'example', self.args)
            connect.assert_not_called()

    def test_auth_failure_does_not_expose_server_diagnostics(self):
        class Rejected(Mailbox):
            def login(self, *args):
                raise imaplib.IMAP4.error('not-a-real-secret: rejected')
        args = SimpleNamespace(site=str(self.root), inbox_action='fetch', **vars(self.args))
        output = io.StringIO()
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=Rejected({})), contextlib.redirect_stdout(output):
            self.assertEqual(inbox.command_inbox(args), 2)
        self.assertIn('Autenticazione', output.getvalue())
        self.assertNotIn('not-a-real-secret', output.getvalue())

    def test_invalid_uidvalidity_and_fetch_failure_leave_no_downloads(self):
        with self.assertRaises(ValueError):
            self.fetch(Mailbox({'1': mail()}, validity=b''))
        class Failed(Mailbox):
            def uid(self, operation, *args):
                if operation == 'FETCH':
                    return 'NO', [b'server diagnostic']
                return super().uid(operation, *args)
        self.assertEqual(self.fetch(Failed({'1': mail()}))[0], 1)
        self.assertFalse((self.root / 'drafts').exists())

    def test_configure_cli_and_site_discovery_from_subdirectory(self):
        result = subprocess.run([sys.executable, '-m', 'websmith', 'inbox', 'configure',
                                 '--host', 'new.example.test', '--username', 'new@example.test'],
                                cwd=self.root / 'contents/en', text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / inbox.CONFIG_PATH).read_text())
        self.assertEqual(data['host'], 'new.example.test')
        self.assertEqual(data['site_id'], 'example')
        self.assertNotIn('password', data)
        if os.name != 'nt':
            self.assertEqual((self.root / inbox.CONFIG_PATH).stat().st_mode & 0o777, 0o600)
        # Reconfiguration can explicitly rebind a copied site's inbox settings.
        data['site_id'] = 'old-site'
        (self.root / inbox.CONFIG_PATH).write_text(json.dumps(data))
        args = engine.build_parser().parse_args(['inbox', 'configure', '--host', 'new.example.test', '--username', 'new@example.test'])
        with patch.object(sys.stdin, 'isatty', return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inbox.configure(self.root, 'example', args), 0)
        self.assertEqual(inbox.read_settings(self.root, 'example')['site_id'], 'example')

    @unittest.skipIf(os.name == 'nt', 'Symlink permissions differ on Windows')
    def test_symlinked_download_path_is_rejected_before_connecting(self):
        outside = self.root / 'elsewhere'
        outside.mkdir()
        (self.root / 'drafts').symlink_to(outside, target_is_directory=True)
        with patch.object(inbox.imaplib, 'IMAP4_SSL') as connect:
            with self.assertRaises(ValueError):
                inbox.fetch(self.root, 'example', self.args)
            connect.assert_not_called()
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
