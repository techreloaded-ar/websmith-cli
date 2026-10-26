"""User-confirmed browser snapshots, not an unattended crawler or anti-bot bypass."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from .import_web import Importer, normalize, origin, web_reference


def browser_environment():
    """Use the persistent user cache, not PyInstaller's temporary extraction directory."""
    if 'PLAYWRIGHT_BROWSERS_PATH' not in os.environ:
        if sys.platform == 'darwin':
            cache = Path.home() / 'Library/Caches/ms-playwright'
        elif sys.platform == 'win32':
            cache = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'ms-playwright'
        else:
            cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'ms-playwright'
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(cache)


class BrowserImporter(Importer):
    def __init__(self, args, directory, confirm=input):
        super().__init__(args, directory)
        self.confirm = confirm
        self.responses = {}
        self.documents = {}
        self.page = None
        self.cancelled = False

    def observe(self, response):
        try:
            url = normalize(response.url)
            request = response.request
            if request.method != 'GET':
                return
            if request.resource_type == 'document' and response.frame == self.page.main_frame:
                self.documents[url] = response
            elif request.resource_type in {'image', 'stylesheet', 'font', 'script', 'media'}:
                if len(self.responses) < self.args.max_assets * 4 or url in self.responses:
                    self.responses[url] = response
                else:
                    self.event(url, 'Limite risposte browser da conservare raggiunto', 'warning')
        except Exception:
            # A response can outlive its detached frame. It cannot be captured reliably.
            return

    def bounded(self, data, label):
        if len(data) > self.args.max_file_bytes or self.total + len(data) > self.args.max_total_bytes:
            raise ValueError(f'Limite dei byte salvati raggiunto: {label}')
        self.total += len(data)
        return data

    def body(self, response):
        length = response.headers.get('content-length', '')
        if length.isdigit() and int(length) > self.args.max_file_bytes:
            raise ValueError(f'Risorsa troppo grande: {response.url}')
        return self.bounded(response.body(), response.url)

    def asset(self, url, depth=0):
        if url in self.records or url in self.attempted_assets:
            return
        if self.assets >= self.args.max_assets or depth > 6:
            self.event(url, 'Limite risorse o annidamento CSS raggiunto')
            return
        response = self.responses.get(url)
        if response is None:
            self.event(url, 'Risorsa non caricata dal browser: nessun download aggiuntivo tentato', 'warning')
            return
        self.attempted_assets.add(url)
        self.assets += 1
        if response.status >= 400:
            self.event(url, f'Risorsa negata dal server: HTTP {response.status}', 'error')
            return
        if response.status < 200 or response.status >= 300:
            # Find the successful final response of a resource redirect.
            request = response.request.redirected_to
            if request is not None:
                target = web_reference(url, request.url)
                if target:
                    self.aliases[url] = target
                    self.asset(target, depth + 1)
            return
        try:
            content_type = response.headers.get('content-type', 'application/octet-stream')
            mime = content_type.split(';')[0].strip()
            if mime in {'text/html', 'application/xhtml+xml'}:
                self.event(url, 'Risorsa HTML non salvata come immagine o asset', 'warning')
                return
            match = re.search(r'charset=([^;\s]+)', content_type, re.I)
            record = self.store(url, normalize(response.url), self.body(response), (mime, match.group(1).strip('"\'') if match else 'utf-8'), 'asset')
            self.events = [event for event in self.events if not (event['url'] == url and event['reason'].startswith('Risorsa non caricata dal browser'))]
            if mime == 'text/css':
                for reference in self.css_references(self.text(record), url):
                    self.asset(reference, depth + 1)
        except Exception as exc:
            self.event(url, f'Risorsa non salvata: {exc}', 'error')

    def text(self, record):
        if record.get('rendered'):
            return (self.directory / record['rendered']).read_text(encoding='utf-8')
        return super().text(record)

    def capture(self, requested):
        final = normalize(self.page.url)
        if self.scope and origin(final) != self.scope:
            raise ValueError('La pagina confermata è fuori dal sito selezionato')
        if final in self.records:
            self.event(final, 'Pagina già acquisita in questa sessione: copia precedente preservata', 'warning')
            return
        response = self.documents.get(final)
        if response is None or response.status < 200 or response.status >= 300:
            status = response.status if response else 'sconosciuto'
            raise ValueError(f'La pagina non è acquisibile: HTTP {status}. Verifica nel browser che non sia una pagina di blocco.')
        content_type = response.headers.get('content-type', '')
        if not any(value in content_type for value in ('text/html', 'application/xhtml+xml')):
            raise ValueError('La pagina confermata non è HTML')
        self.scope = origin(final)
        dom = self.page.content().encode('utf-8')
        raw = self.body(response)
        self.bounded(dom, 'HTML renderizzato')
        match = re.search(r'charset=([^;\s]+)', content_type, re.I)
        record = self.store(requested, final, raw, ('text/html', match.group(1).strip('"\'') if match else 'utf-8'), 'page')
        key = hashlib.sha256(final.encode()).hexdigest()[:24]
        record['rendered'] = f'rendered/{key}.html'
        rendered = self.directory / record['rendered']
        rendered.parent.mkdir(exist_ok=True)
        rendered.write_bytes(dom)
        soup = BeautifulSoup(dom.decode('utf-8'), 'html.parser')
        base_tag = soup.find('base', href=True)
        record['base'] = web_reference(final, str(base_tag['href'])) if base_tag else final
        record['base'] = record['base'] or final
        for reference in self.html_references(soup, record['base']):
            self.asset(reference)
        # Include images/fonts/CSS actually requested dynamically even without a DOM reference.
        for url, resource in list(self.responses.items()):
            if resource.request.resource_type in {'image', 'font', 'stylesheet'}:
                self.asset(url)
        if soup.find('canvas'):
            self.event(final, 'Canvas conservati nello screenshot, non convertiti automaticamente in immagini', 'warning')
        if soup.find(src=re.compile(r'^blob:')):
            self.event(final, 'Risorse blob presenti: usare screenshot e verificare le immagini mancanti', 'warning')
        try:
            height = min(20000, max(1, self.page.evaluate('document.documentElement.scrollHeight')))
            width = min(1440, max(1, self.page.evaluate('document.documentElement.clientWidth')))
            shot = self.page.screenshot(type='png', clip=dict(x=0, y=0, width=width, height=height), timeout=self.args.timeout * 1000)
            self.bounded(shot, 'screenshot')
            record['screenshot'] = f'screenshots/{key}.png'
            target = self.directory / record['screenshot']
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(shot)
            if self.page.evaluate('document.documentElement.scrollHeight') > height:
                self.event(final, 'Screenshot limitato ai primi 20000 pixel di altezza', 'warning')
        except Exception as exc:
            self.event(final, f'Screenshot non salvato: {exc}', 'warning')
        print(f'Pagina salvata: {final}', flush=True)

    def crawl(self, seed):
        browser_environment()
        from playwright.sync_api import Error, TimeoutError, sync_playwright
        with sync_playwright() as playwright:
            channel = None if self.args.browser_channel == 'chromium' else self.args.browser_channel
            try:
                browser = playwright.chromium.launch(channel=channel, headless=self.args.browser_headless)
            except Error as exc:
                raise ValueError('Browser non disponibile. Installa Google Chrome oppure esegui websmith browser-install e usa --browser-channel chromium. Dettaglio: ' + str(exc).splitlines()[0]) from exc
            try:
                context = browser.new_context(viewport=dict(width=1440, height=1000), accept_downloads=False)
                self.page = context.new_page()
                self.page.on('response', self.observe)
                current = seed
                for index in range(self.args.max_pages):
                    try:
                        self.page.goto(current, wait_until='domcontentloaded', timeout=self.args.timeout * 1000)
                    except TimeoutError:
                        self.event(current, 'Caricamento iniziale oltre il timeout: attendere e verificare nella finestra', 'warning')
                    except Error as exc:
                        self.event(current, f'Navigazione non riuscita: {exc}', 'error')
                        break
                    if self.scope is None:
                        self.scope = origin(normalize(self.page.url))
                    print('Verifica la pagina nella finestra dedicata. Scorri per caricare le immagini; completa eventuali verifiche del sito. Websmith non le risolve automaticamente.', flush=True)
                    try:
                        action = self.confirm('Invio per salvare la pagina visibile; q per terminare: ').strip().lower()
                    except EOFError:
                        action = 'q'
                    if action == 'q':
                        self.cancelled = True
                        break
                    # Let queued response events drain; no routing pauses the user's browsing.
                    self.page.wait_for_timeout(750)
                    try:
                        self.capture(current)
                    except (ValueError, Error) as exc:
                        self.event(current, str(exc), 'error')
                    if self.args.single_page:
                        break
                    try:
                        next_url = self.confirm('URL della prossima pagina (Invio termina): ').strip()
                    except EOFError:
                        next_url = ''
                    if not next_url:
                        break
                    current = normalize(next_url)
                    if origin(current) != self.scope:
                        self.event(current, 'Pagina fuori dal sito selezionato', 'error')
                        break
                    if index + 1 == self.args.max_pages:
                        self.event(current, 'Numero massimo di pagine raggiunto')
            except Error as exc:
                self.event(current, f'Finestra browser non più disponibile: {exc}', 'error')
            finally:
                try:
                    browser.close()
                except Error:
                    pass

    def previews(self):
        super().previews()
        for record in self.records.values():
            if record['kind'] != 'page':
                continue
            target = self.directory / record['local']
            soup = BeautifulSoup(target.read_text(encoding='utf-8'), 'html.parser')
            for tag in list(soup.find_all('script')):
                tag.decompose()
            for tag in soup.find_all(True):
                for name in list(tag.attrs):
                    if name.lower().startswith('on'):
                        del tag.attrs[name]
                if tag.name == 'form':
                    tag['inert'] = ''
                    tag.attrs.pop('action', None)
                if tag.name == 'iframe':
                    tag.attrs.pop('src', None)
                    tag.attrs.pop('srcdoc', None)
                if tag.name == 'meta' and str(tag.get('http-equiv', '')).lower() == 'refresh':
                    tag.decompose()
                    continue
                if str(tag.get('href', '')).strip().lower().startswith('javascript:'):
                    tag['href'] = '#'
            target.write_text(str(soup), encoding='utf-8')

    def report(self, seed):
        pages, errors = super().report(seed)
        path = self.directory / 'report.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        report['mode'] = 'browser-manual-snapshot'
        report['cancelled'] = self.cancelled
        report['limits_apply_to'] = 'saved files; not all browser network traffic'
        report['limitations'][0] = 'Salvataggio manuale delle pagine visibili: JavaScript eseguito nel browser, disattivato nell’anteprima. Nessuna navigazione automatica.'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        path = self.directory / 'REPORT.md'
        text = path.read_text(encoding='utf-8').replace('L’anteprima conserva script e moduli del sito: aprendola il browser può contattare servizi esterni.', 'L’anteprima disattiva script, moduli e iframe. Risorse non acquisite e collegamenti esterni possono ancora richiedere Internet.')
        text += '\n## Acquisizione browser manuale\n\nrendered/ contiene l’HTML dopo JavaScript; screenshots/ contiene il riferimento visivo.\noriginals/ conserva le risposte acquisite dal browser. Immagini e CSS salvati sono anche in preview/assets/.\nI limiti di byte e risorse riguardano i file salvati, non tutto il traffico generato dalla navigazione manuale.\nNessun cookie o profilo browser è esportato. Risorse non caricate, canvas e blob possono richiedere lavoro manuale.\nIl salvataggio riguarda pagine confermate dall’operatore, non un crawler; il download HTTP ordinario continua a rispettare robots.txt.\n'
        path.write_text(text, encoding='utf-8')
        return pages, errors


def command_browser_install(args):
    # Use the bundled Playwright driver, including when Python itself is frozen.
    browser_environment()
    from playwright._impl._driver import compute_driver_executable, get_driver_env
    node, cli = compute_driver_executable()
    command = ['--version'] if args.check else ['install', 'chromium']
    return subprocess.call([str(node), str(cli), *command], env=get_driver_env())
