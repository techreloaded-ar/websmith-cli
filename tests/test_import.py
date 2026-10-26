import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class SiteHandler(BaseHTTPRequestHandler):
    visits = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        type(self).visits.append(self.path)
        routes = {
            '/robots.txt': ('text/plain', b'User-agent: *\nDisallow: /blocked\n'),
            '/': ('text/html; charset=utf-8', b'''<html><head><base href="/"><link rel="stylesheet" href="/main.css" integrity="sha256-example"></head><body><h1>Original title</h1><img src="/image.png" srcset="/image.png 1x, /image.png?v=2 2x"><a href="/second#section">Second</a><a href="/blocked">Blocked</a><a href="https://example.invalid/external">External</a><form action="/submit"></form><script src="/app.js"></script></body></html>'''),
            '/second': ('text/html', b'<html><body id="section">Second page<a href="/third">Third</a><img src="/image.png"></body></html>'),
            '/third': ('text/html', b'<html><body>Third page</body></html>'),
            '/blocked': ('text/html', b'Forbidden by robots'),
            '/main.css': ('text/css', b'@import "/nested.css"; body { background: url("/image.png"); }'),
            '/nested.css': ('text/css', b'@font-face { src: url("/font.woff2"); }'),
            '/image.png': ('image/png', b'original-image-bytes'),
            '/image.png?v=2': ('image/png', b'second-image-bytes'),
            '/font.woff2': ('font/woff2', b'font-bytes'),
            '/app.js': ('application/javascript', b'// Never executed'),
            '/missing-link': ('text/html', b'<a href="/missing">Missing page</a>'),
            '/redirect': ('redirect', b'/second'),
            '/redirect-link': ('text/html', b'<a href="/external-redirect">Redirect</a>'),
            '/external-redirect': ('redirect', b'https://example.invalid/'),
            '/large': ('text/html', b'x' * 2000),
        }
        if self.path not in routes:
            self.send_error(404)
            return
        mime, data = routes[self.path]
        if mime == 'redirect':
            self.send_response(302)
            self.send_header('Location', data.decode())
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), SiteHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def cli(self, root, path='/', *options):
        command = [os.environ['WEBSMITH_TEST_BINARY']] if os.environ.get('WEBSMITH_TEST_BINARY') else [sys.executable, '-m', 'websmith']
        return subprocess.run([*command, 'import', self.url + path, '--delay', '0', *options], cwd=root, capture_output=True, text=True)

    def report(self, root):
        directory = Path(root) / 'imports/127.0.0.1'
        return directory, json.loads((directory / 'report.json').read_text())

    def test_acquire_rewrite_css_robots_and_preserve_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'websmith.yaml').write_text('existing configuration')
            SiteHandler.visits.clear()
            result = self.cli(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archive, report = self.report(root)
            self.assertEqual((root / 'websmith.yaml').read_text(), 'existing configuration')
            records = {r['url']: r for r in report['records']}
            home = records[self.url + '/']
            original = (archive / home['original']).read_text()
            preview = (archive / home['local']).read_text()
            self.assertIn('Original title', original)
            self.assertIn('src="/image.png"', original)
            self.assertIn('../assets/', preview)
            self.assertIn('#section', preview)
            self.assertNotIn('<base', preview)
            self.assertNotIn('sha256-example', preview)
            self.assertIn('Pagine acquisite', (archive / 'preview/index.html').read_text())
            self.assertNotIn('/blocked', SiteHandler.visits)
            self.assertNotIn('/submit', SiteHandler.visits)
            css = records[self.url + '/main.css']
            local_css = (archive / css['local']).read_text()
            self.assertNotIn('"/nested.css"', local_css)
            self.assertTrue(any(r['url'].endswith('/font.woff2') for r in records.values()))
            self.assertTrue(any(e['kind'] == 'warning' and 'Moduli' in e['reason'] for e in report['events']))
            self.assertEqual(self.cli(root).returncode, 2)
            self.assertEqual(original, (archive / home['original']).read_text())

    def test_depth_limit_and_custom_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli(directory, '/', '--max-depth', '0', '--output', 'copies/snapshot')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((Path(directory) / 'copies/snapshot/report.json').read_text())
            self.assertEqual(sum(r['kind'] == 'page' for r in report['records']), 1)
            self.assertTrue(any('Limite pagine' in e['reason'] for e in report['events']))

    def test_partial_errors_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.cli(directory, '/missing-link').returncode, 1)
            _, report = self.report(directory)
            self.assertEqual(report['status'], 'partial')
            self.assertTrue(any(e['url'].endswith('/missing') and e['kind'] == 'error' for e in report['events']))

    def test_file_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.cli(directory, '/large', '--max-file-bytes', '200').returncode, 1)
            _, report = self.report(directory)
            self.assertEqual(report['records'], [])

    def test_same_site_redirect(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli(directory, '/redirect', '--max-pages', '1')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            _, report = self.report(directory)
            self.assertEqual(report['aliases'][self.url + '/redirect'], self.url + '/second')

    def test_external_redirect_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.cli(directory, '/redirect-link').returncode, 1)
            _, report = self.report(directory)
            self.assertTrue(any('Redirect fuori' in e['reason'] for e in report['events']))

    def test_resource_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli(directory, '/', '--max-assets', '1', '--max-pages', '1')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            _, report = self.report(directory)
            self.assertLessEqual(sum(r['kind'] == 'asset' for r in report['records']), 1)
            self.assertTrue(any('Limite risorse' in e['reason'] for e in report['events']))

    def test_invalid_destination_and_arguments_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.cli(directory, '/', '--output', '../outside').returncode, 2)
            self.assertEqual(self.cli(directory, '/', '--max-pages', '0').returncode, 2)
            self.assertEqual(list(Path(directory).iterdir()), [])
