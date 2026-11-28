"""Read-only shared mailbox reader with structured JSON output."""
from __future__ import annotations

import argparse
from email import policy
from email.errors import MessageError
from email.parser import BytesParser
import imaplib
import json
import math
import os
from pathlib import Path
import re
import socket
import ssl

import certifi

from . import inbox


class CheckError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def password_from_file(path: Path) -> str:
    """Accept the supplied notes format without printing or copying its secrets."""
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        raise CheckError('credentials_unavailable', 'File delle credenziali assente o illeggibile.') from None
    # Provider setup notes can say "Password: Usa la password dell'account".
    # That is an instruction, not a credential. Read all supported labels and
    # reject conflicting actual passwords instead of guessing or retrying them.
    candidates = re.findall(r'(?im)^\s*(?:password|passwd|pwd)\s*:[ \t]*(\S[^\r\n]*)$', text)
    instruction = re.compile(
        r"(?i)^(?:(?:usa|utilizza|inserisci)\s+la\s+password\b|"
        r"(?:use|enter)\s+(?:the|your)\s+password\b|"
        r"(?:la\s+)?password\s+dell['’]account\b)"
    )
    passwords = [value.strip() for value in candidates if not instruction.match(value.strip())]
    users = re.findall(r'(?im)^\s*(?:Nome utente|username)\s*:[ \t]*(\S[^\r\n]*)$', text)
    if users and any(user.strip().lower() != inbox.TECHRELOADED_ADDRESS for user in users):
        raise CheckError('credentials_invalid', 'Il file non identifica la casella condivisa autorizzata.')
    if not passwords or len(set(passwords)) != 1 or any(c in passwords[0] for c in '\r\n\0'):
        raise CheckError('credentials_invalid', 'Password assente, non valida o ambigua nel file delle credenziali.')
    return passwords[0]


def attachment_info(message) -> list[dict]:
    """List all attachment types, without interpreting attached emails as messages."""
    attachments = []

    def visit(part):
        filename = part.get_filename()
        disposition = part.get_content_disposition()
        if filename is not None or disposition == 'attachment':
            payload = part.get_payload(decode=True)
            attachments.append(dict(filename=filename, content_type=part.get_content_type(),
                                    size_bytes=len(payload) if payload is not None else None,
                                    disposition=disposition))
        elif part.is_multipart():
            for child in part.iter_parts():
                visit(child)

    visit(message)
    return attachments


def read_messages(args, result: dict) -> None:
    all_messages = getattr(args, 'all_messages', False)
    limit = args.limit if args.limit is not None else (None if all_messages else 20)
    if (limit is not None and limit < 1) or args.max_message_bytes < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise CheckError('invalid_options', 'Limiti e timeout devono essere positivi e finiti.')
    if all_messages:
        site_id = None
    elif args.site_id:
        site_id = args.site_id
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', site_id):
            raise CheckError('invalid_site', 'siteId non valido.')
    else:
        from .engine import load_site_config
        try:
            site_id = str(load_site_config(args.site_root).data['site']['id'])
        except (ValueError, OSError):
            raise CheckError('invalid_site', 'Manifest del sito assente o non valido; indicare --site-root o --site-id.') from None
    result['site_id'] = site_id
    password = password_from_file(args.credentials_file)
    context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or certifi.where())
    mailbox = result['mailbox']
    connection = None
    try:
        connection = imaplib.IMAP4_SSL(mailbox['host'], mailbox['port'], ssl_context=context, timeout=args.timeout)
        try:
            inbox.checked(connection.login(mailbox['username'], password), 'login')
        except (imaplib.IMAP4.error, ValueError):
            raise CheckError('authentication_failed', 'Autenticazione della casella condivisa non riuscita.') from None
        finally:
            password = None
        inbox.checked(connection.select(inbox.quote('INBOX'), readonly=True), 'apertura cartella')
        recipient = inbox.TECHRELOADED_ADDRESS
        criteria = ('ALL',) if all_messages else (
            'SUBJECT', inbox.quote(f'[websmith:{site_id}]'),
            'OR', 'TO', inbox.quote(recipient), 'CC', inbox.quote(recipient))
        found = inbox.checked(connection.uid('SEARCH', None, *criteria), 'ricerca messaggi')
        uids = b' '.join(value for value in found if isinstance(value, bytes)).split()
        if any(not re.fullmatch(rb'[1-9][0-9]*', uid) for uid in uids):
            raise CheckError('invalid_response', 'Identificativi IMAP non validi.')
        counts = result['counts']
        counts.update(candidates=len(set(uids)), examined=0, ignored=0, returned=0)
        # Explicit --all-messages has no count limit unless --limit is supplied.
        selected = sorted(set(uids), key=int, reverse=True)[:limit]
        result['has_more_candidates'] = len(set(uids)) > len(selected)
        for uid_bytes in selected:
            uid = uid_bytes.decode('ascii')
            counts['examined'] += 1
            try:
                headers = inbox.checked(connection.uid('FETCH', uid,
                    '(UID RFC822.SIZE BODY.PEEK[HEADER.FIELDS (SUBJECT TO CC FROM DATE MESSAGE-ID)])'), 'lettura intestazioni')
                response, raw_headers = inbox.literal(headers, 65536)
                message = BytesParser(policy=policy.default).parsebytes(raw_headers)
                if not all_messages and (not inbox.belongs_to_site(message, site_id) or not inbox.addressed_to(message, recipient)):
                    counts['ignored'] += 1
                    continue
                entry = dict(uid=uid, subject=str(message.get('Subject', '')),
                             sender=str(message.get('From', '')), to=str(message.get('To', '')),
                             cc=str(message.get('Cc', '')), date=str(message.get('Date', '')),
                             message_id=str(message.get('Message-ID', '')),
                             attachments=None, attachment_count=None)
                if not args.headers_only:
                    match = re.search(rb'RFC822.SIZE\s+(\d+)', response)
                    if not match or not 0 < int(match[1]) <= args.max_message_bytes:
                        raise ValueError('Dimensione del messaggio assente o oltre il limite.')
                    size = int(match[1])
                    body = inbox.checked(connection.uid('FETCH', uid, f'(UID BODY.PEEK[]<0.{size}>)'), 'lettura messaggio')
                    _, raw = inbox.literal(body, size)
                    if len(raw) != size:
                        raise ValueError('Messaggio incompleto.')
                    message = BytesParser(policy=policy.default).parsebytes(raw)
                    if not all_messages and (not inbox.belongs_to_site(message, site_id) or not inbox.addressed_to(message, recipient)):
                        raise ValueError('Messaggio non corrispondente al sito o al destinatario.')
                    entry['attachments'] = attachment_info(message)
                    entry['attachment_count'] = len(entry['attachments'])
                    body_part = message.get_body(preferencelist=('plain', 'html'))
                    text = body_part.get_content() if body_part is not None else ''
                    entry['body'] = dict(content_type=body_part.get_content_type() if body_part else None,
                                         content=text[:100000], truncated=len(text) > 100000)
                    entry['markdown_files'] = []
                    remaining = 100000
                    for name, content in inbox.markdown_files(message):
                        markdown = content.decode('utf-8')
                        entry['markdown_files'].append(dict(name=name, content=markdown[:remaining], truncated=len(markdown) > remaining))
                        remaining = max(0, remaining - len(markdown))
                result['messages'].append(entry)
                counts['returned'] += 1
            except (ValueError, imaplib.IMAP4.error, LookupError, MessageError):
                result['message_errors'].append(dict(uid=uid, code='message_unreadable',
                    message='Impossibile leggere o validare questo messaggio; nessun contenuto restituito.'))
        result['ok'] = not result['message_errors']
        result['status'] = 'ok' if result['ok'] else 'partial'
    finally:
        if connection is not None:
            try:
                connection.logout()
            except (OSError, imaplib.IMAP4.error):
                pass


