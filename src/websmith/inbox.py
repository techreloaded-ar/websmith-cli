"""Retrieve site-tagged Markdown drafts over read-only IMAP/TLS."""
from __future__ import annotations

import getpass
import hashlib
import imaplib
import json
import math
import os
from pathlib import Path
import re
import shutil
import ssl
import sys
import tempfile
from email import policy
from email.errors import MessageError
from email.parser import BytesParser
from email.utils import getaddresses

import certifi

CONFIG_PATH = '.websmith/inbox.json'
DEFAULT_PASSWORD_ENV = 'WEBSMITH_MAIL_PASSWORD'
TECHRELOADED_ADDRESS = 'trtalks@techreloaded.it'
SHARED_MAILBOX = dict(host='mail.techreloaded.it', port=993,
                      username=TECHRELOADED_ADDRESS, recipient=TECHRELOADED_ADDRESS)
PROFILES = {
    'shared': SHARED_MAILBOX,
    'techreloaded': SHARED_MAILBOX,  # Compatibility alias; not a site-specific account.
}
SITE_TAG = re.compile(r'\[websmith:([^\]\r\n]+)\]', re.IGNORECASE)


def local_path(root: Path, relative: str) -> Path:
    """Do not follow links for either configuration or incoming files."""
    path = root
    for part in Path(relative).parts:
        if part in {'..', '/'}:
            raise ValueError('Percorso inbox non valido.')
        path /= part
        if path.is_symlink():
            raise ValueError('I percorsi inbox non possono contenere link simbolici.')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Il percorso inbox deve essere interno al sito.')
    return path


def validate_settings(data: dict, site_id: str) -> dict:
    fields = {'version', 'site_id', 'host', 'port', 'username', 'folder', 'password_env'}
    if not isinstance(data, dict) or not fields <= set(data) or set(data) - fields - {'recipient'} or data.get('version') != 1:
        raise ValueError('Configurazione inbox non valida: eseguire inbox configure. Non salvare password nel file.')
    if data['site_id'] != site_id:
        raise ValueError('La configurazione inbox appartiene a un altro sito: eseguire inbox configure.')
    for key in ('host', 'username', 'folder', 'password_env'):
        value = data[key]
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f'Impostazione inbox non valida: {key}.')
    if not re.fullmatch(r'[a-zA-Z0-9._:-]+', data['host']):
        raise ValueError('Indicare il nome del server IMAP, senza URL o credenziali.')
    if type(data['port']) is not int or not 1 <= data['port'] <= 65535:
        raise ValueError('La porta IMAP deve essere compresa tra 1 e 65535.')
    if not data['folder'].isascii():
        raise ValueError('Usare un nome cartella IMAP ASCII (o codificato in modified UTF-7).')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', data['password_env']):
        raise ValueError('Nome della variabile per la password non valido.')
    recipient = data.get('recipient', '')
    if not isinstance(recipient, str) or (recipient and not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", recipient
    )):
        raise ValueError('Destinatario inbox non valido: indicare un solo indirizzo email.')
    # Enforce the recipient restriction also for older TechReloaded settings.
    if data['username'].lower() == TECHRELOADED_ADDRESS and recipient.lower() not in ('', TECHRELOADED_ADDRESS):
        raise ValueError(f'La casella {TECHRELOADED_ADDRESS} richiede lo stesso destinatario.')
    return data


def read_settings(root: Path, site_id: str, *, rebind: bool = False) -> dict:
    path = local_path(root, CONFIG_PATH)
    if not path.is_file():
        raise ValueError('Casella non configurata: eseguire websmith inbox configure.')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('Configurazione inbox illeggibile.') from None
    return validate_settings(data, data.get('site_id') if rebind and isinstance(data, dict) else site_id)


