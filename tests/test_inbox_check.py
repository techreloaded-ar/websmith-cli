import contextlib
from email.message import EmailMessage
import imaplib
import io
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from websmith import inbox, inbox_check
from test_inbox import Mailbox, mail
from test_package import make_site


class InboxCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.credentials = self.root / 'credentials'
        self.credentials.write_text('uid: trtalks\npasswd: current-test-password\n'
            'Nome utente: trtalks@techreloaded.it\nPassword: Usa la password dell’account email.\n')
        self.args = SimpleNamespace(site_id='example', site_root=None, credentials_file=self.credentials,
            limit=20, max_message_bytes=10000000, timeout=15, headers_only=False)

    def check(self, box):
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=box) as connect:
            result, code = inbox_check.check(self.args)
        return result, code, connect

    def test_password_ignores_provider_instruction_and_reads_passwd(self):
        self.assertEqual(inbox_check.password_from_file(self.credentials), 'current-test-password')
        self.credentials.write_text('Nome utente: trtalks@techreloaded.it\nPassword: only-test-password\n')
        self.assertEqual(inbox_check.password_from_file(self.credentials), 'only-test-password')

    def test_instruction_only_and_conflicting_passwords_do_not_connect(self):
        for content in ('Password: Usa la password dell’account email.\n',
                        'passwd: one-test-password\nPassword: another-test-password\n'):
            self.credentials.write_text(content)
            result, code, connect = self.check(Mailbox({}))
            self.assertEqual(code, 2)
            self.assertEqual(result['error']['code'], 'credentials_invalid')
            connect.assert_not_called()

    def test_shared_mailbox_readonly_body_and_markdown_with_exact_site_filter(self):
        address = inbox.TECHRELOADED_ADDRESS
        box = Mailbox({'1': mail(recipient=address),
                       '2': mail('[websmith:other] Altra bozza', recipient=address),
                       '3': mail(recipient=f'"{address}" <personal@example.test>'),
                       '4': mail('[websmith:example-old] Altro sito', recipient=address)})
        result, code, connect = self.check(box)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['mailbox']['username'], address)
        self.assertEqual(box.credentials, (address, 'current-test-password'))
        self.assertEqual(box.selected, ('"INBOX"', True))
        context = connect.call_args.kwargs['ssl_context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(result['counts'], dict(candidates=4, examined=4, ignored=3, returned=1))
        self.assertEqual(result['messages'][0]['body']['content'].strip(), 'Bozza in allegato.')
        self.assertEqual(result['messages'][0]['markdown_files'][0]['content'], '# Caffè\n\nTesto.')
        bodies = [call[1] for call in box.calls if call[0] == 'FETCH' and 'BODY.PEEK[]' in call[2]]
        self.assertEqual(bodies, ['1'])
        self.assertTrue(box.logged_out)
        self.assertEqual(set(self.root.iterdir()), {self.credentials})

    def test_site_manifest_is_used_and_headers_only_does_not_read_bodies(self):
        make_site(self.root)
        self.args.site_id = None
        self.args.site_root = str(self.root)
        self.args.headers_only = True
        result, code, _ = self.check(Mailbox({'1': mail(recipient=inbox.TECHRELOADED_ADDRESS)}))
        self.assertEqual(code, 0, result)
        self.assertEqual(result['site_id'], 'example')
        self.assertNotIn('body', result['messages'][0])
        self.assertIsNone(result['messages'][0]['attachments'])
        self.assertTrue(result['headers_only'])

    def test_all_messages_mode_reads_untagged_and_other_sites_and_lists_all_attachments(self):
        self.args.site_id = None
        self.args.all_messages = True
        self.args.limit = None
        message = EmailMessage()
        message['Subject'] = 'Messaggio senza tag'
        message['From'] = 'writer@example.test'
        message.set_content('Due allegati.')
        message.add_attachment(b'%PDF-test', maintype='application', subtype='pdf', filename='report.pdf')
        message.add_attachment(b'# Bozza', maintype='text', subtype='markdown', filename='story.md')
        box = Mailbox({'1': message.as_bytes(),
                       '2': mail('[websmith:other] Altro sito'),
                       '3': mail('Altro messaggio senza tag', attachments=[])})
        result, code, _ = self.check(box)
        self.assertEqual(code, 0, result)
        self.assertEqual(result['scope'], 'all_messages')
        self.assertIsNone(result['site_id'])
        self.assertEqual(result['counts']['returned'], 3)
        self.assertEqual(result['counts']['ignored'], 0)
        self.assertIn(('SEARCH', None, 'ALL'), box.calls)
        by_uid = {entry['uid']: entry for entry in result['messages']}
        self.assertEqual(by_uid['1']['attachment_count'], 2)
        self.assertEqual(by_uid['1']['attachments'][0], dict(filename='report.pdf',
            content_type='application/pdf', size_bytes=9, disposition='attachment'))
        self.assertEqual(by_uid['1']['attachments'][1]['filename'], 'story.md')
        self.assertEqual(by_uid['3']['attachments'], [])
        self.assertEqual(by_uid['3']['attachment_count'], 0)
        self.assertEqual(box.selected, ('"INBOX"', True))
        self.assertEqual(box.credentials[0], inbox.TECHRELOADED_ADDRESS)

    def test_all_messages_cli_has_no_implicit_twenty_message_limit(self):
        box = Mailbox({str(uid): mail('Senza tag') for uid in range(1, 23)})
        output = io.StringIO()
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=box), contextlib.redirect_stdout(output):
            code = inbox_check.main(['--all-messages', '--headers-only', '--credentials-file', str(self.credentials)])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result['messages']), 22)
        self.assertFalse(result['has_more_candidates'])
        self.assertFalse(any('BODY.PEEK[]' in call[-1] for call in box.calls))

    def test_dns_and_auth_errors_have_json_codes_without_leaking_credentials(self):
        with patch.object(inbox.imaplib, 'IMAP4_SSL', side_effect=socket.gaierror('current-test-password')):
            result, code = inbox_check.check(self.args)
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'dns_error')
        self.assertFalse(result['ok'])
        self.assertIsNone(result['counts']['candidates'])
        self.assertNotIn('current-test-password', json.dumps(result))

        class Rejected(Mailbox):
            def login(self, *args):
                raise imaplib.IMAP4.error('current-test-password rejected')

        box = Rejected({})
        result, code, _ = self.check(box)
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'authentication_failed')
        self.assertNotIn('current-test-password', json.dumps(result))
        self.assertTrue(box.logged_out)

    def test_invalid_scope_and_credentials_do_not_connect(self):
        self.args.site_id = 'bad\r\nSEARCH ALL'
        result, code, connect = self.check(Mailbox({}))
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'invalid_site')
        connect.assert_not_called()
        self.args.site_id = 'example'
        self.credentials.write_text('Nome utente: personal@example.test\nPassword: test-password\n')
        result, code, connect = self.check(Mailbox({}))
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'credentials_invalid')
        connect.assert_not_called()
        self.credentials.unlink()
        result, code, connect = self.check(Mailbox({}))
        self.assertEqual(code, 2)
        self.assertEqual(result['error']['code'], 'credentials_unavailable')
        connect.assert_not_called()

    def test_empty_inbox_is_success_and_limit_reports_remaining_candidates(self):
        result, code, _ = self.check(Mailbox({}))
        self.assertEqual(code, 0)
        self.assertEqual(result['counts']['candidates'], 0)
        self.assertEqual(result['messages'], [])
        self.args.limit = 1
        box = Mailbox({'1': mail(recipient=inbox.TECHRELOADED_ADDRESS),
                       '2': mail(recipient=inbox.TECHRELOADED_ADDRESS)})
        result, code, _ = self.check(box)
        self.assertEqual(code, 0)
        self.assertTrue(result['has_more_candidates'])
        self.assertEqual(result['messages'][0]['uid'], '2')

    def test_bad_message_returns_partial_and_no_unvalidated_content(self):
        box = Mailbox({'1': mail(attachments=[('bad.md', b'\xff\xfe')], recipient=inbox.TECHRELOADED_ADDRESS)})
        result, code, _ = self.check(box)
        self.assertEqual(code, 1)
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['messages'], [])
        self.assertEqual(result['message_errors'][0]['uid'], '1')

    def test_main_outputs_only_json(self):
        output = io.StringIO()
        with patch.object(inbox.imaplib, 'IMAP4_SSL', return_value=Mailbox({})), contextlib.redirect_stdout(output):
            code = inbox_check.main(['--site-id', 'example', '--credentials-file', str(self.credentials)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'ok')
        self.assertNotIn('current-test-password', output.getvalue())

    def test_script_runs_from_any_directory_and_errors_are_json(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/check-mail.py'
        result = subprocess.run([sys.executable, str(script), '--site-id', 'example',
            '--credentials-file', str(self.root / 'missing')], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'credentials_unavailable')


if __name__ == '__main__':
    unittest.main()
