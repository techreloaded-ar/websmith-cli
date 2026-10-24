import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from websmith import engine


def make_site(root):
    for directory in ['contents/en/pages', 'templates/html/components', 'templates/CSS', 'media', 'templates/images']:
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name, text in {
        'COMPOSITION_GUIDE.md': '# Synthetic test site',
        'templates/html/components/catalog.yaml': 'components: [{name: test-component, owned_by: site, layout_role: block}]',
        'templates/CSS/main.css': 'body { color: black; }',
        'templates/images/logo.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
        'templates/html/page.html': '<html><head><title data-websmith-text="page.title">Preview</title></head><body><main class="body"></main></body></html>',
        'templates/html/root.html': '<html><body>Test</body></html>',
        'contents/en/pages/home.md': '---\nid: home\nslug: home\nstatus: published\ntemplate: page.html\ntitle: Test page\n---\n## Hello\n\nSynthetic text.\n',
    }.items():
        (root / name).write_text(text)
    data = {
        '$schema': 'https://websmith.local/schemas/websmith-site.schema.json',
        'version': 1,
        'site': {'id': 'example', 'name': 'Example', 'status': 'active', 'base_url': 'https://example.test'},
        'paths': dict(composition_guide='COMPOSITION_GUIDE.md', contents='contents', templates='templates/html', components='templates/html/components', component_catalog='templates/html/components/catalog.yaml', css='templates/CSS', media='media', output='web'),
        'content': {'canonical_language': 'en', 'languages': {'en': {'html_lang': 'en', 'source': 'contents/en', 'output': 'web/en'}}, 'page_directories': ['pages']},
        'frontmatter': {'required': ['slug', 'status'], 'canonical_page_required': ['id', 'template']},
        'templates': {'default': 'page.html', 'profiles': {'page': {'file': 'page.html', 'content_target': '.body'}}},
        'styles': {'publish': {'templates/CSS/main.css': 'web/shared/css/main.css'}},
        'assets': {'shared_images': {'source': 'templates/images', 'output': 'web/shared/images'}, 'editorial_sources': ['media'], 'resolution_roots': ['media']},
        'brand': {'organization': 'Example', 'email': 'info@example.test', 'logo': 'templates/images/logo.svg', 'published_logo': 'web/shared/images/logo.svg'},
        'root_redirect': {'enabled': False, 'template': 'templates/html/root.html', 'output': 'web/index.html', 'default_language': 'en', 'destinations': {'en': 'en/home.html'}, 'alternates': {'en': 'en'}, 'title': 'Example', 'description': 'Example', 'language_labels': {'en': 'English'}},
    }
    (root / 'websmith.yaml').write_text(json.dumps(data))


class PackageTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, '-m', 'websmith', *map(str, args)], cwd=cwd, text=True, capture_output=True)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installed_resources_and_help(self):
        self.assertTrue(engine.SITE_SCHEMA_PATH.is_file())
        self.assert_ok(self.run_cli('--version'))
        self.assert_ok(self.run_cli('HELP'))

    def test_external_site_and_repeatable_render(self):
        with tempfile.TemporaryDirectory(prefix='websmith site ') as directory:
            root = Path(directory)
            make_site(root)
            self.assert_ok(self.run_cli('validate-site', cwd=root / 'contents'))
            self.assert_ok(self.run_cli('--site-root', root, 'validate-pages'))
            self.assert_ok(self.run_cli('--site-root', root, 'render-page', 'home'))
            outputs = {p.relative_to(root): p.read_bytes() for p in (root / 'web').rglob('*') if p.is_file()}
            self.assertTrue(any(b'Synthetic text.' in content for content in outputs.values()))
            self.assert_ok(self.run_cli('--site-root', root, 'render-page', 'home'))
            self.assertEqual(outputs, {p.relative_to(root): p.read_bytes() for p in (root / 'web').rglob('*') if p.is_file()})
            source = root / 'contents/en/pages/home.md'
            source.write_text(source.read_text().replace('title: Test page', 'title: Test page\nunused_editorial: Must fail'))
            self.assertNotEqual(self.run_cli('--site-root', root, 'render-page', 'home').returncode, 0)
            self.assertEqual(outputs, {p.relative_to(root): p.read_bytes() for p in (root / 'web').rglob('*') if p.is_file()})

    def test_legacy_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_site(root / 'websites/example')
            self.assert_ok(self.run_cli('validate-site', 'example', cwd=root))
            self.assert_ok(self.run_cli('render-page', 'home', '--site', 'example', cwd=root))

    def test_cache_isolation_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / name / 'same' for name in ['one', 'two']]
            for root in roots:
                make_site(root)
            first, second = [engine.config_for_root(root) for root in roots]
            self.assertNotEqual(first.root, second.root)
            manifest = roots[0] / 'websmith.yaml'
            data = json.loads(manifest.read_text())
            data['paths']['output'] = '../outside'
            manifest.write_text(json.dumps(data))
            self.assertNotEqual(self.run_cli('--site-root', roots[0], 'validate-site').returncode, 0)

    def test_explicit_missing_site_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_site(root)
            self.assertNotEqual(self.run_cli('--site-root', root / 'missing', 'validate-site', cwd=root).returncode, 0)


if __name__ == '__main__':
    unittest.main()
