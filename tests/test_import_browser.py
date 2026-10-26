import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DynamicSite(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/image.svg':
            mime, body = 'image/svg+xml', b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>'
        elif self.path == '/style.css':
            mime, body = 'text/css', b'body { color: rgb(12, 34, 56); }'
        elif self.path == '/denied':
            self.send_error(403)
            return
        elif self.path in {'/', '/second'}:
            mime, body = 'text/html; charset=utf-8', b'''<!doctype html><html><head><link rel="stylesheet" href="/style.css"></head><body><div id="dynamic"></div><form action="/submit"><input></form><script>setTimeout(() => {document.getElementById('dynamic').innerHTML='<h1>Rendered content</h1><img src="/image.svg">';}, 20);</script></body></html>'''
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(os.environ.get('WEBSMITH_BROWSER_TEST') == '1' and os.name != 'nt', 'Real browser integration is opt-in and requires a browser')
class BrowserImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), DynamicSite)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def run_capture(self, root, path='/', single_page=True):
        import pty
        import select
        master, slave = pty.openpty()
        command = [os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY') else [sys.executable, '-m', 'websmith']
        channel = os.environ.get('WEBSMITH_BROWSER_CHANNEL', 'chrome')
        arguments = [*command, 'import', self.url + path, '--browser', '--browser-headless', '--browser-channel', channel]
        if single_page:
            arguments.append('--single-page')
        process = subprocess.Popen(arguments, cwd=root, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        output = b''
        confirmations = 0
        next_pages = 0
        deadline = time.monotonic() + 90
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.2)
                if readable:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    output += chunk
                    if output.count(b'Invio per salvare') > confirmations:
                        os.write(master, b'\n')
                        confirmations += 1
                    if output.count(b'URL della prossima') > next_pages:
                        os.write(master, (self.url + '/second\n').encode() if next_pages == 0 else b'\n')
                        next_pages += 1
                if process.poll() is not None:
                    break
            returncode = process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            os.close(master)
        return returncode, output.decode('utf-8', 'replace')

    def test_rendered_dom_images_screenshot_and_inert_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_capture(directory)
            self.assertEqual(code, 0, output)
            root = Path(directory) / 'imports/127.0.0.1-browser'
            report = json.loads((root / 'report.json').read_text())
            self.assertEqual(report['mode'], 'browser-manual-snapshot')
            page = next(r for r in report['records'] if r['kind'] == 'page')
            rendered = (root / page['rendered']).read_text()
            preview = (root / page['local']).read_text()
            self.assertIn('<h1>Rendered content</h1>', rendered)
            from bs4 import BeautifulSoup
            self.assertIsNone(BeautifulSoup((root / page['original']).read_text(), 'html.parser').find('h1'))
            self.assertNotIn('<script', preview)
            self.assertIn('inert', preview)
            self.assertIn('../assets/', preview)
            self.assertEqual((root / page['screenshot']).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertTrue(any(r['mime'] == 'image/svg+xml' for r in report['records']))

    def test_multiple_pages_share_loaded_images(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_capture(directory, single_page=False)
            self.assertEqual(code, 0, output)
            root = Path(directory) / 'imports/127.0.0.1-browser'
            report = json.loads((root / 'report.json').read_text())
            pages = [r for r in report['records'] if r['kind'] == 'page']
            self.assertEqual(len(pages), 2)
            self.assertTrue(all((root / r['screenshot']).is_file() for r in pages))
            images = [r for r in report['records'] if r['mime'] == 'image/svg+xml']
            self.assertEqual(len(images), 1)

    def test_browser_access_denied_is_not_saved_as_content(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_capture(directory, '/denied')
            self.assertEqual(code, 1, output)
            report = json.loads((Path(directory) / 'imports/127.0.0.1-browser/report.json').read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['records'], [])
            self.assertTrue(any('HTTP 403' in e['reason'] for e in report['events']))