def check(args) -> tuple[dict, int]:
    result = dict(schema_version=1, ok=False, status='error', site_id=args.site_id,
                  scope='all_messages' if getattr(args, 'all_messages', False) else 'site',
                  mailbox=dict(host=inbox.SHARED_MAILBOX['host'], port=inbox.SHARED_MAILBOX['port'],
                               username=inbox.TECHRELOADED_ADDRESS, folder='INBOX'),
                  read_only=True, headers_only=args.headers_only, content_is_untrusted=True,
                  messages=[], message_errors=[], counts=dict(candidates=None, examined=0, ignored=0, returned=0))
    try:
        read_messages(args, result)
        return result, 0 if result['ok'] else 1
    except CheckError as exc:
        code, message = exc.code, str(exc)
    except socket.gaierror:
        code, message = 'dns_error', 'Impossibile risolvere mail.techreloaded.it dall’ambiente corrente.'
    except (TimeoutError, socket.timeout):
        code, message = 'timeout', 'Tempo di connessione o lettura IMAP scaduto.'
    except ssl.SSLError:
        code, message = 'tls_error', 'Connessione TLS o verifica del certificato non riuscita.'
    except PermissionError:
        code, message = 'permission_denied', 'Accesso ai file o alla rete negato dall’ambiente corrente.'
    except OSError:
        code, message = 'network_error', 'Connessione al server IMAP non riuscita.'
    except (ValueError, imaplib.IMAP4.error):
        code, message = 'imap_error', 'Risposta IMAP non valida o operazione non riuscita.'
    result.update(ok=False, status='error', error=dict(code=code, message=message))
    return result, 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Legge la casella condivisa trtalks e restituisce un unico oggetto JSON per Codex.')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--all-messages', action='store_true', help='Legge tutti i messaggi di INBOX della sola casella condivisa, senza filtri site.id o destinatario')
    scope.add_argument('--site-id', help='site.id esplicito per prove senza manifest')
    scope.add_argument('--site-root', help='Cartella del sito; altrimenti cerca il manifest dalla cartella corrente')
    parser.add_argument('--credentials-file', type=Path, default=Path(__file__).resolve().parents[2] / 'docs' / inbox.TECHRELOADED_ADDRESS)
    parser.add_argument('--limit', type=int, help='Massimo messaggi esaminati; senza limite con --all-messages, altrimenti 20')
    parser.add_argument('--max-message-bytes', type=int, default=10000000)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--headers-only', action='store_true', help='Legge solo le intestazioni, senza corpi o allegati')
    result, code = check(parser.parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