def configure(root: Path, site_id: str, args) -> int:
    path = local_path(root, CONFIG_PATH)
    previous = read_settings(root, site_id, rebind=True) if path.exists() else {}
    profile = PROFILES.get(getattr(args, 'profile', None), {})

    def setting(name, label, default=None):
        supplied = getattr(args, name, None)
        if supplied is not None:
            return supplied
        value = profile.get(name, previous.get(name, default))
        if sys.stdin.isatty():
            entered = input(f'{label}' + (f' [{value}]' if value is not None else '') + ': ').strip()
            return entered or value
        if value is None:
            raise ValueError(f'Indicare --{name.replace("_", "-")} oppure usare un terminale interattivo.')
        return value

    port = setting('port', 'Porta IMAP TLS', 993)
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError('Porta IMAP non valida.') from None
    username = setting('username', 'Username', SHARED_MAILBOX['username'])
    data = validate_settings(dict(
        version=1, site_id=site_id,
        host=setting('host', 'Server IMAP', SHARED_MAILBOX['host']), port=port,
        username=username,
        recipient=setting('recipient', 'Destinatario da filtrare', username if '@' in username else ''),
        folder=setting('folder', 'Cartella', 'INBOX'),
        password_env=setting('password_env', 'Variabile password', DEFAULT_PASSWORD_ENV),
    ), site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.inbox-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    print(f'Casella configurata per {site_id}. Oggetto richiesto: [websmith:{site_id}]')
    print(f"IMAP TLS: {data['host']}:{data['port']}; account: {data['username']}; destinatario: {recipient_for(data) or 'non impostato'}.")
    print('La password non viene salvata; verrà letta dalla variabile configurata o richiesta al download.')
    return 0


def password_for(settings: dict) -> str:
    password = os.environ.get(settings['password_env'])
    if not password:
        if not sys.stdin.isatty():
            raise ValueError('Password mancante: impostare la variabile configurata o usare un terminale interattivo.')
        password = getpass.getpass('Password IMAP (o password per applicazioni): ')
    if not password or '\r' in password or '\n' in password or '\0' in password:
        raise ValueError('Password IMAP vuota o non valida.')
    return password


def quote(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def checked(result, operation: str):
    status, data = result
    if status != 'OK':
        raise ValueError(f'Operazione IMAP non riuscita: {operation}.')
    return data


def literal(data, maximum: int) -> tuple[bytes, bytes]:
    parts = [item for item in data if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], bytes)]
    if len(parts) != 1 or len(parts[0][1]) > maximum:
        raise ValueError('Risposta IMAP assente o oltre il limite previsto.')
    return parts[0]


def belongs_to_site(message, site_id: str) -> bool:
    subjects = message.get_all('Subject', [])
    return len(subjects) == 1 and SITE_TAG.findall(str(subjects[0]).lower()) == [site_id]


def recipient_for(settings: dict) -> str:
    if settings['username'].lower() == TECHRELOADED_ADDRESS:
        return TECHRELOADED_ADDRESS
    return settings.get('recipient', '').lower()


def addressed_to(message, recipient: str) -> bool:
    if not recipient:
        return True  # Legacy configurations without a recipient filter.
    headers = [str(value) for name in ('To', 'Cc') for value in message.get_all(name, [])]
    return any(address.lower() == recipient for _, address in getaddresses(headers))


def markdown_files(message) -> list[tuple[str, bytes]]:
    """Extract Markdown files and explicit text/markdown bodies; ignore attached emails."""
    files = []

    def visit(part):
        if part.get_content_maintype() == 'message':
            return
        if part.is_multipart():
            for child in part.iter_parts():
                visit(child)
            return
        filename = part.get_filename()
        if filename:
            if Path(filename).suffix.lower() not in {'.md', '.markdown'}:
                return
        elif part.get_content_type() != 'text/markdown':
            return
        payload = part.get_payload(decode=True)
        if not payload:
            raise ValueError('Allegato Markdown vuoto o non decodificabile.')
        try:
            text = payload.decode(part.get_content_charset() or 'utf-8')
        except (UnicodeError, LookupError):
            raise ValueError('Codifica Markdown non valida: usare UTF-8 o dichiarare il charset MIME.') from None
        if not text.strip() or '\0' in text:
            raise ValueError('Allegato Markdown vuoto o contenente dati binari.')
        # Never use a sender-controlled directory or filename directly.
        basename = (filename or 'draft.md').replace('\\', '/').rsplit('/', 1)[-1]
        stem = re.sub(r'[^a-zA-Z0-9._-]+', '-', Path(basename).stem).strip('.-')[:100] or 'draft'
        files.append((f'{len(files) + 1:02d}-{stem}.md', text.encode('utf-8')))

    visit(message)
    return files


def save_message(root: Path, relative: str, files: list[tuple[str, bytes]], metadata: dict):
    destination = local_path(root, relative)
    if destination.exists():
        raise ValueError('La destinazione della bozza esiste già: nessun file sovrascritto.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.download-', dir=destination.parent))
    try:
        for filename, content in files:
            (temporary / filename).write_bytes(content)
        (temporary / 'message.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def fetch(root: Path, site_id: str, args) -> int:
    settings = read_settings(root, site_id)
    recipient = recipient_for(settings)
    if args.limit < 1 or args.max_message_bytes < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('Limiti e timeout devono essere positivi e finiti.')
    # Validate output before connecting, even when no message will be saved.
    local_path(root, 'drafts/inbox')
    scope = hashlib.sha256(json.dumps([
        settings['host'].lower(), settings['port'], settings['username'], settings['folder'], site_id,
    ]).encode()).hexdigest()[:20]
    context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or certifi.where())
    password = password_for(settings)
    connection = None
    downloaded = duplicates = ignored = failures = pending = 0
    try:
        connection = imaplib.IMAP4_SSL(settings['host'], settings['port'], ssl_context=context, timeout=args.timeout)
        try:
            checked(connection.login(settings['username'], password), 'login')
        except imaplib.IMAP4.error:
            raise ValueError('Autenticazione IMAP fallita: verificare username e password (eventualmente per applicazioni).') from None
        checked(connection.select(quote(settings['folder']), readonly=True), 'apertura cartella in sola lettura')
        _, validity_data = connection.response('UIDVALIDITY')
        if not validity_data or not isinstance(validity_data[0], bytes) or not re.fullmatch(rb'[1-9][0-9]*', validity_data[0]):
            raise ValueError('UIDVALIDITY mancante o non valida: download interrotto per evitare duplicati.')
        validity = validity_data[0].decode('ascii')
        criteria = ['SUBJECT', quote(f'[websmith:{site_id}]')]
        if recipient:
            criteria.extend(['OR', 'TO', quote(recipient), 'CC', quote(recipient)])
        results = checked(connection.uid('SEARCH', None, *criteria), 'ricerca per sito e destinatario')
        uids = b' '.join(item for item in results if isinstance(item, bytes)).split()
        if any(not re.fullmatch(rb'[1-9][0-9]*', uid) for uid in uids):
            raise ValueError('Identificativi IMAP non validi.')
        for uid_bytes in dict.fromkeys(uids):
            uid = uid_bytes.decode('ascii')
            relative = f'drafts/inbox/{scope}/{validity}-{uid}'
            destination = local_path(root, relative)
            if destination.exists():
                if not local_path(root, relative + '/message.json').is_file():
                    raise ValueError('Destinazione inbox incompleta: spostarla prima di ripetere il download.')
                duplicates += 1
                continue
            if downloaded + pending + failures >= args.limit:
                print('Limite per esecuzione raggiunto; ripetere inbox fetch per continuare.')
                break
            try:
                headers = checked(connection.uid('FETCH', uid, '(UID RFC822.SIZE BODY.PEEK[HEADER.FIELDS (SUBJECT TO CC)])'), 'lettura intestazioni')
                response, header = literal(headers, 65536)
                message_headers = BytesParser(policy=policy.default).parsebytes(header)
                if not belongs_to_site(message_headers, site_id) or not addressed_to(message_headers, recipient):
                    ignored += 1
                    continue
                size_match = re.search(rb'RFC822.SIZE\s+(\d+)', response)
                if not size_match or not 0 < int(size_match[1]) <= args.max_message_bytes:
                    raise ValueError('Messaggio oltre il limite di dimensione o dimensione non disponibile.')
                if args.dry_run:
                    pending += 1
                    print(f'UID {uid}: messaggio del sito da esaminare (allegati non scaricati).')
                    continue
                size = int(size_match[1])
                body = checked(connection.uid('FETCH', uid, f'(UID BODY.PEEK[]<0.{size}>)'), 'download messaggio')
                _, raw = literal(body, size)
                if len(raw) != size:
                    raise ValueError('Download del messaggio incompleto.')
                message = BytesParser(policy=policy.default).parsebytes(raw)
                if not belongs_to_site(message, site_id) or not addressed_to(message, recipient):
                    raise ValueError('Il messaggio scaricato non corrisponde al sito o al destinatario.')
                files = markdown_files(message)
                if not files:
                    ignored += 1
                    print(f'UID {uid}: nessun allegato Markdown o corpo text/markdown.')
                    continue
                save_message(root, relative, files, dict(
                    site_id=site_id, uid=uid, uidvalidity=validity,
                    recipient=recipient,
                    message_id=str(message.get('Message-ID', '')),
                    subject=str(message.get('Subject', '')), sender=str(message.get('From', '')),
                    date=str(message.get('Date', '')), files=[name for name, _ in files],
                ))
                downloaded += 1
                print(f'Salvati {len(files)} file Markdown in {relative}/')
            except MessageError:
                failures += 1
                print(f'UID {uid}: struttura MIME non valida.')
            except ValueError as exc:
                failures += 1
                print(f'UID {uid}: {exc}')
        print(f'Messaggi salvati: {downloaded}; già presenti: {duplicates}; ignorati: {ignored}; errori: {failures}.'
              + (f' Da esaminare: {pending}.' if args.dry_run else ''))
        return 1 if failures else 0
    finally:
        if connection is not None:
            try:
                connection.logout()
            except (OSError, imaplib.IMAP4.error):
                pass


def command_inbox(args) -> int:
    from .engine import load_site_config
    try:
        site = load_site_config(args.site)
        site_id = str(site.data['site']['id'])
        if args.inbox_action == 'configure':
            return configure(site.root, site_id, args)
        return fetch(site.root, site_id, args)
    except (OSError, imaplib.IMAP4.error):
        # Server diagnostics can echo credentials. Never print them.
        print('Connessione IMAP/TLS o accesso ai file non riuscito. Verificare rete, server, certificato e permessi.')
        return 2
    except (ValueError, EOFError) as exc:
        print(f'Inbox: {exc}' if isinstance(exc, ValueError) else 'Configurazione interrotta: input terminato.')
        return 2


def add_parser(subparsers):
    parser = subparsers.add_parser('inbox', help='Configura la casella e scarica le bozze Markdown del sito corrente')
    parser.set_defaults(site=None)
    actions = parser.add_subparsers(dest='inbox_action', required=True)
    setup = actions.add_parser('configure', help='Imposta server IMAP TLS e username per questo sito, senza salvare la password')
    setup.add_argument('--profile', choices=sorted(PROFILES), help='Parametri precompilati della casella; site.id resta quello del sito corrente')
    setup.add_argument('--host', help='Server IMAP TLS, senza schema URL')
    setup.add_argument('--port', type=int, help='Porta TLS; predefinita 993')
    setup.add_argument('--username', help='Username della casella')
    setup.add_argument('--recipient', help='Destinatario esatto in To o Cc; predefinito lo username se è un indirizzo email')
    setup.add_argument('--folder', help='Cartella IMAP; predefinita INBOX')
    setup.add_argument('--password-env', help=f'Variabile da cui leggere la password; predefinita {DEFAULT_PASSWORD_ENV}')
    setup.set_defaults(func=command_inbox)
    download = actions.add_parser('fetch', help='Scarica gli allegati .md/.markdown o corpi text/markdown contrassegnati per il sito')
    download.add_argument('--limit', type=int, default=50, help='Massimo messaggi salvati, segnalati con errore o elencati in dry-run; predefinito 50')
    download.add_argument('--max-message-bytes', type=int, default=10_000_000, help='Dimensione massima di una email; predefinita 10 MB')
    download.add_argument('--timeout', type=float, default=30, help='Timeout connessione in secondi; predefinito 30')
    download.add_argument('--dry-run', action='store_true', help='Controlla oggetti e destinatari dei messaggi nuovi, senza scaricare allegati o scrivere file')
    download.set_defaults(func=command_inbox)
