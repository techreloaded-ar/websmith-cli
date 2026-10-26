#!/usr/bin/env python3
"""
Websmith command line helper.

Initial scope: inspect website source structure without generating or editing
website output. Markdown with YAML frontmatter is the canonical content format;
standalone YAML content files are treated as legacy files to migrate.
"""

from __future__ import annotations

import argparse
import filecmp
import html
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - reported at runtime by validation command.
    yaml = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - reported at runtime by render command.
    BeautifulSoup = None

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - reported at runtime by site validation.
    Draft202012Validator = None
    FormatChecker = None


RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"
REPO_ROOT = Path.cwd().resolve()
WEBSITES_ROOT = REPO_ROOT / "websites"
EXPLICIT_SITE_ROOT: Path | None = None


def resolve_site_root(selector: str | None) -> Path:
    if selector and Path(selector).is_absolute():
        return Path(selector).resolve()
    if selector:
        if "/" in selector or "\\" in selector or selector in {".", ".."}:
            raise SystemExit("Use --site-root for a site directory")
        legacy = (WEBSITES_ROOT / selector).resolve()
        if EXPLICIT_SITE_ROOT is not None and legacy != EXPLICIT_SITE_ROOT:
            raise SystemExit("Conflicting --site and --site-root selections")
        return legacy
    if EXPLICIT_SITE_ROOT is not None:
        return EXPLICIT_SITE_ROOT
    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        if (candidate / "websmith.yaml").is_file():
            return candidate
    raise SystemExit("No site found: run inside a site or use --site-root DIRECTORY")

SITE_MANIFEST_NAME = "websmith.yaml"
SITE_SCHEMA_PATH = RESOURCE_ROOT / "schemas" / "websmith-site.schema.json"
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
COMPONENT_MARKER_RE = re.compile(r"^<!--\s*component:\s*(.*?)\s*-->$")
COMPONENT_END_MARKER_RE = re.compile(r"^<!--\s*/component\s*-->$")
ITEM_MARKER_RE = re.compile(r"^<!--\s*item\s*-->$")
SECTION_HEADING_RE = re.compile(r"^##\s+")
EYEBROW_RE = re.compile(r"^--(.+)--$")

LEGACY_FIELD_NAMES = {
    "Nome",
    "Descrizione",
    "Descriione",
    "Immagine",
    "Immgine",
    "Ruolo",
    "Titolo",
    "Sottotitolo",
    "Testo",
}

TECHNICAL_FRONTMATTER_FIELDS = frozenset(
    {
        "current_html",
        "featured",
        "id",
        "lang",
        "slug",
        "source_id",
        "status",
        "template",
    }
)

SHARED_METADATA_DESTINATIONS = frozenset(
    {
        "page.abstract",
        "page.ai_category",
        "page.ai_difficulty",
        "page.ai_license",
        "page.ai_product_type",
        "page.ai_status",
        "page.ai_target_roles",
        "page.author",
        "page.date",
        "page.description",
        "page.keywords",
        "page.last_updated",
        "page.og_type",
        "page.robots",
        "page.schema_author",
        "page.schema_image",
        "page.schema_org",
        "page.schema_type",
        "page.seo_title",
        "page.title",
    }
)

@dataclass(frozen=True)
class SiteInspection:
    name: str
    root: Path
    markdown_files: list[Path]
    yaml_legacy_files: list[Path]
    templates: list[Path]
    media_files: list[Path]
    output_files: list[Path]
    missing_dirs: list[Path]
    md_without_frontmatter: list[Path]


@dataclass(frozen=True)
class SiteConfig:
    name: str
    root: Path
    data: dict[str, object]

    @property
    def canonical_language(self) -> str:
        content = self.data["content"]
        return str(content["canonical_language"])

    @property
    def languages(self) -> dict[str, dict[str, object]]:
        content = self.data["content"]
        return content["languages"]

    @property
    def page_directories(self) -> frozenset[str]:
        content = self.data["content"]
        return frozenset(str(value) for value in content["page_directories"])

    @property
    def contents_root(self) -> Path:
        paths = self.data["paths"]
        return self.root / str(paths["contents"])

    @property
    def output_root(self) -> Path:
        paths = self.data["paths"]
        return self.root / str(paths["output"])

    def configured_path(self, key: str) -> Path:
        paths = self.data["paths"]
        return self.root / str(paths[key])

    @property
    def templates_root(self) -> Path:
        return self.configured_path("templates")

    @property
    def components_root(self) -> Path:
        return self.configured_path("components")

    @property
    def component_catalog(self) -> Path:
        return self.configured_path("component_catalog")

    @property
    def css_root(self) -> Path:
        return self.configured_path("css")

    @property
    def media_root(self) -> Path:
        return self.configured_path("media")

    @property
    def default_template(self) -> str:
        templates = self.data["templates"]
        return str(templates["default"])

    def template_content_target(self, template_name: str) -> str | None:
        templates = self.data["templates"]
        profiles = templates.get("profiles", {})
        if not isinstance(profiles, dict):
            return None
        for profile in profiles.values():
            if not isinstance(profile, dict):
                continue
            if str(profile.get("file", "")) != template_name:
                continue
            target = str(profile.get("content_target", "") or "").strip()
            return target or None
        return None

    @property
    def style_publish_rules(self) -> tuple[tuple[Path, Path], ...]:
        styles = self.data["styles"]
        publish = styles["publish"]
        return tuple(
            (self.root / str(source), self.root / str(destination))
            for source, destination in publish.items()
        )

    @property
    def shared_images_source(self) -> Path:
        assets = self.data["assets"]
        return self.root / str(assets["shared_images"]["source"])

    @property
    def shared_images_output(self) -> Path:
        assets = self.data["assets"]
        return self.root / str(assets["shared_images"]["output"])

    @property
    def shared_root(self) -> Path:
        return self.shared_images_output.parent

    @property
    def asset_resolution_roots(self) -> tuple[Path, ...]:
        assets = self.data["assets"]
        return tuple(self.root / str(value) for value in assets["resolution_roots"])

    @property
    def asset_copy_rules(self) -> tuple[tuple[Path, Path], ...]:
        assets = self.data["assets"]
        configured_rules = [assets["shared_images"], *assets.get("copy_rules", [])]
        return tuple(
            (self.root / str(rule["source"]), self.root / str(rule["output"]))
            for rule in configured_rules
        )

    @property
    def organization(self) -> str:
        site = self.data["site"]
        brand = self.data["brand"]
        return str(brand.get("organization") or site["name"])

    @property
    def base_url(self) -> str:
        site = self.data["site"]
        return str(site["base_url"]).rstrip("/")

    @property
    def email(self) -> str:
        brand = self.data["brand"]
        return str(brand["email"])

    @property
    def logo_source(self) -> Path:
        brand = self.data["brand"]
        return self.root / str(brand["logo"])

    @property
    def published_logo(self) -> Path:
        brand = self.data["brand"]
        return self.root / str(brand["published_logo"])

    @property
    def published_logo_url(self) -> str:
        relative_logo = self.published_logo.relative_to(self.output_root).as_posix()
        return f"{self.base_url}/{relative_logo}"

    @property
    def root_redirect(self) -> dict[str, object]:
        return self.data["root_redirect"]

    @property
    def routing(self) -> dict[str, object]:
        configured = self.data.get("routing")
        return configured if isinstance(configured, dict) else {}

    def language(self, language: str) -> dict[str, object]:
        if language not in self.languages:
            supported = ", ".join(self.languages)
            raise SystemExit(
                f"Unsupported language for site '{self.name}': {language}. Supported: {supported}"
            )
        return self.languages[language]


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


@lru_cache(maxsize=None)
def load_site_config(site_name: str) -> SiteConfig:
    site_name = str(resolve_site_root(site_name))
    data, errors = validate_site_manifest(site_name)
    if data is None or errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise SystemExit(f"Invalid site manifest for '{site_name}':\n{details}")
    return SiteConfig(name=site_name, root=resolve_site_root(site_name), data=data)


def config_for_root(site_root: Path) -> SiteConfig:
    return load_site_config(str(site_root.resolve()))


@lru_cache(maxsize=None)
def load_component_catalog(site_name: str) -> dict[str, dict[str, object]]:
    site_config = load_site_config(site_name)
    catalog = yaml.safe_load(read_text(site_config.component_catalog))
    components = catalog.get("components", []) if isinstance(catalog, dict) else []
    return {
        str(component["name"]): component
        for component in components
        if isinstance(component, dict) and str(component.get("name", "")).strip()
    }


def component_catalog_for_root(site_root: Path) -> dict[str, dict[str, object]]:
    return load_component_catalog(str(site_root.resolve()))


def component_required_fields(site_root: Path, component_name: str) -> frozenset[str]:
    component = component_catalog_for_root(site_root).get(component_name, {})
    fields = component.get("fields", {}) if isinstance(component, dict) else {}
    required = fields.get("required", []) if isinstance(fields, dict) else []
    return frozenset(str(field) for field in required)


def language_config(site_root: Path, language: str) -> dict[str, str]:
    configured = config_for_root(site_root).language(language)
    labels = configured.get("labels")
    result = {
        "html_lang": str(configured["html_lang"]),
        "source_root": str(configured["source"]),
        "output_root": str(configured["output"]),
    }
    if isinstance(labels, dict):
        for key, value in labels.items():
            result_key = (
                f"{key}_label"
                if key in {"home", "team", "services", "contacts"}
                else str(key)
            )
            result[result_key] = str(value)
    return result


def source_root(site_root: Path, language: str) -> Path:
    return site_root / language_config(site_root, language)["source_root"]


def output_root(site_root: Path, language: str) -> Path:
    return site_root / language_config(site_root, language)["output_root"]


def require_source(path: Path) -> bool:
    if path.exists():
        return True
    print(f"Source not found: {relative(path)}")
    return False


def template_file_name(metadata: dict[str, object], default: str) -> str:
    value = metadata.get("template")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def collect_files(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob(pattern) if path.is_file())


def has_frontmatter(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8-sig")
    return bool(FRONTMATTER_RE.match(content))


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def extract_frontmatter(path: Path) -> str | None:
    match = FRONTMATTER_RE.match(read_text(path))
    if not match:
        return None
    return match.group(1)


def html_attr(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def site_relative_path(
    site_root: Path,
    value: object,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty relative path")
        return None

    configured = Path(value.strip())
    if configured.is_absolute():
        errors.append(f"{label}: absolute paths are not allowed: {value}")
        return None

    resolved = (site_root / configured).resolve()
    try:
        resolved.relative_to(site_root.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes the site root: {value}")
        return None
    return resolved


def require_manifest_path(
    site_root: Path,
    value: object,
    label: str,
    errors: list[str],
    *,
    kind: str,
) -> Path | None:
    resolved = site_relative_path(site_root, value, label, errors)
    if resolved is None:
        return None
    if kind == "file" and not resolved.is_file():
        errors.append(f"{label}: file not found: {relative(resolved)}")
    elif kind == "directory" and not resolved.is_dir():
        errors.append(f"{label}: directory not found: {relative(resolved)}")
    elif kind == "directory_or_missing" and resolved.exists() and not resolved.is_dir():
        errors.append(f"{label}: expected a directory path: {relative(resolved)}")
    return resolved


def validate_site_manifest(site_name: str) -> tuple[dict[str, object] | None, list[str]]:
    site_root = resolve_site_root(site_name)
    manifest_path = site_root / SITE_MANIFEST_NAME
    errors: list[str] = []

    if yaml is None:
        return None, ["PyYAML is required for site manifest validation"]
    if Draft202012Validator is None or FormatChecker is None:
        return None, ["jsonschema is required for site manifest validation"]
    if not site_root.is_dir():
        return None, [f"Site not found: {relative(site_root)}"]
    if not manifest_path.is_file():
        return None, [f"Manifest not found: {relative(manifest_path)}"]
    if not SITE_SCHEMA_PATH.is_file():
        return None, [f"Shared schema not found: {relative(SITE_SCHEMA_PATH)}"]

    try:
        data = yaml.safe_load(read_text(manifest_path))
    except yaml.YAMLError as exc:
        return None, [f"{relative(manifest_path)}: invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{relative(manifest_path)}: manifest must be a mapping/object"]

    try:
        schema = json.loads(read_text(SITE_SCHEMA_PATH))
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"{relative(SITE_SCHEMA_PATH)}: invalid JSON schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for issue in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in issue.absolute_path) or "manifest"
        errors.append(f"{location}: {issue.message}")
    if errors:
        return data, errors

    declared_schema = data.get("$schema")
    if declared_schema:
        resolved_schema = (manifest_path.parent / str(declared_schema)).resolve()
        if (
            declared_schema not in {
                "https://websmith.local/schemas/websmith-site.schema.json",
                "../../schemas/websmith-site.schema.json",
            }
            and resolved_schema != SITE_SCHEMA_PATH.resolve()
        ):
            errors.append(
                f"$schema: expected {relative(SITE_SCHEMA_PATH)}, got {declared_schema}"
            )

    site = data["site"]
    paths = data["paths"]
    content = data["content"]
    templates = data["templates"]
    styles = data["styles"]
    assets = data["assets"]
    brand = data["brand"]
    root_redirect = data["root_redirect"]

    if not Path(site_name).is_absolute() and site["id"] != site_name:
        errors.append(f"site.id: expected '{site_name}', got '{site['id']}'")

    path_kinds = {
        "composition_guide": "file",
        "contents": "directory",
        "templates": "directory",
        "components": "directory",
        "component_catalog": "file",
        "css": "directory",
        "media": "directory",
        "output": "directory_or_missing",
    }
    resolved_paths: dict[str, Path] = {}
    for key, kind in path_kinds.items():
        resolved = require_manifest_path(
            site_root,
            paths[key],
            f"paths.{key}",
            errors,
            kind=kind,
        )
        if resolved is not None:
            resolved_paths[key] = resolved

    templates_root = resolved_paths.get("templates")
    components_root = resolved_paths.get("components")
    component_catalog = resolved_paths.get("component_catalog")
    if templates_root is not None and components_root is not None:
        try:
            components_root.relative_to(templates_root)
        except ValueError:
            errors.append("paths.components: must be inside paths.templates")
    if components_root is not None and component_catalog is not None:
        try:
            component_catalog.relative_to(components_root)
        except ValueError:
            errors.append("paths.component_catalog: must be inside paths.components")

    languages = content["languages"]
    canonical_language = content["canonical_language"]
    if canonical_language not in languages:
        errors.append(
            f"content.canonical_language: '{canonical_language}' is not declared in content.languages"
        )

    configured_contents = resolved_paths.get("contents")
    configured_output = resolved_paths.get("output")
    language_sources: set[Path] = set()
    language_outputs: set[Path] = set()
    for language, language_data in languages.items():
        source = require_manifest_path(
            site_root,
            language_data["source"],
            f"content.languages.{language}.source",
            errors,
            kind="directory",
        )
        output = require_manifest_path(
            site_root,
            language_data["output"],
            f"content.languages.{language}.output",
            errors,
            kind="directory_or_missing",
        )
        if source is not None:
            if source in language_sources:
                errors.append(f"content.languages.{language}.source: duplicate language source")
            language_sources.add(source)
            if configured_contents is not None:
                try:
                    source.relative_to(configured_contents)
                except ValueError:
                    errors.append(
                        f"content.languages.{language}.source: must be inside paths.contents"
                    )
        if output is not None:
            if output in language_outputs:
                errors.append(f"content.languages.{language}.output: duplicate language output")
            language_outputs.add(output)
            if configured_output is not None:
                try:
                    output.relative_to(configured_output)
                except ValueError:
                    errors.append(
                        f"content.languages.{language}.output: must be inside paths.output"
                    )

    template_root = resolved_paths.get("templates")
    default_template = templates["default"]
    if template_root is not None:
        default_path = (template_root / default_template).resolve()
        try:
            default_path.relative_to(template_root)
        except ValueError:
            errors.append("templates.default: path escapes paths.templates")
        else:
            if not default_path.is_file():
                errors.append(f"templates.default: template not found: {relative(default_path)}")
        for profile, profile_data in templates["profiles"].items():
            profile_path = (template_root / profile_data["file"]).resolve()
            try:
                profile_path.relative_to(template_root)
            except ValueError:
                errors.append(f"templates.profiles.{profile}.file: path escapes paths.templates")
            else:
                if not profile_path.is_file():
                    errors.append(
                        f"templates.profiles.{profile}.file: template not found: {relative(profile_path)}"
                    )

    for source_value, output_value in styles["publish"].items():
        source = require_manifest_path(
            site_root,
            source_value,
            f"styles.publish source '{source_value}'",
            errors,
            kind="file",
        )
        destination = site_relative_path(
            site_root,
            output_value,
            f"styles.publish destination '{output_value}'",
            errors,
        )
        if source is not None and resolved_paths.get("css") is not None:
            try:
                source.relative_to(resolved_paths["css"])
            except ValueError:
                errors.append(f"styles.publish source '{source_value}': must be inside paths.css")
        if destination is not None and configured_output is not None:
            try:
                destination.relative_to(configured_output)
            except ValueError:
                errors.append(
                    f"styles.publish destination '{output_value}': must be inside paths.output"
                )

    shared_images = assets["shared_images"]
    require_manifest_path(
        site_root,
        shared_images["source"],
        "assets.shared_images.source",
        errors,
        kind="directory",
    )
    shared_output = site_relative_path(
        site_root,
        shared_images["output"],
        "assets.shared_images.output",
        errors,
    )
    for index, editorial_source in enumerate(assets["editorial_sources"]):
        require_manifest_path(
            site_root,
            editorial_source,
            f"assets.editorial_sources.{index}",
            errors,
            kind="directory",
        )
    for index, resolution_root in enumerate(assets["resolution_roots"]):
        require_manifest_path(
            site_root,
            resolution_root,
            f"assets.resolution_roots.{index}",
            errors,
            kind="directory_or_missing",
        )
    for index, copy_rule in enumerate(assets.get("copy_rules", [])):
        require_manifest_path(
            site_root,
            copy_rule["source"],
            f"assets.copy_rules.{index}.source",
            errors,
            kind="directory",
        )
        copy_output = site_relative_path(
            site_root,
            copy_rule["output"],
            f"assets.copy_rules.{index}.output",
            errors,
        )
        if copy_output is not None and configured_output is not None:
            try:
                copy_output.relative_to(configured_output)
            except ValueError:
                errors.append(f"assets.copy_rules.{index}.output: must be inside paths.output")

    logo = require_manifest_path(site_root, brand["logo"], "brand.logo", errors, kind="file")
    published_logo = site_relative_path(
        site_root,
        brand["published_logo"],
        "brand.published_logo",
        errors,
    )
    for label, destination in [
        ("assets.shared_images.output", shared_output),
        ("brand.published_logo", published_logo),
    ]:
        if destination is not None and configured_output is not None:
            try:
                destination.relative_to(configured_output)
            except ValueError:
                errors.append(f"{label}: must be inside paths.output")
    if logo is not None and shared_output is not None and published_logo is not None:
        expected_logo = shared_output / logo.name
        if published_logo != expected_logo:
            errors.append(
                f"brand.published_logo: expected {relative(expected_logo)} from shared image copy rule"
            )

    redirect_languages = set(root_redirect["destinations"])
    configured_languages = set(languages)
    if root_redirect["default_language"] not in languages:
        errors.append("root_redirect.default_language: language is not declared in content.languages")
    if root_redirect["enabled"] and redirect_languages != configured_languages:
        errors.append(
            "root_redirect.destinations: must declare exactly the configured content languages"
        )
    alternate_languages = set(root_redirect["alternates"])
    if not alternate_languages.issubset(configured_languages):
        errors.append("root_redirect.alternates: contains a language not declared in content.languages")
    label_languages = set(root_redirect["language_labels"])
    if root_redirect["enabled"] and label_languages != configured_languages:
        errors.append(
            "root_redirect.language_labels: must declare exactly the configured content languages"
        )
    if configured_output is not None:
        for language, destination_value in root_redirect["destinations"].items():
            destination = (configured_output / destination_value).resolve()
            try:
                destination.relative_to(configured_output)
            except ValueError:
                errors.append(
                    f"root_redirect.destinations.{language}: path escapes paths.output"
                )
    redirect_output = site_relative_path(
        site_root,
        root_redirect["output"],
        "root_redirect.output",
        errors,
    )
    require_manifest_path(
        site_root,
        root_redirect["template"],
        "root_redirect.template",
        errors,
        kind="file",
    )
    if redirect_output is not None and configured_output is not None:
        try:
            redirect_output.relative_to(configured_output)
        except ValueError:
            errors.append("root_redirect.output: must be inside paths.output")

    catalog_path = resolved_paths.get("component_catalog")
    if catalog_path is not None and catalog_path.is_file():
        try:
            catalog = yaml.safe_load(read_text(catalog_path))
        except yaml.YAMLError as exc:
            errors.append(f"paths.component_catalog: invalid YAML: {exc}")
        else:
            components = catalog.get("components") if isinstance(catalog, dict) else None
            if not isinstance(components, list) or not components:
                errors.append("paths.component_catalog: expected a non-empty components list")
            else:
                component_names: set[str] = set()
                for index, component in enumerate(components):
                    if not isinstance(component, dict) or not str(component.get("name", "")).strip():
                        errors.append(
                            f"paths.component_catalog.components.{index}: missing component name"
                        )
                        continue
                    component_name = str(component["name"])
                    if component_name in component_names:
                        errors.append(
                            f"paths.component_catalog.components.{index}: duplicate component '{component_name}'"
                        )
                    component_names.add(component_name)
                    render = component.get("render")
                    if render is None:
                        continue
                    if not isinstance(render, dict):
                        errors.append(
                            f"paths.component_catalog.components.{index}.render: expected an object"
                        )
                        continue
                    template_name = str(render.get("template", ""))
                    selector = str(render.get("selector", ""))
                    if not template_name or not selector:
                        errors.append(
                            f"paths.component_catalog.components.{index}.render: template and selector are required"
                        )
                        continue
                    if components_root is None:
                        continue
                    render_template = (components_root / template_name).resolve()
                    try:
                        render_template.relative_to(components_root.resolve())
                    except ValueError:
                        errors.append(
                            f"paths.component_catalog.components.{index}.render.template: path escapes paths.components"
                        )
                        continue
                    if not render_template.is_file():
                        errors.append(
                            f"paths.component_catalog.components.{index}.render.template: file not found '{template_name}'"
                        )
                        continue
                    if BeautifulSoup is not None:
                        render_soup = BeautifulSoup(read_text(render_template), "html.parser")
                        if render_soup.select_one(selector) is None:
                            errors.append(
                                f"paths.component_catalog.components.{index}.render.selector: no match for '{selector}'"
                            )

    return data, errors


def command_validate_site(args: argparse.Namespace) -> int:
    manifest_path = resolve_site_root(args.site) / SITE_MANIFEST_NAME
    data, errors = validate_site_manifest(args.site)

    print(f"Site manifest validation: {args.site}")
    print(f"Manifest: {relative(manifest_path)}")
    print(f"Schema: {relative(SITE_SCHEMA_PATH)}")
    if data is not None:
        languages = data.get("content", {}).get("languages", {})
        if isinstance(languages, dict):
            print(f"Languages: {', '.join(languages)}")

    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Errors: 0")
    return 0


def inspect_site(site_name: str) -> SiteInspection:
    site_root = resolve_site_root(site_name)
    if not site_root.exists():
        raise SystemExit(f"Site not found: {relative(site_root)}")

    manifest_path = site_root / SITE_MANIFEST_NAME
    manifest_data: dict[str, object] | None = None
    if manifest_path.is_file():
        manifest_data, manifest_errors = validate_site_manifest(site_name)
        if manifest_errors:
            manifest_data = None

    if manifest_data is not None:
        paths = manifest_data["paths"]
        content_root = site_root / str(paths["contents"])
        template_root = site_root / str(paths["templates"])
        output_path = site_root / str(paths["output"])
        expected_dirs = [
            content_root,
            template_root,
            site_root / str(paths["components"]),
            site_root / str(paths["css"]),
            site_root / str(paths["media"]),
        ]
        assets = manifest_data["assets"]
        media_roots = [
            site_root / str(value)
            for value in assets["editorial_sources"]
        ]
    else:
        content_root = site_root / "contents"
        template_root = site_root / "templates"
        media_roots = [site_root / "media", content_root / "media", template_root / "images"]
        output_path = site_root / "web"
        expected_dirs = [content_root, template_root, output_path]

    missing_dirs = [path for path in expected_dirs if not path.exists()]

    markdown_files = collect_files(content_root, "*.md")
    yaml_legacy_files = collect_files(content_root, "*.yaml") + collect_files(content_root, "*.yml")
    templates = collect_files(template_root, "*.html") + collect_files(template_root, "*.htm")
    media_files: list[Path] = []
    for media_root in media_roots:
        media_files.extend(
            path
            for path in collect_files(media_root, "*")
            if path.suffix.lower() not in {".html", ".htm", ".md", ".yaml", ".yml"}
        )
    output_files = collect_files(output_path, "*")

    md_without_frontmatter = [path for path in markdown_files if not has_frontmatter(path)]

    return SiteInspection(
        name=site_name,
        root=site_root,
        markdown_files=markdown_files,
        yaml_legacy_files=sorted(set(yaml_legacy_files)),
        templates=sorted(set(templates)),
        media_files=sorted(set(media_files)),
        output_files=output_files,
        missing_dirs=missing_dirs,
        md_without_frontmatter=md_without_frontmatter,
    )


def print_file_sample(title: str, files: list[Path], limit: int = 8) -> None:
    print(f"{title}: {len(files)}")
    for path in files[:limit]:
        print(f"  - {relative(path)}")
    if len(files) > limit:
        print(f"  ... {len(files) - limit} more")


def command_inspect(args: argparse.Namespace) -> int:
    inspection = inspect_site(args.site)
    manifest_path = inspection.root / SITE_MANIFEST_NAME
    manifest_errors: list[str] = []
    if manifest_path.exists():
        _manifest, manifest_errors = validate_site_manifest(args.site)

    print(f"Websmith inspection: {inspection.name}")
    print(f"Root: {relative(inspection.root)}")
    print(f"Manifest: {relative(manifest_path) if manifest_path.exists() else 'missing'}")
    if manifest_errors:
        print(f"Manifest errors: {len(manifest_errors)}")
    print()

    if inspection.missing_dirs:
        print_file_sample("Missing expected directories", inspection.missing_dirs)
        print()

    print_file_sample("Markdown content files", inspection.markdown_files)
    print_file_sample("Markdown files missing frontmatter", inspection.md_without_frontmatter)
    print_file_sample("Legacy YAML content files to migrate", inspection.yaml_legacy_files)
    print_file_sample("HTML templates", inspection.templates)
    print_file_sample("Media/static files", inspection.media_files)
    print_file_sample("Generated output files", inspection.output_files)

    print()
    print("Canonical content format: Markdown with YAML frontmatter")
    if manifest_errors:
        print("Status: invalid site manifest")
    elif inspection.missing_dirs:
        print("Status: incomplete site structure")
    elif not manifest_path.exists():
        print("Status: site manifest missing")
    elif inspection.yaml_legacy_files:
        print("Status: migration needed for standalone YAML content files")
    elif inspection.md_without_frontmatter:
        print("Status: frontmatter cleanup needed")
    else:
        print("Status: source format looks aligned")

    return 0


def command_validate_frontmatter(args: argparse.Namespace) -> int:
    if yaml is None:
        print("PyYAML is required for frontmatter validation. Install with: python3 -m pip install pyyaml")
        return 2

    inspection = inspect_site(args.site)
    site_config = load_site_config(args.site)
    frontmatter_config = site_config.data["frontmatter"]
    required_fields = [str(field) for field in frontmatter_config["required"]]
    errors: list[str] = []

    for path in inspection.markdown_files:
        frontmatter = extract_frontmatter(path)
        if frontmatter is None:
            errors.append(f"{relative(path)}: missing YAML frontmatter")
            continue

        try:
            data = yaml.safe_load(frontmatter)
        except yaml.YAMLError as exc:
            errors.append(f"{relative(path)}: invalid YAML frontmatter: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"{relative(path)}: frontmatter must be a mapping/object")
            continue

        missing = [field for field in required_fields if field not in data or data[field] in (None, "")]
        if missing:
            errors.append(f"{relative(path)}: missing required field(s): {', '.join(missing)}")

    print(f"Frontmatter validation: {inspection.name}")
    print(f"Markdown files checked: {len(inspection.markdown_files)}")

    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Errors: 0")
    return 0


def resolve_page_source(site_root: Path, language: str, page: str) -> Path | None:
    root = source_root(site_root, language)
    normalized_page = page.strip().strip("/")
    if not normalized_page:
        return root / "pagine" / "index.md"
    if normalized_page in {"index", "index.html", "home"}:
        return root / "pagine" / "index.md"

    candidates = []
    page_path = Path(normalized_page)
    if page_path.suffix == ".md":
        candidates.append(root / page_path)
    else:
        candidates.extend(
            [
                root / page_path.with_suffix(".md"),
                root / page_path / "index.md",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    output_base = output_root(site_root, language)
    wanted = normalized_page.removesuffix(".html").removesuffix("/index").strip("/")

    for source in collect_files(root, "*.md"):
        metadata, _body = strip_frontmatter(read_text(source))
        slug = str(metadata.get("slug") or source.stem).strip("/")
        if wanted in {source.stem, slug}:
            return source
        output = infer_content_output(site_root, source, metadata)
        if output is None:
            continue
        try:
            rel = output.relative_to(output_base).as_posix()
        except ValueError:
            continue
        rel_no_html = rel.removesuffix(".html")
        rel_no_index = rel.removesuffix("/index.html")
        if wanted in {rel, rel_no_html, rel_no_index}:
            return source

    return None


def is_page_source(site_root: Path, source: Path) -> bool:
    site_config = config_for_root(site_root)
    try:
        relative_source = source.relative_to(site_config.contents_root)
    except ValueError:
        return False

    parts = relative_source.parts
    if parts and parts[0] in site_config.languages:
        parts = parts[1:]
    return bool(parts) and parts[0] in site_config.page_directories


def previous_nonblank_line(lines: list[str], index: int) -> str:
    for previous in range(index - 1, -1, -1):
        if lines[previous].strip():
            return lines[previous].strip()
    return ""


def is_external_asset(src: str) -> bool:
    return src.startswith(("http://", "https://", "data:", "mailto:", "tel:", "#"))


def unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return tuple(unique)


def local_asset_matches(
    site_root: Path,
    src: str,
    *,
    source: Path | None = None,
    output: Path | None = None,
) -> tuple[Path, ...]:
    site_config = config_for_root(site_root)
    clean_src = src.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_src or is_external_asset(clean_src):
        return ()
    if clean_src.startswith("/"):
        candidate = site_config.output_root / clean_src.lstrip("/")
        return (candidate,) if candidate.is_file() else ()

    if source is not None:
        candidate = source.parent / clean_src
        if candidate.is_file():
            return (candidate,)
    if output is not None:
        candidate = output.parent / clean_src
        if candidate.is_file():
            return (candidate,)

    exact_matches = [
        resolution_root / clean_src
        for resolution_root in site_config.asset_resolution_roots
        if (resolution_root / clean_src).is_file()
    ]
    if exact_matches:
        return unique_paths(exact_matches)

    requested_parts = Path(clean_src).parts
    recursive_matches: list[Path] = []
    for resolution_root in site_config.asset_resolution_roots:
        if not resolution_root.is_dir():
            continue
        for candidate in resolution_root.rglob(Path(clean_src).name):
            if not candidate.is_file():
                continue
            relative_parts = candidate.relative_to(resolution_root).parts
            if len(requested_parts) == 1 or relative_parts[-len(requested_parts):] == requested_parts:
                recursive_matches.append(candidate)
    return unique_paths(recursive_matches)


def local_asset_validation_error(
    site_root: Path,
    source: Path,
    output: Path | None,
    src: str,
) -> str | None:
    clean_src = src.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_src or is_external_asset(clean_src):
        return None
    matches = local_asset_matches(site_root, src, source=source, output=output)
    if not matches:
        return f"missing local asset '{src}'"
    if len(matches) > 1:
        locations = ", ".join(relative(path) for path in matches)
        return f"ambiguous local asset '{src}': {locations}"
    return None


def local_asset_source(site_root: Path, src: str) -> Path | None:
    clean_src = src.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_src or is_external_asset(clean_src) or clean_src.startswith("/"):
        return None

    matches = local_asset_matches(site_root, src)
    if len(matches) > 1:
        locations = ", ".join(relative(path) for path in matches)
        raise ValueError(f"ambiguous local asset '{src}': {locations}")
    return matches[0] if matches else None


def copy_referenced_local_assets(site_root: Path, output: Path, soup: object) -> None:
    for tag in soup.find_all(["img", "source"]):
        src = str(tag.get("src") or "")
        if not src or is_external_asset(src) or src.startswith("/"):
            continue
        target = output.parent / src.split("#", 1)[0].split("?", 1)[0]
        source = local_asset_source(site_root, src)
        if source is None:
            continue
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def validate_component_requirements(
    site_root: Path,
    source: Path,
    component_name: str,
    block: dict[str, object],
    errors: list[str],
    line_label: str,
) -> None:
    metadata = block.get("metadata") or {}
    if isinstance(metadata, dict):
        required = component_required_fields(site_root, component_name)
        missing = [field for field in sorted(required) if not str(metadata.get(field, "")).strip()]
        if missing:
            errors.append(f"{relative(source)}:{line_label}: component '{component_name}' missing field(s): {', '.join(missing)}")

    items = block.get("items") or []
    for item in items:
        component = item.get("component") if isinstance(item, dict) else None
        item_name = component.get("name") if isinstance(component, dict) else None
        item_metadata = item.get("metadata") if isinstance(item, dict) else None
        if not item_name or not isinstance(item_metadata, dict):
            continue
        required = component_required_fields(site_root, str(item_name))
        missing = [field for field in sorted(required) if not str(item_metadata.get(field, "")).strip()]
        if missing:
            errors.append(f"{relative(source)}:{line_label}: item component '{item_name}' missing field(s): {', '.join(missing)}")


def populated_source_leaf_paths(value: object, prefix: str = "page") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            paths.extend(populated_source_leaf_paths(child, child_prefix))
        return paths
    if isinstance(value, (list, tuple)):
        paths = []
        for child in value:
            child_prefix = f"{prefix}[]"
            paths.extend(populated_source_leaf_paths(child, child_prefix))
        return paths
    return [prefix] if binding_is_present(value) else []


def template_page_binding_paths(template: Path) -> set[str]:
    soup = BeautifulSoup(read_text(template), "html.parser")
    paths: set[str] = set()
    for tag in soup.find_all(True):
        for attribute, value in tag.attrs.items():
            if not str(attribute).startswith("data-websmith-"):
                continue
            text_value = " ".join(str(item) for item in value) if isinstance(value, list) else str(value)
            paths.update(
                re.findall(r"(?<![A-Za-z0-9_$])page(?:\.[A-Za-z0-9_-]+)+", text_value)
            )
    return paths


def source_path_has_destination(path: str, destinations: set[str]) -> bool:
    return any(
        path == destination
        or path.startswith(f"{destination}.")
        or path.startswith(f"{destination}[]")
        for destination in destinations
    )


def template_placement_errors(
    site_root: Path,
    source: Path,
    metadata: dict[str, object],
    body: str,
) -> list[str]:
    site_config = config_for_root(site_root)
    template_name = template_file_name(metadata, site_config.default_template)
    if template_name == "current-html":
        return []
    template = site_config.templates_root / template_name
    if not template.is_file():
        return [f"{relative(source)}: template not found for placement validation: {template_name}"]
    if BeautifulSoup is None:
        return [f"{relative(source)}: beautifulsoup4 is required for placement validation"]

    destinations = set(SHARED_METADATA_DESTINATIONS)
    destinations.update(template_page_binding_paths(template))
    unused_paths: list[str] = []
    for path in populated_source_leaf_paths(metadata):
        top_level = path.removeprefix("page.").split(".", 1)[0].split("[]", 1)[0]
        if top_level in TECHNICAL_FRONTMATTER_FIELDS:
            continue
        if not source_path_has_destination(path, destinations):
            unused_paths.append(path)

    errors = [
        f"{relative(source)}: Markdown value has no template destination: {path}"
        for path in sorted(set(unused_paths))
    ]
    if body.strip():
        soup = BeautifulSoup(read_text(template), "html.parser")
        configured_target = site_config.template_content_target(template_name)
        if soup.select_one("[data-websmith-body]") is None and (
            not configured_target or soup.select_one(configured_target) is None
        ):
            errors.append(
                f"{relative(source)}: Markdown body has no template destination"
            )
    return errors


def validate_page_source(site_root: Path, source: Path) -> tuple[Path | None, list[str]]:
    markdown = read_text(source)
    metadata, body = strip_frontmatter(markdown)
    output = infer_content_output(site_root, source, metadata)
    reference_map = build_content_reference_map(site_root)
    lines = body.splitlines()
    errors: list[str] = []
    errors.extend(template_placement_errors(site_root, source, metadata, body))
    component_catalog = component_catalog_for_root(site_root)

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        marker = parse_component_marker(stripped)

        if marker:
            component_name = marker[0]
            if component_name not in component_catalog:
                errors.append(f"{relative(source)}:{line_number}: unknown component '{component_name}'")
            elif component_catalog[component_name].get("owned_by") != "markdown":
                owner = component_catalog[component_name].get("owned_by", "unspecified")
                errors.append(
                    f"{relative(source)}:{line_number}: component '{component_name}' "
                    f"is owned by {owner}, not Markdown"
                )
            previous = previous_nonblank_line(lines, line_number - 1)
            is_item_component = bool(ITEM_MARKER_RE.match(previous))
            if not is_item_component:
                has_closing = any(is_component_end_marker(candidate) for candidate in lines[line_number:])
                if not has_closing:
                    errors.append(f"{relative(source)}:{line_number}: component '{component_name}' missing <!-- /component -->")
            parsed = parse_component_block_at(lines, line_number - 1)
            if parsed:
                validate_component_requirements(
                    site_root,
                    source,
                    parsed[0],
                    parsed[1],
                    errors,
                    str(line_number),
                )
            continue

        if stripped.startswith("<!--") and stripped.endswith("-->"):
            comment = stripped[4:-3].strip()
            lower_comment = comment.lower()
            if lower_comment.startswith("component ") or lower_comment.startswith("griglia") or lower_comment.startswith("cella"):
                errors.append(f"{relative(source)}:{line_number}: legacy marker '{comment}'")

        for field in LEGACY_FIELD_NAMES:
            if re.match(rf"^{re.escape(field)}\s*:", stripped):
                errors.append(f"{relative(source)}:{line_number}: legacy field '{field}'")

        if stripped.startswith("<") and not stripped.startswith("<!--"):
            errors.append(f"{relative(source)}:{line_number}: raw HTML is not allowed in Markdown body")

        for reference in re.findall(r"(?<!!)\[([A-Za-z0-9_/-]+)\](?!\()", line):
            if reference not in reference_map:
                errors.append(f"{relative(source)}:{line_number}: unresolved content reference '[{reference}]'")

        image_match = re.match(r"^(image|src)\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if image_match:
            image_src = image_match.group(2).strip().strip('"').strip("'")
            asset_error = local_asset_validation_error(site_root, source, output, image_src)
            if asset_error:
                errors.append(f"{relative(source)}:{line_number}: {asset_error}")

        for _alt, image_src in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", line):
            image_src = image_src.strip()
            asset_error = local_asset_validation_error(site_root, source, output, image_src)
            if asset_error:
                errors.append(f"{relative(source)}:{line_number}: {asset_error}")

    return output, errors


def validate_source_before_render(site_root: Path, source: Path) -> bool:
    _output, errors = validate_page_source(site_root, source)
    if not errors:
        return True

    print(f"Render blocked: source validation failed for {relative(source)}")
    print(f"Errors: {len(errors)}")
    for error in errors:
        print(f"  - {error}")
    return False


def require_file(path: Path, label: str) -> bool:
    if path.exists() and path.is_file():
        return True
    print(f"{label} not found: {relative(path)}")
    return False


def resolve_page_by_id(site_root: Path, page_id: str, language: str | None = None) -> tuple[Path, Path, dict[str, object]] | None:
    normalized_id = page_id.strip()
    if not normalized_id:
        return None

    site_config = config_for_root(site_root)
    canonical_language = site_config.canonical_language
    language = language or canonical_language
    site_config.language(language)

    for canonical_source in collect_files(source_root(site_root, canonical_language), "*.md"):
        canonical_metadata, _body = strip_frontmatter(read_text(canonical_source))
        if str(canonical_metadata.get("id", "")).strip() != normalized_id:
            continue
        if language == canonical_language:
            return canonical_source, canonical_source, canonical_metadata

        try:
            relative_source = canonical_source.relative_to(source_root(site_root, canonical_language))
        except ValueError:
            return None
        translation_path = source_root(site_root, language) / relative_source
        if not translation_path.exists():
            return None
        return canonical_source, translation_path, canonical_metadata

    return None


def output_language(site_root: Path, output: Path) -> str | None:
    site_config = config_for_root(site_root)
    for language in site_config.languages:
        try:
            output.resolve().relative_to(output_root(site_root, language).resolve())
        except ValueError:
            continue
        return language
    return None


def resolve_page_by_output(site_root: Path, output_path: Path) -> tuple[str, str, Path, Path] | None:
    output_path = output_path.resolve()
    site_config = config_for_root(site_root)
    language = output_language(site_root, output_path)
    if language is None:
        return None
    language_relative_output = output_path.relative_to(output_root(site_root, language).resolve()).as_posix()

    for canonical_source in collect_files(source_root(site_root, site_config.canonical_language), "*.md"):
        canonical_metadata, _body = strip_frontmatter(read_text(canonical_source))
        resolved_language = resolve_page_by_id(
            site_root,
            str(canonical_metadata.get("id") or canonical_source.stem),
            language,
        )
        if resolved_language is None:
            continue
        _canonical, language_source, _canonical_metadata = resolved_language
        configured_output = infer_content_output(site_root, language_source, canonical_metadata)
        if configured_output is None:
            continue
        if configured_output.relative_to(output_root(site_root, language)).as_posix() != language_relative_output:
            continue
        page_id = str(canonical_metadata.get("id") or canonical_source.stem)
        return page_id, language, canonical_source, output_path

    return None


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def markdown_translation_contract(body: str) -> dict[str, list[str]]:
    heading_levels: list[str] = []
    eyebrows: list[str] = []
    components: list[str] = []
    content_refs: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        heading = re.match(r"^(#{1,6})\s+", stripped)
        if heading:
            heading_levels.append(str(len(heading.group(1))))

        eyebrow = re.match(r"^--(.+?)--$", stripped)
        if eyebrow:
            eyebrows.append(eyebrow.group(1).strip())

        marker = parse_component_marker(stripped)
        if marker:
            components.append(marker[0])

        content_refs.extend(re.findall(r"(?<!!)\[([A-Za-z0-9_/-]+)\](?!\()", line))
        content_refs.extend(re.findall(r"\]\(\[([A-Za-z0-9_-]+)\]\)", line))

    return {
        "heading_levels": heading_levels,
        "eyebrows": eyebrows,
        "components": components,
        "content_refs": ordered_unique(content_refs),
    }


def compare_translation_contracts(
    source_contract: dict[str, list[str]],
    target_contract: dict[str, list[str]],
) -> list[str]:
    issues: list[str] = []
    for key, label in [
        ("heading_levels", "heading level sequence"),
        ("eyebrows", "section eyebrow markers"),
        ("components", "component marker sequence"),
        ("content_refs", "logical content references"),
    ]:
        if source_contract.get(key, []) != target_contract.get(key, []):
            issues.append(f"{label} differs")
    return issues


def copy_configured_assets(site_root: Path) -> None:
    site_config = config_for_root(site_root)
    for source, destination in site_config.asset_copy_rules:
        if not source.is_dir():
            print(f"Asset source not found: {relative(source)}")
            continue
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, dirs_exist_ok=True)


def relative_shared_asset(site_root: Path, output: Path, *parts: str) -> str:
    target = config_for_root(site_root).shared_root / Path(*parts)
    return os.path.relpath(target, output.parent)


def normalize_logo_paths(soup: object, site_root: Path, output: Path) -> None:
    site_config = config_for_root(site_root)
    logo_name = site_config.logo_source.name
    logo_src = os.path.relpath(site_config.published_logo, output.parent)
    for image in soup.find_all("img"):
        src = str(image.get("src") or "")
        if src.endswith(logo_name):
            image["src"] = logo_src


def validate_logo_paths(soup: object, site_root: Path, output: Path) -> list[str]:
    logo_name = config_for_root(site_root).logo_source.name
    errors: list[str] = []
    for image in soup.find_all("img"):
        src = str(image.get("src") or "")
        if not src.endswith(logo_name):
            continue
        parsed = urlparse(src)
        if parsed.scheme or src.startswith("//"):
            continue
        target = (output.parent / parsed.path).resolve()
        if not target.exists():
            errors.append(f"{relative(output)}: missing rendered logo asset '{src}' -> {target}")
    return errors


def write_validated_soup(soup: object, site_root: Path, output: Path) -> bool:
    errors = validate_logo_paths(soup, site_root, output)
    if errors:
        print("Render blocked: generated logo path is invalid")
        for error in errors:
            print(f"  - {error}")
        return False
    output.write_text(str(soup), encoding="utf-8")
    return True


def command_validate_page(args: argparse.Namespace) -> int:
    site_root = resolve_site_root(args.site)
    source = resolve_page_source(site_root, args.lang, args.page)
    if source is None or not source.exists():
        print(f"Page source not found: site={args.site} lang={args.lang} page={args.page}")
        return 2

    output, errors = validate_page_source(site_root, source)

    print(f"Page validation: {args.site} {args.lang} {args.page}")
    print(f"Source: {relative(source)}")
    if output is not None:
        print(f"Output: {relative(output)}")

    if errors:
        print(f"Errors: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Errors: 0")
    return 0


def command_validate_pages(args: argparse.Namespace) -> int:
    site_root = resolve_site_root(args.site)
    site_config = load_site_config(args.site)
    languages = list(site_config.languages) if args.lang == "all" else [args.lang]
    for language in languages:
        site_config.language(language)
    all_errors: list[str] = []
    checked = 0
    skipped = 0

    for language in languages:
        root = source_root(site_root, language)
        for source in collect_files(root, "*.md"):
            if not is_page_source(site_root, source):
                skipped += 1
                continue
            checked += 1
            _output, errors = validate_page_source(site_root, source)
            all_errors.extend(errors)

    print(f"Page validation: {args.site} {args.lang}")
    print(f"Markdown page sources checked: {checked}")
    print(f"Non-page Markdown sources skipped: {skipped}")

    if all_errors:
        print(f"Errors: {len(all_errors)}")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("Errors: 0")
    return 0


def parse_metadata_and_body(lines: list[str]) -> tuple[dict[str, str], str]:
    metadata: dict[str, str] = {}
    body_start = 0
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            body_start = index + 1
            break
        if ":" not in stripped:
            body_start = index
            break
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "|":
            block_lines: list[str] = []
            index += 1
            while index < len(lines):
                block_line = lines[index]
                if not block_line.strip():
                    block_lines.append("")
                    index += 1
                    continue
                if not block_line.startswith((" ", "\t")):
                    break
                block_lines.append(block_line.strip())
                index += 1
            metadata[key] = "\n".join(block_lines).strip()
            continue

        metadata[key] = value
        index += 1

    if index >= len(lines):
        body_start = len(lines)

    return metadata, "\n".join(lines[body_start:]).strip()


def parse_item(lines: list[str]) -> dict[str, object]:
    component: dict[str, object] | None = None
    metadata_lines = lines

    while metadata_lines and not metadata_lines[0].strip():
        metadata_lines = metadata_lines[1:]

    marker = parse_component_marker(metadata_lines[0]) if metadata_lines else None
    if marker:
        component = {"name": marker[0], "params": marker[1]}
        metadata_lines = metadata_lines[1:]

    metadata, body = parse_metadata_and_body(metadata_lines)
    if "body" in metadata:
        body = metadata["body"]

    return {"component": component, "metadata": metadata, "body": body}


def parse_component_marker(line: str) -> tuple[str, dict[str, str]] | None:
    marker = COMPONENT_MARKER_RE.match(line.strip())
    if not marker:
        return None

    raw_content = marker.group(1).strip()
    if "," in raw_content:
        name, raw_params = raw_content.split(",", 1)
    else:
        name, raw_params = raw_content, ""
    name = normalize_component_name(name.strip())
    raw_params = raw_params.strip()
    params: dict[str, str] = {}

    if raw_params:
        for raw_param in raw_params.split(","):
            raw_param = raw_param.strip()
            if not raw_param:
                continue
            if ":" not in raw_param:
                params[raw_param] = ""
                continue
            key, value = raw_param.split(":", 1)
            params[key.strip()] = value.strip()

    return name, params


def is_component_end_marker(line: str) -> bool:
    return bool(COMPONENT_END_MARKER_RE.match(line.strip()))


def normalize_component_name(name: str) -> str:
    return name.strip().lower()


def parse_component_blocks(markdown: str, component_name: str) -> list[dict[str, object]]:
    lines = markdown.splitlines()
    blocks: list[dict[str, object]] = []
    index = 0

    while index < len(lines):
        marker = parse_component_marker(lines[index])
        if not marker or marker[0] != component_name:
            index += 1
            continue

        component_params = marker[1]
        block_lines: list[str] = []
        index += 1
        inside_item = False
        current_item_has_content = False
        while index < len(lines):
            if is_component_end_marker(lines[index]):
                index += 1
                break
            next_component = parse_component_marker(lines[index])
            next_section = SECTION_HEADING_RE.match(lines[index].strip())
            next_item = ITEM_MARKER_RE.match(lines[index].strip())
            stripped_line = lines[index].strip()
            if next_section or (next_component and (not inside_item or current_item_has_content)):
                break
            if next_item:
                inside_item = True
                current_item_has_content = False
            elif stripped_line:
                current_item_has_content = True
            block_lines.append(lines[index])
            index += 1

        raw_parts: list[list[str]] = []
        component_lines: list[str] = []
        current_item: list[str] | None = None

        for line in block_lines:
            if ITEM_MARKER_RE.match(line.strip()):
                if current_item is not None:
                    raw_parts.append(current_item)
                current_item = []
                continue
            if current_item is None:
                component_lines.append(line)
            else:
                current_item.append(line)

        if current_item is not None:
            raw_parts.append(current_item)

        metadata, body = parse_metadata_and_body(component_lines)
        items = []
        for raw_item in raw_parts:
            items.append(parse_item(raw_item))

        blocks.append({"params": component_params, "metadata": metadata, "body": body, "items": items})

    return blocks


def parse_component_block_at(lines: list[str], start_index: int) -> tuple[str, dict[str, object], int] | None:
    marker = parse_component_marker(lines[start_index])
    if not marker:
        return None

    component_name, component_params = marker
    block_lines: list[str] = []
    index = start_index + 1
    inside_item = False
    current_item_has_content = False
    while index < len(lines):
        if is_component_end_marker(lines[index]):
            index += 1
            break
        next_component = parse_component_marker(lines[index])
        next_section = SECTION_HEADING_RE.match(lines[index].strip())
        next_item = ITEM_MARKER_RE.match(lines[index].strip())
        stripped_line = lines[index].strip()
        if next_section or (next_component and (not inside_item or current_item_has_content)):
            break
        if next_item:
            inside_item = True
            current_item_has_content = False
        elif stripped_line:
            current_item_has_content = True
        block_lines.append(lines[index])
        index += 1

    raw_parts: list[list[str]] = []
    component_lines: list[str] = []
    current_item: list[str] | None = None

    for line in block_lines:
        if ITEM_MARKER_RE.match(line.strip()):
            if current_item is not None:
                raw_parts.append(current_item)
            current_item = []
            continue
        if current_item is None:
            component_lines.append(line)
        else:
            current_item.append(line)

    if current_item is not None:
        raw_parts.append(current_item)

    metadata, body = parse_metadata_and_body(component_lines)
    block = {
        "params": component_params,
        "metadata": metadata,
        "body": body,
        "items": [parse_item(raw_item) for raw_item in raw_parts],
    }
    return component_name, block, index


def strip_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    frontmatter = {}
    match = FRONTMATTER_RE.match(markdown)
    if not match:
        return frontmatter, markdown

    if yaml is not None:
        loaded = yaml.safe_load(match.group(1)) or {}
        if isinstance(loaded, dict):
            frontmatter = loaded

    return frontmatter, markdown[match.end():]


def render_inline(text: object) -> str:
    escaped = html.escape(str(text or ""))
    escaped = re.sub(r"`([^`]+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def slugify(text: str) -> str:
    """Convert heading text to a lowercase hyphen-separated anchor id."""
    clean = re.sub(r"<[^>]+>", "", text)               # strip HTML tags
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)     # strip **bold**
    clean = re.sub(r"`(.+?)`", r"\1", clean)            # strip `code`
    clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)  # strip [link](url)
    clean = clean.lower().strip()
    for chars, base in [("àáâãä", "a"), ("èéêë", "e"), ("ìíîï", "i"), ("òóôõö", "o"), ("ùúûü", "u")]:
        for ch in chars:
            clean = clean.replace(ch, base)
    clean = re.sub(r"[^\w\s-]", "", clean)
    clean = re.sub(r"[\s_]+", "-", clean)
    return clean.strip("-") or "section"


def render_markdown_fragment(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    _seen_slugs: dict[str, int] = {}
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            output.append("<ul>")
            for item in list_items:
                output.append(f"  <li>{render_inline(item)}</li>")
            output.append("</ul>")
            list_items = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            index += 1
            continue

        if stripped.startswith("<"):
            flush_paragraph()
            flush_list()
            html_lines = [line]
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("#"):
                html_lines.append(lines[index])
                if lines[index].strip().startswith("</"):
                    index += 1
                    break
                index += 1
            output.append("\n".join(html_lines))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            heading_text = heading.group(2)
            heading_html = render_inline(heading_text)
            if level in (2, 3):
                slug = slugify(heading_text)
                if slug in _seen_slugs:
                    _seen_slugs[slug] += 1
                    slug = f"{slug}-{_seen_slugs[slug]}"
                else:
                    _seen_slugs[slug] = 0
                output.append(f'<h{level} id="{slug}">{heading_html}</h{level}>')
            else:
                output.append(f"<h{level}>{heading_html}</h{level}>")
            index += 1
            continue

        if stripped == "---":
            flush_paragraph()
            flush_list()
            index += 1
            continue

        # Eyebrow: standalone line wrapped in double dashes → <p class="eyebrow">
        eyebrow_m = EYEBROW_RE.match(stripped)
        if eyebrow_m:
            flush_paragraph()
            flush_list()
            output.append(f'<p class="eyebrow">{render_inline(eyebrow_m.group(1))}</p>')
            index += 1
            continue

        # Fenced code block (``` ... ```)
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            code_lines = []
            index += 1
            while index < len(lines):
                if lines[index].strip().startswith("```"):
                    index += 1
                    break
                code_lines.append(lines[index])
                index += 1
            escaped = html.escape("\n".join(code_lines))
            output.append(f"<pre><code>{escaped}</code></pre>")
            continue

        # Markdown table (| col | col |)
        if stripped.startswith("|"):
            flush_paragraph()
            flush_list()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            # row[0]=headers, row[1]=separator (---), row[2+]=data
            rows = []
            for row_line in table_lines:
                cells = [c.strip() for c in row_line.strip("|").split("|")]
                rows.append(cells)
            if len(rows) >= 2:
                thead_cells = rows[0]
                tbody_rows = rows[2:] if len(rows) > 2 else []
                html_parts = ["<table>", "<thead><tr>"]
                for cell in thead_cells:
                    html_parts.append(f"<th>{render_inline(cell)}</th>")
                html_parts.append("</tr></thead>")
                if tbody_rows:
                    html_parts.append("<tbody>")
                    for tr in tbody_rows:
                        html_parts.append("<tr>")
                        for cell in tr:
                            html_parts.append(f"<td>{render_inline(cell)}</td>")
                        html_parts.append("</tr>")
                    html_parts.append("</tbody>")
                html_parts.append("</table>")
                output.append("\n".join(html_parts))
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(stripped[2:])
            index += 1
            continue

        flush_list()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    flush_list()
    return "\n".join(output)


class DeclarativeBindingError(ValueError):
    pass


def binding_value(context: dict[str, object], path: str) -> object:
    current: object = context
    for part in path.split("."):
        if part == "$item":
            part = "$item"
        if not isinstance(current, dict) or part not in current:
            raise DeclarativeBindingError(f"binding value not found: {path}")
        current = current[part]
    return current


def optional_binding_value(context: dict[str, object], path: str) -> object | None:
    try:
        return binding_value(context, path)
    except DeclarativeBindingError:
        return None


def binding_items(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [] if value is None else [value]


def binding_is_present(value: object) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def remove_missing_binding_target(tag: object, fragment: object) -> bool:
    """Remove WYSIWYG preview markup for an absent source binding.

    Returns True when the bound node is the fragment root and the caller should
    stop processing that fragment.
    """
    if tag is fragment:
        tag.clear()
        return True
    tag.decompose()
    return False


def format_binding_value(value: object, directive: str) -> str:
    if directive.startswith("zero-pad:"):
        width_text = directive.split(":", 1)[1]
        if not width_text.isdigit():
            raise DeclarativeBindingError(f"invalid zero-pad width: {width_text}")
        text = str(value)
        return text.zfill(int(width_text)) if text.isdigit() else text
    raise DeclarativeBindingError(f"unknown binding format: {directive}")


def nested_component_context(value: object) -> tuple[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise DeclarativeBindingError("component binding must reference an item object")
    component = value.get("component")
    metadata = value.get("metadata")
    if not isinstance(component, dict) or not component.get("name"):
        raise DeclarativeBindingError("component binding item has no component name")
    if not isinstance(metadata, dict):
        metadata = {}
    return str(component["name"]), {
        **metadata,
        "body": metadata.get("body") or value.get("body", ""),
        "params": component.get("params", {}),
        "items": value.get("items", []),
    }


def bind_declarative_fragment(
    fragment: object,
    context: dict[str, object],
    *,
    site_root: Path | None = None,
    output: Path | None = None,
    language_outputs: dict[str, str] | None = None,
) -> None:
    repeat_nodes = []
    if getattr(fragment, "attrs", None) and fragment.attrs.get("data-websmith-repeat"):
        repeat_nodes.append(fragment)
    repeat_nodes.extend(fragment.select("[data-websmith-repeat]"))
    for container in repeat_nodes:
        value_path = str(container.get("data-websmith-repeat") or "")
        value = optional_binding_value(context, value_path)
        if not binding_is_present(value):
            if remove_missing_binding_target(container, fragment):
                return
            continue
        values = binding_items(value)
        item_template = container.select_one("[data-websmith-repeat-item]")
        if item_template is None:
            raise DeclarativeBindingError(
                f"repeat binding '{value_path}' has no data-websmith-repeat-item"
            )
        rendered_items = []
        for value in values:
            item_soup = BeautifulSoup(str(item_template), "html.parser")
            item = item_soup.find()
            item_context = {**context, "$item": value}
            bind_declarative_fragment(
                item,
                item_context,
                site_root=site_root,
                output=output,
                language_outputs=language_outputs,
            )
            item.attrs.pop("data-websmith-repeat-item", None)
            rendered_items.append(item)
        container.clear()
        for item in rendered_items:
            container.append(item)
        container.attrs.pop("data-websmith-repeat", None)

    conditional_nodes = []
    if getattr(fragment, "attrs", None) and fragment.attrs.get("data-websmith-if"):
        conditional_nodes.append(fragment)
    conditional_nodes.extend(fragment.select("[data-websmith-if]"))
    for tag in reversed(conditional_nodes):
        value_path = str(tag.attrs.pop("data-websmith-if"))
        if not binding_is_present(optional_binding_value(context, value_path)):
            if tag is fragment:
                tag.clear()
                return
            tag.decompose()

    conditional_not_nodes = []
    if getattr(fragment, "attrs", None) and fragment.attrs.get("data-websmith-if-not"):
        conditional_not_nodes.append(fragment)
    conditional_not_nodes.extend(fragment.select("[data-websmith-if-not]"))
    for tag in reversed(conditional_not_nodes):
        value_path = str(tag.attrs.pop("data-websmith-if-not"))
        if binding_is_present(optional_binding_value(context, value_path)):
            if tag is fragment:
                tag.clear()
                return
            tag.decompose()

    conditional_any_nodes = []
    if getattr(fragment, "attrs", None) and fragment.attrs.get("data-websmith-if-any"):
        conditional_any_nodes.append(fragment)
    conditional_any_nodes.extend(fragment.select("[data-websmith-if-any]"))
    for tag in conditional_any_nodes:
        expression = str(tag.attrs.pop("data-websmith-if-any"))
        value_paths = [part.strip() for part in expression.split(";") if part.strip()]
        if not value_paths:
            raise DeclarativeBindingError("data-websmith-if-any requires at least one path")
        if not any(
            binding_is_present(optional_binding_value(context, value_path))
            for value_path in value_paths
        ):
            if tag is fragment:
                tag.clear()
                return
            tag.decompose()

    choice_nodes = []
    if getattr(fragment, "attrs", None) and fragment.attrs.get("data-websmith-choice"):
        choice_nodes.append(fragment)
    choice_nodes.extend(fragment.select("[data-websmith-choice]"))
    for tag in choice_nodes:
        expression = str(tag.attrs.pop("data-websmith-choice"))
        parts = expression.split("|", 1)
        value = optional_binding_value(context, parts[0].strip())
        if not binding_is_present(value) and len(parts) > 1:
            value = parts[1]
        if not binding_is_present(value):
            if remove_missing_binding_target(tag, fragment):
                return
            continue
        candidates = [
            child
            for child in tag.find_all(attrs={"data-websmith-value": True}, recursive=False)
            if str(child.get("data-websmith-value")) == str(value)
        ]
        if len(candidates) != 1:
            raise DeclarativeBindingError(
                f"choice binding '{expression}' matched {len(candidates)} variants for '{value}'"
            )
        selected = candidates[0]
        selected.attrs.pop("data-websmith-value", None)
        tag.clear()
        tag.append(selected)

    for tag in [fragment, *fragment.find_all(True)]:
        if getattr(tag, "attrs", None) is None:
            continue
        text_path = tag.attrs.pop("data-websmith-text", None)
        if text_path:
            value = optional_binding_value(context, str(text_path))
            if not binding_is_present(value):
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            format_directive = str(tag.attrs.pop("data-websmith-format", "") or "")
            if format_directive:
                value = format_binding_value(value, format_directive)
            tag.clear()
            tag.append(str(value))

        inline_path = tag.attrs.pop("data-websmith-inline", None)
        if inline_path:
            value = optional_binding_value(context, str(inline_path))
            if not binding_is_present(value):
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            tag.clear()
            append_html_fragment(
                fragment if hasattr(fragment, "new_tag") else tag,
                tag,
                render_inline(value),
            )

        optional_inline_path = tag.attrs.pop("data-websmith-inline-optional", None)
        if optional_inline_path:
            value = optional_binding_value(context, str(optional_inline_path))
            if not binding_is_present(value):
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            tag.clear()
            append_html_fragment(
                fragment if hasattr(fragment, "new_tag") else tag,
                tag,
                render_inline(value),
            )

        markdown_path = tag.attrs.pop("data-websmith-markdown", None)
        if markdown_path:
            value = optional_binding_value(context, str(markdown_path))
            if not binding_is_present(value):
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            tag.clear()
            append_html_fragment(
                fragment if hasattr(fragment, "new_tag") else tag,
                tag,
                render_markdown_fragment(str(value)),
            )

        attribute_bindings = str(tag.attrs.pop("data-websmith-attribute", "") or "")
        missing_attribute_value = False
        for raw_binding in attribute_bindings.split(";"):
            if not raw_binding.strip():
                continue
            if ":" not in raw_binding:
                raise DeclarativeBindingError(f"invalid attribute binding: {raw_binding}")
            attribute, value_path = raw_binding.split(":", 1)
            value = optional_binding_value(context, value_path.strip())
            if not binding_is_present(value):
                missing_attribute_value = True
                break
            tag[attribute.strip()] = str(value)
        if missing_attribute_value:
            if remove_missing_binding_target(tag, fragment):
                return
            continue

        prefixed_attributes = str(
            tag.attrs.pop("data-websmith-attribute-prefix-if-bare", "") or ""
        )
        missing_prefixed_value = False
        for raw_binding in prefixed_attributes.split(";"):
            if not raw_binding.strip():
                continue
            parts = raw_binding.split(":", 1)
            if len(parts) != 2 or "|" not in parts[1]:
                raise DeclarativeBindingError(
                    f"invalid prefixed attribute binding: {raw_binding}"
                )
            attribute, expression = parts
            value_path, prefix = expression.split("|", 1)
            source_value = optional_binding_value(context, value_path.strip())
            if not binding_is_present(source_value):
                missing_prefixed_value = True
                break
            value = str(source_value)
            tag[attribute.strip()] = f"{prefix}{value}" if "/" not in value else value
        if missing_prefixed_value:
            if remove_missing_binding_target(tag, fragment):
                return
            continue

        templated_attributes = str(
            tag.attrs.pop("data-websmith-attribute-template", "") or ""
        )
        missing_templated_value = False
        for raw_binding in templated_attributes.split(";"):
            if not raw_binding.strip():
                continue
            if ":" not in raw_binding:
                raise DeclarativeBindingError(
                    f"invalid templated attribute binding: {raw_binding}"
                )
            attribute, template = raw_binding.split(":", 1)

            def replace_placeholder(match: re.Match[str]) -> str:
                nonlocal missing_templated_value
                value = optional_binding_value(context, match.group(1))
                if not binding_is_present(value):
                    missing_templated_value = True
                    return ""
                return str(value)

            tag[attribute.strip()] = re.sub(r"\$\{([^}]+)\}", replace_placeholder, template)
            if missing_templated_value:
                break
        if missing_templated_value:
            if remove_missing_binding_target(tag, fragment):
                return
            continue

        class_binding = str(tag.attrs.pop("data-websmith-class-if-contains", "") or "")
        if class_binding:
            parts = class_binding.split(":", 2)
            if len(parts) != 3:
                raise DeclarativeBindingError(f"invalid class binding: {class_binding}")
            class_name, value_path, expected = parts
            if expected.lower() in str(optional_binding_value(context, value_path) or "").lower():
                classes = list(tag.get("class") or [])
                if class_name not in classes:
                    tag["class"] = [*classes, class_name]

        class_if_present = str(
            tag.attrs.pop("data-websmith-class-if-present", "") or ""
        )
        if class_if_present:
            parts = class_if_present.split(":", 1)
            if len(parts) != 2:
                raise DeclarativeBindingError(
                    f"invalid class-if-present binding: {class_if_present}"
                )
            class_name, value_path = parts
            if not re.fullmatch(r"[-_a-zA-Z0-9]+", class_name):
                raise DeclarativeBindingError(
                    f"invalid class in binding '{class_if_present}': {class_name}"
                )
            if binding_is_present(optional_binding_value(context, value_path)):
                classes = list(tag.get("class") or [])
                if class_name not in classes:
                    tag["class"] = [*classes, class_name]

        classes_from_binding = str(tag.attrs.pop("data-websmith-classes-from", "") or "")
        if classes_from_binding:
            parts = classes_from_binding.split("|", 2)
            value_path = parts[0].strip()
            prefix = parts[1] if len(parts) > 1 else ""
            default = parts[2] if len(parts) > 2 else ""
            value = optional_binding_value(context, value_path)
            tokens = str(value if binding_is_present(value) else default).split()
            classes = list(tag.get("class") or [])
            for token in tokens:
                class_name = f"{prefix}{token}"
                if not re.fullmatch(r"[-_a-zA-Z0-9]+", class_name):
                    raise DeclarativeBindingError(
                        f"invalid class generated by binding '{classes_from_binding}': {class_name}"
                    )
                if class_name not in classes:
                    classes.append(class_name)
            tag["class"] = classes

        class_from_binding = str(tag.attrs.pop("data-websmith-class-from", "") or "")
        if class_from_binding:
            parts = class_from_binding.split("|", 2)
            value_path = parts[0].strip()
            prefix = parts[1] if len(parts) > 1 else ""
            default = parts[2] if len(parts) > 2 else ""
            value = optional_binding_value(context, value_path)
            if not binding_is_present(value):
                value = default
            class_name = f"{prefix}{value}".strip()
            if not class_name or not re.fullmatch(r"[-_a-zA-Z0-9]+", class_name):
                raise DeclarativeBindingError(
                    f"invalid class generated by binding '{class_from_binding}': {class_name}"
                )
            classes = list(tag.get("class") or [])
            if class_name not in classes:
                tag["class"] = [*classes, class_name]

        component_path = tag.attrs.pop("data-websmith-component", None)
        if component_path:
            if site_root is None:
                raise DeclarativeBindingError("component binding requires site context")
            component_value = optional_binding_value(context, str(component_path))
            if not binding_is_present(component_value):
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            component_name, component_context = nested_component_context(
                component_value
            )
            rendered = render_catalog_component(site_root, component_name, component_context)
            if rendered is None:
                raise DeclarativeBindingError(
                    f"component '{component_name}' has no catalog render contract"
                )
            replacement_soup = BeautifulSoup(rendered, "html.parser")
            replacement = replacement_soup.find()
            if replacement is None:
                raise DeclarativeBindingError(
                    f"component '{component_name}' rendered an empty fragment"
                )
            tag.replace_with(replacement)
            continue

        content_id = tag.attrs.pop("data-websmith-content-href", None)
        if content_id:
            if site_root is None or output is None:
                raise DeclarativeBindingError("content href binding requires page context")
            href = resolve_content_url(f"[{content_id}]", site_root, output)
            if href == f"[{content_id}]":
                raise DeclarativeBindingError(
                    f"content id not found for binding: {content_id}"
                )
            fragment_id = str(tag.attrs.pop("data-websmith-fragment", "") or "")
            tag["href"] = f"{href}#{fragment_id}" if fragment_id else href

        language_id = tag.attrs.pop("data-websmith-language", None)
        if language_id:
            if output is None or language_outputs is None or language_id not in language_outputs:
                previous = tag.find_previous_sibling()
                following = tag.find_next_sibling()
                for sibling in (previous, following):
                    sibling_classes = getattr(sibling, "attrs", {}).get("class", []) if sibling else []
                    if "separator" in sibling_classes:
                        sibling.decompose()
                        break
                if remove_missing_binding_target(tag, fragment):
                    return
                continue
            tag["href"] = os.path.relpath(Path(language_outputs[str(language_id)]), output.parent)

        output_binding = str(tag.attrs.pop("data-websmith-output-path", "") or "")
        if output_binding:
            if output is None or ":" not in output_binding:
                raise DeclarativeBindingError(f"invalid output path binding: {output_binding}")
            attribute, target = output_binding.split(":", 1)
            site_output_root = config_for_root(site_root).output_root if site_root else None
            if site_output_root is None:
                raise DeclarativeBindingError("output path binding requires site context")
            target_path = (site_output_root / target).resolve()
            try:
                target_path.relative_to(site_output_root.resolve())
            except ValueError as exc:
                raise DeclarativeBindingError(
                    f"output path binding escapes the site output: {target}"
                ) from exc
            tag[attribute] = os.path.relpath(target_path, output.parent)


def render_catalog_component(
    site_root: Path | None,
    component_name: str,
    context: dict[str, object],
) -> str | None:
    if site_root is None:
        return None
    specification = component_catalog_for_root(site_root).get(component_name, {})
    render = specification.get("render") if isinstance(specification, dict) else None
    if not isinstance(render, dict):
        return None
    template_name = str(render.get("template", ""))
    selector = str(render.get("selector", ""))
    if not template_name or not selector:
        raise DeclarativeBindingError(
            f"component '{component_name}' has an incomplete render contract"
        )
    components_root = config_for_root(site_root).components_root.resolve()
    template_path = (components_root / template_name).resolve()
    try:
        template_path.relative_to(components_root)
    except ValueError as exc:
        raise DeclarativeBindingError(
            f"component template escapes the component root: {template_name}"
        ) from exc
    if not template_path.is_file():
        raise DeclarativeBindingError(
            f"component template not found: {relative(template_path)}"
        )
    template_soup = BeautifulSoup(read_text(template_path), "html.parser")
    fragment = template_soup.select_one(selector)
    if fragment is None:
        raise DeclarativeBindingError(
            f"component '{component_name}' selector not found: {selector}"
        )
    defaults = render.get("defaults", {})
    if defaults is not None and not isinstance(defaults, dict):
        raise DeclarativeBindingError(
            f"component '{component_name}' render defaults must be a mapping"
        )
    resolved_context = resolve_catalog_content_context(
        site_root,
        context,
        render,
        component_name,
    )
    bind_declarative_fragment(
        fragment,
        {**(defaults or {}), **resolved_context},
        site_root=site_root,
    )
    return str(fragment)


def build_content_source_reference_map(site_root: Path) -> dict[str, Path]:
    references: dict[str, Path] = {}
    for source in collect_files(config_for_root(site_root).contents_root, "*.md"):
        metadata, _body = strip_frontmatter(read_text(source))
        for key in ("id", "slug"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                references[value.strip()] = source
        references[source.stem] = source
    return references


def resolve_catalog_content_context(
    site_root: Path,
    context: dict[str, object],
    render: dict[str, object],
    component_name: str,
) -> dict[str, object]:
    resolve_content = render.get("resolve_content")
    if resolve_content is None:
        return context
    if not isinstance(resolve_content, dict):
        raise DeclarativeBindingError(
            f"component '{component_name}' resolve_content must be a mapping"
        )
    items_spec = resolve_content.get("items")
    if not isinstance(items_spec, dict):
        raise DeclarativeBindingError(
            f"component '{component_name}' resolve_content.items must be a mapping"
        )
    reference_path = str(items_spec.get("reference", "")).strip()
    target_key = str(items_spec.get("as", "")).strip()
    required = bool(items_spec.get("required", True))
    if not reference_path or not target_key:
        raise DeclarativeBindingError(
            f"component '{component_name}' content resolution requires reference and as"
        )

    items = context.get("items")
    if not isinstance(items, list):
        raise DeclarativeBindingError(
            f"component '{component_name}' content resolution requires an items list"
        )
    source_map = build_content_source_reference_map(site_root)
    resolved_items: list[object] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise DeclarativeBindingError(
                f"component '{component_name}' item {index} must be a mapping"
            )
        reference_value = optional_binding_value(item, reference_path)
        if not binding_is_present(reference_value):
            if required:
                raise DeclarativeBindingError(
                    f"component '{component_name}' item {index} is missing content reference '{reference_path}'"
                )
            resolved_items.append(item)
            continue
        reference_id = content_reference_id(reference_value)
        if reference_id is None:
            raise DeclarativeBindingError(
                f"component '{component_name}' item {index} has invalid content reference '{reference_value}'"
            )
        source = source_map.get(reference_id)
        if source is None:
            raise DeclarativeBindingError(
                f"component '{component_name}' item {index} has unresolved content reference '[{reference_id}]'"
            )
        metadata, body = strip_frontmatter(read_text(source))
        anchor = str(metadata.get("slug") or source.stem).strip()
        resolved_item = dict(item)
        resolved_item[target_key] = {
            "id": reference_id,
            "anchor": anchor,
            "page": metadata,
            "body": body,
        }
        resolved_items.append(resolved_item)

    return {**context, "items": resolved_items}


def render_component_item(item: dict[str, object], site_root: Path | None = None) -> str:
    component = item.get("component") or {}
    metadata = item.get("metadata") or {}
    name = component.get("name") if isinstance(component, dict) else None

    catalog_context = {
        **metadata,
        "body": metadata.get("body") or item.get("body", ""),
        "params": component.get("params", {}) if isinstance(component, dict) else {},
    }
    catalog_rendered = render_catalog_component(site_root, str(name or ""), catalog_context)
    if catalog_rendered is not None:
        return catalog_rendered

    raise DeclarativeBindingError(
        f"component '{name or '<missing>'}' has no catalog render contract"
    )


def render_component(name: str, block: dict[str, object], site_root: Path | None = None) -> str:
    metadata = block.get("metadata") or {}
    params = block.get("params") or {}
    items = block.get("items") or []

    catalog_context = {
        **metadata,
        "body": block.get("body", ""),
        "items": items,
        "params": params,
    }
    catalog_rendered = render_catalog_component(site_root, name, catalog_context)
    if catalog_rendered is not None:
        return catalog_rendered

    raise DeclarativeBindingError(
        f"component '{name}' has no catalog render contract"
    )


def render_markdown_with_components(markdown: str, site_root: Path | None = None) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    buffer: list[str] = []
    index = 0

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer:
            output.append(render_markdown_fragment("\n".join(buffer)))
            buffer = []

    while index < len(lines):
        if parse_component_marker(lines[index]):
            flush_buffer()
            parsed = parse_component_block_at(lines, index)
            if parsed is None:
                index += 1
                continue
            name, block, index = parsed
            output.append(render_component(name, block, site_root))
            continue
        buffer.append(lines[index])
        index += 1

    flush_buffer()
    return "\n".join(part for part in output if part.strip())


def iter_component_blocks(markdown: str) -> list[tuple[str, dict[str, object]]]:
    lines = markdown.splitlines()
    components: list[tuple[str, dict[str, object]]] = []
    index = 0
    while index < len(lines):
        if not parse_component_marker(lines[index]):
            index += 1
            continue
        parsed = parse_component_block_at(lines, index)
        if parsed is None:
            index += 1
            continue
        name, block, index = parsed
        components.append((name, block))
    return components


def extract_h2_toc(body: str) -> list[tuple[str, str]]:
    """Return (display_text, anchor_id) for every ## heading in the Markdown body.

    Applies the same slug deduplication used by render_markdown_fragment so that
    the generated href values always match the id attributes on the rendered headings.
    """
    entries: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+)$", line.strip())
        if not m:
            continue
        raw = m.group(1)
        # Strip Markdown formatting for the visible label
        display = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
        display = re.sub(r"`(.+?)`", r"\1", display)
        display = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", display)
        display = display.strip()
        slug = slugify(raw)
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 0
        entries.append((display, slug))
    return entries


def inject_toc(soup: object, body: str) -> None:
    """Populate a template-declared TOC with entries derived from ## headings."""
    toc_list = soup.select_one("[data-websmith-toc]")
    if toc_list is None:
        return
    toc_list.attrs.pop("data-websmith-toc", None)
    entries = extract_h2_toc(body)
    toc_list.clear()
    if not entries:
        return
    items_html = "".join(
        f'<li><a href="#{html.escape(slug)}">{html.escape(text)}</a></li>'
        for text, slug in entries
    )
    append_html_fragment(soup, toc_list, items_html)


def set_tag_text(soup: object, selector: str, value: object) -> None:
    tag = soup.select_one(selector)
    if tag is not None:
        tag.clear()
        tag.append(str(value or ""))


def set_meta_content(soup: object, selector: str, value: object) -> None:
    tag = soup.select_one(selector)
    if tag is not None:
        tag["content"] = str(value or "")


def set_link_href(soup: object, selector: str, value: object) -> None:
    tag = soup.select_one(selector)
    if tag is not None:
        tag["href"] = str(value or "")


def set_image_source(soup: object, selector: str, src: str, alt: str) -> None:
    tag = soup.select_one(selector)
    if tag is not None:
        tag["src"] = src
        tag["alt"] = alt


def append_html_fragment(soup: object, parent: object, html_fragment: str) -> None:
    fragment = BeautifulSoup(html_fragment, "html.parser")
    for child in list(fragment.contents):
        parent.append(child)


def rewrite_internal_markdown_links(
    content_target: object,
    site_root: Path | None = None,
    output: Path | None = None,
) -> None:
    for link in content_target.select("a[href]"):
        href = str(link.get("href") or "")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
            continue
        reference_url = resolve_content_url(href, site_root, output)
        if reference_url != href:
            link["href"] = reference_url
            continue
        if ".md" not in href:
            continue
        link["href"] = re.sub(r"\.md(?=([#?]|$))", ".html", href)


def rewrite_template_paths(
    soup: object,
    *,
    configured_path_map: dict[str, str],
    template_image_prefix: str,
    published_image_prefix: str,
    published_styles: dict[str, str],
) -> None:
    path_map = configured_path_map

    for tag in soup.find_all(["a", "link", "script", "img", "form"]):
        for attr in ("href", "src", "action"):
            value = tag.get(attr)
            if value in path_map:
                tag[attr] = path_map[value]
            elif isinstance(value, str) and value.startswith(f"{template_image_prefix}/"):
                suffix = value.removeprefix(f"{template_image_prefix}/")
                tag[attr] = f"{published_image_prefix}/{suffix}"

    main_css_href = published_styles.get("main.css")
    components_css_href = published_styles.get("components.css")
    main_css = soup.select_one(f'link[rel="stylesheet"][href="{main_css_href}"]') if main_css_href else None
    components_css = soup.select_one(f'link[rel="stylesheet"][href="{components_css_href}"]') if components_css_href else None
    if main_css is not None and components_css is None and components_css_href:
        new_link = soup.new_tag("link", rel="stylesheet", href=components_css_href)
        main_css.insert_after(new_link)

def content_reference_id(value: object) -> str | None:
    if isinstance(value, list) and len(value) == 1:
        return str(value[0]).strip()
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\[([A-Za-z0-9_-]+)\]", value.strip())
    return match.group(1) if match else None


def infer_content_output(site_root: Path, source: Path, metadata: dict[str, object]) -> Path | None:
    site_config = config_for_root(site_root)
    canonical_language = site_config.canonical_language
    try:
        relative_source = source.relative_to(site_config.contents_root)
    except ValueError:
        return None
    language = canonical_language
    relative_parts = relative_source.parts
    if relative_parts and relative_parts[0] in site_config.languages:
        language = relative_parts[0]
        relative_source = Path(*relative_parts[1:])

    page_id = str(metadata.get("id") or metadata.get("source_id") or source.stem).strip()
    overrides = site_config.routing.get("output_overrides", {})
    if isinstance(overrides, dict):
        configured = overrides.get(page_id)
        if isinstance(configured, str) and configured.strip():
            return output_root(site_root, language) / configured.strip().lstrip("/")

    strip_prefixes = site_config.routing.get("strip_source_prefixes", [])
    if (
        isinstance(strip_prefixes, list)
        and relative_source.parts
        and relative_source.parts[0] in {str(value) for value in strip_prefixes}
    ):
        relative_source = Path(*relative_source.parts[1:])
    if not relative_source.parts:
        return None
    return output_root(site_root, language) / relative_source.with_suffix(".html")


def build_content_reference_map(site_root: Path) -> dict[str, Path]:
    references: dict[str, Path] = {}
    for source in collect_files(config_for_root(site_root).contents_root, "*.md"):
        metadata, _body = strip_frontmatter(read_text(source))
        output = infer_content_output(site_root, source, metadata)
        if output is None:
            continue
        for key in ("id", "slug"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                references[value.strip()] = output
        references[source.stem] = output
    return references


def resolve_content_url(value: object, site_root: Path | None = None, output: Path | None = None) -> str:
    reference_id = content_reference_id(value)
    if reference_id is None:
        return str(value or "").strip()
    if site_root is None or output is None:
        return f"[{reference_id}]"

    language = output_language(site_root, output)
    if language is not None:
        resolved_page = resolve_page_by_id(site_root, reference_id, language)
        if resolved_page is not None:
            _canonical_source, language_source, canonical_metadata = resolved_page
            language_target = infer_content_output(site_root, language_source, canonical_metadata)
            if language_target is not None:
                return os.path.relpath(language_target, output.parent)

    target = build_content_reference_map(site_root).get(reference_id)
    if target is None:
        return f"[{reference_id}]"
    return os.path.relpath(target, output.parent)


def render_template_schema(
    soup: object,
    metadata: dict[str, object],
    site_config: SiteConfig,
    canonical_url: str,
) -> None:
    script = soup.select_one('script[type="application/ld+json"]')
    if script is None:
        return
    schema_org = metadata.get("schema_org")
    if isinstance(schema_org, dict) and isinstance(schema_org.get("data"), dict):
        schema_data = dict(schema_org["data"])
        schema_data["@context"] = "https://schema.org"
        schema_data["@type"] = str(schema_org.get("type", "WebPage"))
        if isinstance(schema_data.get("offers"), dict) and "type" in schema_data["offers"]:
            schema_data["offers"] = dict(schema_data["offers"])
            schema_data["offers"]["@type"] = schema_data["offers"].pop("type")
        schema_data["publisher"] = {
            "@type": "Organization",
            "name": site_config.organization,
            "logo": {
                "@type": "ImageObject",
                "url": site_config.published_logo_url,
            },
        }
        schema_data["url"] = canonical_url
        script.string = json.dumps(schema_data, ensure_ascii=False, indent=4)
        return

    title = str(metadata.get("seo_title", metadata.get("title", "")))
    description = str(metadata.get("abstract", metadata.get("description", "")))
    keywords = metadata.get("keywords", [])
    schema_type = str(metadata.get("schema_type") or "WebPage")
    schema_image = str(metadata.get("schema_image") or "").strip()
    schema_author = metadata.get("schema_author")
    if isinstance(schema_author, dict):
        author_type = str(schema_author.get("type") or "Organization")
        author_name = str(schema_author.get("name") or site_config.organization)
    else:
        author_type = "Organization"
        author_name = str(metadata.get("author") or site_config.organization)
    schema = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "headline": title,
        "description": description,
        "author": {"@type": author_type, "name": author_name},
        "publisher": {
            "@type": "Organization",
            "name": site_config.organization,
            "logo": {
                "@type": "ImageObject",
                "url": site_config.published_logo_url,
            },
        },
        "image": schema_image,
        "datePublished": str(metadata.get("date", "")),
        "dateModified": str(metadata.get("last_updated", metadata.get("date", ""))),
        "keywords": ", ".join(str(keyword) for keyword in keywords) if isinstance(keywords, list) else str(keywords or ""),
        "inLanguage": str(metadata.get("lang", "it")),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical_url,
        },
    }
    script.string = json.dumps(schema, ensure_ascii=False, indent=4)


def public_destination_url(site_config: SiteConfig, destination: str) -> str:
    public_path = destination.strip().lstrip("/")
    if public_path.endswith("index.html"):
        public_path = public_path.removesuffix("index.html")
    return f"{site_config.base_url}/{public_path}"


def public_output_url(site_config: SiteConfig, output: Path) -> str:
    relative_output = output.relative_to(site_config.output_root).as_posix()
    return public_destination_url(site_config, relative_output)


def render_root_index_html(site_config: SiteConfig) -> str:
    redirect = site_config.root_redirect
    default_language = str(redirect["default_language"])
    destinations = redirect["destinations"]
    language_labels = redirect["language_labels"]
    default_destination = str(destinations[default_language])
    default_public_url = public_destination_url(site_config, default_destination)
    html_language = str(site_config.language(default_language)["html_lang"])

    alternate_links = "\n".join(
        "    <link rel=\"alternate\" "
        f"hreflang=\"{html_attr(hreflang)}\" "
        f"href=\"{html_attr(public_destination_url(site_config, str(destinations[language])))}\">"
        for language, hreflang in redirect["alternates"].items()
    )
    alternate_block = (
        "    <!-- Alternate per lingue -->\n"
        f"{alternate_links}\n"
        f'    <link rel="alternate" hreflang="x-default" href="{html_attr(default_public_url)}">'
    )

    template = site_config.root / str(redirect["template"])
    html_doc = read_text(template)
    html_doc = re.sub(
        r'<html\s+lang="[^"]*">',
        f'<html lang="{html_attr(html_language)}">',
        html_doc,
        count=1,
    )
    html_doc = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(str(redirect['title']))}</title>",
        html_doc,
        count=1,
        flags=re.DOTALL,
    )
    html_doc = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*">',
        f'<meta name="description" content="{html_attr(redirect["description"])}">',
        html_doc,
        count=1,
    )
    html_doc = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*">',
        f'<link rel="canonical" href="{html_attr(default_public_url)}">',
        html_doc,
        count=1,
    )
    html_doc = re.sub(
        r"<!-- websmith:alternates -->.*?<!-- /websmith:alternates -->",
        alternate_block,
        html_doc,
        count=1,
        flags=re.DOTALL,
    )
    html_doc = re.sub(
        r'<script\s+id="websmith-root-redirect">.*?</script>',
        (
            "<script>\n"
            "        // Redirect immediato senza attesa\n"
            f"        window.location.href = {json.dumps(default_destination, ensure_ascii=False)};\n"
            "    </script>"
        ),
        html_doc,
        count=1,
        flags=re.DOTALL,
    )
    html_doc = re.sub(
        r'<meta\s+id="websmith-root-refresh"\s+http-equiv="refresh"\s+content="[^"]*">',
        (
            '<meta http-equiv="refresh" '
            f'content="0;url={html_attr(default_destination)}">'
        ),
        html_doc,
        count=1,
    )
    for language, destination in destinations.items():
        html_doc = re.sub(
            rf'<a\s+data-websmith-language="{re.escape(str(language))}"\s+href="[^"]*">.*?</a>',
            f'<a href="{html_attr(destination)}">{html.escape(str(language_labels[language]))}</a>',
            html_doc,
            count=1,
        )
    return html_doc


def command_render_root_index(args: argparse.Namespace) -> int:
    site_config = load_site_config(args.site)
    redirect = site_config.root_redirect
    if not bool(redirect["enabled"]):
        print(f"Root redirect disabled for site: {site_config.name}")
        return 0

    output = site_config.root / str(redirect["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_root_index_html(site_config), encoding="utf-8")
    print(f"Rendered: {relative(output)}")
    return 0


def command_render_index(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the Markdown/front-matter page renderer."""
    return command_render_page(
        argparse.Namespace(site="techreloaded", page_id="home", lang=args.lang, all_langs=False)
    )


def render_generic_markdown_page(
    *,
    site_root: Path,
    source: Path,
    canonical_metadata: dict[str, object],
    output: Path,
    language: str,
) -> int:
    if BeautifulSoup is None:
        print("BeautifulSoup is required for render-page")
        return 2

    site_config = config_for_root(site_root)
    labels = language_config(site_root, language)
    style_publish_rules = site_config.style_publish_rules

    if not require_source(source):
        return 2
    if not validate_source_before_render(site_root, source):
        return 1
    metadata, body = strip_frontmatter(read_text(source))
    metadata.setdefault("lang", labels["html_lang"])
    template_name = template_file_name(
        metadata,
        template_file_name(canonical_metadata, site_config.default_template),
    )

    uses_current_html = template_name == "current-html"
    if uses_current_html:
        current_html = metadata.get("current_html")
        if isinstance(current_html, str) and current_html.strip():
            template = REPO_ROOT / current_html.strip()
            if not template.exists():
                template = site_root / current_html.strip()
        else:
            template = output
        if not require_file(template, "Current HTML"):
            return 2
    else:
        template = site_config.templates_root / template_name
        if not require_file(template, "Template"):
            return 2
    for style_source, _style_output in style_publish_rules:
        if not require_file(style_source, "Configured CSS"):
            return 2

    soup = BeautifulSoup(read_text(template), "html.parser")
    if soup.html is not None:
        soup.html["lang"] = labels["html_lang"]

    configured_path_map = {
        os.path.relpath(source_path, site_config.templates_root): os.path.relpath(destination, output.parent)
        for source_path, destination in style_publish_rules
    }
    configured_path_map[
        os.path.relpath(site_config.logo_source, site_config.templates_root)
    ] = os.path.relpath(site_config.published_logo, output.parent)
    published_styles = {
        source_path.name: os.path.relpath(destination, output.parent)
        for source_path, destination in style_publish_rules
    }
    rewrite_template_paths(
        soup,
        configured_path_map=configured_path_map,
        template_image_prefix=os.path.relpath(
            site_config.shared_images_source,
            site_config.templates_root,
        ),
        published_image_prefix=os.path.relpath(
            site_config.shared_images_output,
            output.parent,
        ),
        published_styles=published_styles,
    )

    title = str(metadata.get("seo_title", metadata.get("title", site_config.organization)))
    description = str(metadata.get("description", metadata.get("abstract", "")))
    canonical = public_output_url(site_config, output)
    keywords = metadata.get("keywords", [])
    keywords_content = ", ".join(str(keyword) for keyword in keywords) if isinstance(keywords, list) else str(keywords or "")

    if soup.title is not None:
        suffix = "" if metadata.get("seo_title") else f" - {site_config.organization}"
        soup.title.string = f"{title}{suffix}"
    set_meta_content(soup, 'meta[name="description"]', description)
    set_meta_content(soup, 'meta[name="keywords"]', keywords_content)
    set_meta_content(soup, 'meta[name="author"]', metadata.get("author", site_config.organization))
    set_meta_content(soup, 'meta[name="robots"]', metadata.get("robots", "index, follow"))
    set_link_href(soup, 'link[rel="canonical"]', canonical)
    set_meta_content(
        soup,
        'meta[property="og:title"]',
        f"{title} - {site_config.organization}"
        if not str(title).endswith(site_config.organization)
        else title,
    )
    set_meta_content(soup, 'meta[property="og:description"]', metadata.get("abstract", description))
    set_meta_content(soup, 'meta[property="og:type"]', metadata.get("og_type", "article"))
    set_meta_content(soup, 'meta[property="og:url"]', canonical)
    set_meta_content(soup, 'meta[name="ai:page-type"]', metadata.get("ai_category", ""))
    set_meta_content(soup, 'meta[name="ai:difficulty"]', metadata.get("ai_difficulty", ""))
    set_meta_content(soup, 'meta[name="ai:target-roles"]', metadata.get("ai_target_roles", ""))
    set_meta_content(soup, 'meta[name="ai:product-type"]', metadata.get("ai_product_type", ""))
    set_meta_content(soup, 'meta[name="ai:license"]', metadata.get("ai_license", ""))
    set_meta_content(soup, 'meta[name="ai:status"]', metadata.get("ai_status", ""))

    render_template_schema(soup, metadata, site_config, canonical)
    configured_labels = site_config.language(language).get("labels", {})
    language_output_paths: dict[str, str] = {}
    page_id = str(canonical_metadata.get("id") or metadata.get("source_id") or metadata.get("id") or "")
    for configured_language in site_config.languages:
        resolved_language = resolve_page_by_id(site_root, page_id, configured_language)
        if resolved_language is None:
            continue
        _canonical_source, language_source, _canonical_metadata = resolved_language
        language_output = infer_content_output(site_root, language_source, canonical_metadata)
        if language_output is not None:
            language_output_paths[configured_language] = str(language_output)
    template_context: dict[str, object] = {
        "labels": configured_labels,
        "site": {
            "name": site_config.organization,
            "email": site_config.email,
            "base_url": site_config.base_url,
        },
        "page": metadata,
    }
    try:
        bind_declarative_fragment(
            soup,
            template_context,
            site_root=site_root,
            output=output,
            language_outputs=language_output_paths,
        )
    except DeclarativeBindingError as exc:
        print(f"Render blocked: declarative template binding failed: {exc}")
        print("No HTML or assets were written.")
        return 1

    if not uses_current_html:
        target_selector = site_config.template_content_target(template_name)
        content_target = soup.select_one("[data-websmith-body]")
        if content_target is None and target_selector:
            content_target = soup.select_one(target_selector)
        if content_target is None:
            print("Template missing declared body destination")
            return 2
        content_mode = str(content_target.attrs.pop("data-websmith-content-mode", "replace"))
        if content_mode not in {"replace", "append"}:
            print(f"Template has invalid data-websmith-content-mode: {content_mode}")
            return 2
        if content_mode == "replace":
            content_target.clear()
        try:
            rendered_body = render_markdown_with_components(body, site_root)
        except DeclarativeBindingError as exc:
            print(f"Render blocked: declarative component binding failed: {exc}")
            print("No HTML or assets were written.")
            return 1
        append_html_fragment(soup, content_target, rendered_body)
        rewrite_internal_markdown_links(soup, site_root, output)
        inject_toc(soup, body)
    output.parent.mkdir(parents=True, exist_ok=True)
    for style_source, style_output in style_publish_rules:
        style_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(style_source, style_output)
    copy_configured_assets(site_root)
    normalize_logo_paths(soup, site_root, output)
    copy_referenced_local_assets(site_root, output, soup)

    if not write_validated_soup(soup, site_root, output):
        return 1
    print(f"Rendered: {relative(output)}")
    for _style_source, style_output in style_publish_rules:
        print(f"Copied CSS: {relative(style_output)}")
    return 0


def command_render_page(args: argparse.Namespace) -> int:
    site_name = getattr(args, "site", None)
    site_config = load_site_config(site_name)
    site_root = site_config.root
    language = args.lang or site_config.canonical_language
    site_config.language(language)
    requested_languages = [language]

    if args.all_langs:
        canonical = resolve_page_by_id(site_root, args.page_id, site_config.canonical_language)
        if canonical is None:
            print(f"Page id not found: {args.page_id}")
            return 2
        requested_languages = [
            configured_language
            for configured_language in site_config.languages
            if resolve_page_by_id(site_root, args.page_id, configured_language) is not None
        ]

    resolved_pages: list[
        tuple[str, Path, dict[str, object], Path]
    ] = []
    for language in requested_languages:
        resolved = resolve_page_by_id(site_root, args.page_id, language)
        if resolved is None:
            print(f"Page id not found or not available for language: {args.page_id} ({language})")
            return 2
        _canonical_source, source, canonical_metadata = resolved
        output = infer_content_output(site_root, source, canonical_metadata)
        if output is None:
            print(f"Page output cannot be derived for language: {args.page_id} ({language})")
            return 2
        resolved_pages.append((language, source, canonical_metadata, output))

    preflight_errors: list[str] = []
    for _language, source, _canonical_metadata, _output in resolved_pages:
        _validated_output, errors = validate_page_source(site_root, source)
        preflight_errors.extend(errors)
    if preflight_errors:
        print(f"Render blocked: preflight validation failed for page id '{args.page_id}'")
        print(f"Errors: {len(preflight_errors)}")
        for error in preflight_errors:
            print(f"  - {error}")
        print("No HTML or assets were written.")
        return 1

    exit_code = 0
    rendered_languages: list[str] = []
    for language, source, canonical_metadata, output in resolved_pages:
        result = render_family_page(site_root, args.page_id, source, canonical_metadata, output, language)
        if result != 0:
            exit_code = result
            break
        rendered_languages.append(language)

    if args.all_langs and rendered_languages:
        print(f"Rendered languages: {', '.join(rendered_languages)}")
    return exit_code


def command_resolve_page(args: argparse.Namespace) -> int:
    site_root = resolve_site_root(args.site)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    resolved = resolve_page_by_output(site_root, output_path)
    if resolved is None:
        print(f"Generated page output does not resolve to a canonical source: {relative(output_path)}")
        return 2

    page_id, language, canonical_source, normalized_output = resolved
    print(f"id: {page_id}")
    print(f"language: {language}")
    print(f"canonical_source: {relative(canonical_source)}")
    print(f"output: {relative(normalized_output)}")
    print(
        "render_command: PYTHONPYCACHEPREFIX=/tmp python3 scripts/websmith.py "
        f"render-page {page_id} --site {args.site} --all-langs"
    )
    return 0


def command_sync_translations(args: argparse.Namespace) -> int:
    site_root = resolve_site_root(args.site)
    site_config = load_site_config(args.site)
    canonical_language = site_config.canonical_language
    resolved = resolve_page_by_id(site_root, args.page_id, canonical_language)
    if resolved is None:
        print(f"Page id not found: {args.page_id}")
        return 2

    canonical_source, _source, canonical_metadata = resolved
    _metadata, canonical_body = strip_frontmatter(read_text(canonical_source))
    source_contract = markdown_translation_contract(canonical_body)
    issues: list[str] = []
    print(f"Translation sync check: {args.page_id}")
    print(f"Canonical source: {relative(canonical_source)}")

    found_translation = False
    for language in site_config.languages:
        if language == canonical_language:
            continue
        resolved_translation = resolve_page_by_id(site_root, args.page_id, language)
        if resolved_translation is None:
            continue
        found_translation = True
        _canonical, translation_source, _canonical_metadata = resolved_translation

        target_metadata, target_body = strip_frontmatter(read_text(translation_source))
        if str(target_metadata.get("source_id", "")).strip() != args.page_id:
            issues.append(f"{language}: source_id is not '{args.page_id}'")
        if "lang" not in target_metadata:
            issues.append(f"{language}: missing lang frontmatter")

        target_contract = markdown_translation_contract(target_body)
        contract_issues = compare_translation_contracts(source_contract, target_contract)
        if contract_issues:
            for issue in contract_issues:
                issues.append(f"{language}: {issue}")
        else:
            print(f"{language}: structure aligned ({relative(translation_source)})")

    if not found_translation:
        print("No translation files found at the corresponding language paths.")
        return 0

    if issues:
        print(f"Issues: {len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("Issues: 0")
    return 0


def family_page_ids(site_root: Path, family_id: str) -> list[str]:
    normalized_family = family_id.strip()
    canonical_language = config_for_root(site_root).canonical_language
    page_ids: list[str] = []
    for source in collect_files(source_root(site_root, canonical_language), "*.md"):
        metadata, _body = strip_frontmatter(read_text(source))
        page_id = str(metadata.get("id", "")).strip()
        if not page_id:
            continue
        if page_id == normalized_family or page_id.startswith(f"{normalized_family}-"):
            page_ids.append(page_id)
            continue
        try:
            relative_source = source.relative_to(source_root(site_root, canonical_language))
        except ValueError:
            continue
        if relative_source.parts[:1] == (normalized_family,):
            page_ids.append(page_id)
    return sorted(page_ids, key=lambda value: (value != normalized_family, value))


def translation_sync_issues(site_root: Path, page_id: str) -> list[str]:
    site_config = config_for_root(site_root)
    canonical_language = site_config.canonical_language
    resolved = resolve_page_by_id(site_root, page_id, canonical_language)
    if resolved is None:
        return [f"{page_id}: page id not found"]

    canonical_source, _source, canonical_metadata = resolved
    _metadata, canonical_body = strip_frontmatter(read_text(canonical_source))
    source_contract = markdown_translation_contract(canonical_body)
    issues: list[str] = []
    for language in site_config.languages:
        if language == canonical_language:
            continue
        resolved_translation = resolve_page_by_id(site_root, page_id, language)
        if resolved_translation is None:
            continue
        _canonical, translation_source, _canonical_metadata = resolved_translation

        target_metadata, target_body = strip_frontmatter(read_text(translation_source))
        if str(target_metadata.get("source_id", "")).strip() != page_id:
            issues.append(f"{page_id}: {language}: source_id is not '{page_id}'")
        if "lang" not in target_metadata:
            issues.append(f"{page_id}: {language}: missing lang frontmatter")

        target_contract = markdown_translation_contract(target_body)
        for issue in compare_translation_contracts(source_contract, target_contract):
            issues.append(f"{page_id}: {language}: {issue}")

    return issues


def html_link_issues(site_root: Path, output: Path) -> list[str]:
    issues: list[str] = []
    if not output.exists():
        return [f"{relative(output)}: generated output missing"]
    if BeautifulSoup is None:
        return issues

    soup = BeautifulSoup(read_text(output), "html.parser")
    language = output_language(site_root, output)

    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        if "[" in href or "]" in href:
            issues.append(f"{relative(output)}: unresolved href '{href}'")

        if language in {"eng", "ai"}:
            href_path = urlparse(href).path.replace("\\", "/")
            points_to_italian = href_path.startswith("/ita/") or href_path.startswith("../ita/") or "/ita/" in href_path
            if points_to_italian and link.find_parent(class_="language-switcher") is None and link.find_parent(class_="nav") is None:
                issues.append(f"{relative(output)}: non-language link points to Italian output '{href}'")

    ids = {str(tag.get("id")) for tag in soup.find_all(id=True)}
    for toc_link in soup.select(".doc-toc-list a[href^='#']"):
        anchor = str(toc_link.get("href") or "")[1:]
        if anchor and anchor not in ids:
            issues.append(f"{relative(output)}: TOC link points to missing heading '#{anchor}'")

    return issues


def render_family_page(
    site_root: Path,
    page_id: str,
    source: Path,
    canonical_metadata: dict[str, object],
    output: Path,
    language: str,
) -> int:
    return render_generic_markdown_page(
        site_root=site_root,
        source=source,
        canonical_metadata=canonical_metadata,
        output=output,
        language=language,
    )


def command_validate_family(args: argparse.Namespace) -> int:
    site_config = load_site_config(args.site)
    site_root = site_config.root
    canonical_language = site_config.canonical_language
    page_ids = family_page_ids(site_root, args.family_id)
    all_errors: list[str] = []
    checked_outputs: list[Path] = []

    print(f"Family validation: {args.site} {args.family_id}")
    if not page_ids:
        print(f"No canonical page ids found for family: {args.family_id}")
        return 2

    print(f"Pages: {', '.join(page_ids)}")

    for page_id in page_ids:
        resolved = resolve_page_by_id(site_root, page_id, canonical_language)
        if resolved is None:
            all_errors.append(f"{page_id}: canonical source not found ({canonical_language})")
            continue

        canonical_source, _source, canonical_metadata = resolved
        if "id" not in canonical_metadata:
            all_errors.append(f"{relative(canonical_source)}: missing id frontmatter")
        if "template" not in canonical_metadata:
            all_errors.append(f"{relative(canonical_source)}: missing template frontmatter")

        all_errors.extend(translation_sync_issues(site_root, page_id))

        for language in site_config.languages:
            resolved_language = resolve_page_by_id(site_root, page_id, language)
            if resolved_language is None:
                continue

            _canonical_source, source, _canonical_metadata = resolved_language
            output = infer_content_output(site_root, source, canonical_metadata)
            if output is None:
                all_errors.append(f"{page_id}: {language}: output cannot be derived")
                continue

            _inferred_output, page_errors = validate_page_source(site_root, source)
            all_errors.extend(page_errors)

            if not args.no_render:
                result = render_family_page(site_root, page_id, source, canonical_metadata, output, language)
                if result != 0:
                    all_errors.append(f"{page_id}: {language}: render failed with exit code {result}")
                    continue

            checked_outputs.append(output)
            all_errors.extend(html_link_issues(site_root, output))

    print(f"Languages checked: {', '.join(site_config.languages)}")
    print(f"HTML outputs checked: {len(checked_outputs)}")

    if all_errors:
        print(f"Errors: {len(all_errors)}")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("Errors: 0")
    return 0


def command_render_archetipo(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the Markdown/front-matter page renderer."""
    return command_render_page(argparse.Namespace(site="techreloaded", page_id="archetipo", lang=args.lang, all_langs=False))


def command_render_archetipo_beta(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the Markdown/front-matter page renderer."""
    return command_render_page(argparse.Namespace(site="techreloaded", page_id="archetipo-beta", lang=args.lang, all_langs=False))


def command_render_documentazione(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the Markdown/front-matter page renderer."""
    return command_render_page(argparse.Namespace(site="techreloaded", page_id="archetipo-documentazione", lang=args.lang, all_langs=False))


def command_render_team(args: argparse.Namespace) -> int:
    """Compatibility wrapper for the Markdown/front-matter page renderer."""
    return command_render_page(argparse.Namespace(site="techreloaded", page_id="team-index", lang=args.lang, all_langs=False))


def command_render_team_pages(args: argparse.Namespace) -> int:
    """Compatibility wrapper for team profile pages rendered by page id."""
    site_root = resolve_site_root("techreloaded")
    source_root_path = source_root(site_root, args.lang) / "team"
    if not source_root_path.exists():
        print(f"Source directory not found: {relative(source_root_path)}")
        return 2

    sources = sorted(path for path in source_root_path.glob("*.md") if path.name != "index.md")
    if getattr(args, "slug", None):
        sources = [path for path in sources if path.stem == args.slug]
        if not sources:
            print(f"Team person source not found: {args.slug}")
            return 2

    rendered_count = 0
    for source in sources:
        metadata, body = strip_frontmatter(read_text(source))
        page_id = str(metadata.get("source_id") or metadata.get("id") or source.stem)
        result = command_render_page(argparse.Namespace(site="techreloaded", page_id=page_id, lang=args.lang, all_langs=False))
        if result != 0:
            return result
        rendered_count += 1

    print(f"Rendered team person pages: {rendered_count}")
    return 0


def command_parse_component(args: argparse.Namespace) -> int:
    site_root = resolve_site_root(args.site)
    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = REPO_ROOT / file_path

    try:
        file_path.relative_to(site_root)
    except ValueError:
        print(f"File must be inside site root: {relative(site_root)}")
        return 2

    if not file_path.exists():
        print(f"File not found: {relative(file_path)}")
        return 2

    blocks = parse_component_blocks(read_text(file_path), args.component)

    print(f"Component parse: {args.component}")
    print(f"File: {relative(file_path)}")
    print(f"Blocks found: {len(blocks)}")

    for block_index, block in enumerate(blocks, start=1):
        metadata = block["metadata"]
        params = block["params"]
        items = block["items"]
        print()
        print(f"Block {block_index}")
        print(f"  params: {', '.join(f'{key}={value}' for key, value in params.items()) if params else '(none)'}")
        print(f"  title: {metadata.get('title', '')}")
        print(f"  metadata keys: {', '.join(metadata.keys()) if metadata else '(none)'}")
        print(f"  body chars: {len(block['body'])}")
        print(f"  items: {len(items)}")
        for item_index, item in enumerate(items, start=1):
            item_component = item["component"]
            item_metadata = item["metadata"]
            item_body = item["body"]
            preview = " ".join(item_body.split())[:90]
            label = item_metadata.get("title") or item_metadata.get("name") or ""
            print(f"    {item_index}. {label}")
            if item_component:
                print(
                    "       component: "
                    f"{item_component['name']}"
                    f" ({', '.join(f'{key}={value}' for key, value in item_component['params'].items()) if item_component['params'] else 'no params'})"
                )
            print(f"       metadata keys: {', '.join(item_metadata.keys()) if item_metadata else '(none)'}")
            print(f"       body chars: {len(item_body)}")
            if preview:
                print(f"       body preview: {preview}")

    return 0 if blocks else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Websmith deterministic site tooling")
    parser.add_argument("--site-root", type=Path, help="Independent site directory (before command)")
    parser.add_argument("--version", action="version", version="websmith 0.1.0a3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    from .import_web import command_import
    import_parser = subparsers.add_parser("import", help="Acquisisce un sito pubblico senza modificare i sorgenti Websmith")
    import_parser.add_argument("url", help="URL http/https iniziale")
    import_parser.add_argument("--output", help="Destinazione relativa nuova; predefinita imports/NOME-DOMINIO")
    import_parser.add_argument("--max-pages", type=int, default=30)
    import_parser.add_argument("--max-depth", type=int, default=3)
    import_parser.add_argument("--max-assets", type=int, default=200)
    import_parser.add_argument("--max-file-bytes", type=int, default=10_000_000)
    import_parser.add_argument("--max-total-bytes", type=int, default=100_000_000)
    import_parser.add_argument("--timeout", type=float, default=15)
    import_parser.add_argument("--delay", type=float, default=0.25, help="Intervallo minimo fra richieste in secondi")
    import_parser.set_defaults(func=command_import)

    from .initialize import command_init
    init_parser = subparsers.add_parser("init", help="Inizializza Websmith nella cartella corrente senza sovrascrivere file")
    init_parser.add_argument("--yes", action="store_true", help="Usa i valori predefiniti senza domande")
    init_parser.add_argument("--name", help="Nome del sito")
    init_parser.add_argument("--id", help="Identificativo del sito")
    init_parser.add_argument("--url", help="URL del sito; predefinito https://example.test")
    init_parser.add_argument("--language", choices=["it", "en"], help="Lingua iniziale")
    init_parser.add_argument("--agent", choices=["codex", "claude", "none"], help="Agente da configurare")
    init_parser.set_defaults(func=command_init)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect site structure without writing files")
    inspect_parser.add_argument("site", nargs="?", help="Website name under websites/")
    inspect_parser.set_defaults(func=command_inspect)

    validate_site_parser = subparsers.add_parser(
        "validate-site",
        help="Validate a site's websmith.yaml manifest and referenced local resources",
    )
    validate_site_parser.add_argument("site", nargs="?", help="Website name under websites/")
    validate_site_parser.set_defaults(func=command_validate_site)

    validate_parser = subparsers.add_parser(
        "validate-frontmatter",
        help="Validate Markdown YAML frontmatter for a website",
    )
    validate_parser.add_argument("site", nargs="?", help="Website name under websites/")
    validate_parser.set_defaults(func=command_validate_frontmatter)

    validate_page_parser = subparsers.add_parser(
        "validate-page",
        help="Validate one Markdown page contract before rendering",
    )
    validate_page_parser.add_argument("site", help="Website name under websites/")
    validate_page_parser.add_argument("lang", help="Language declared by the site's websmith.yaml")
    validate_page_parser.add_argument(
        "page",
        help="Page path, source stem, slug, or output path, for example prodotti/archetipo or archetipo-beta",
    )
    validate_page_parser.set_defaults(func=command_validate_page)

    validate_pages_parser = subparsers.add_parser(
        "validate-pages",
        help="Validate all Markdown page contracts before rendering",
    )
    validate_pages_parser.add_argument("site", nargs="?", help="Website name under websites/")
    validate_pages_parser.add_argument(
        "--lang",
        default="all",
        help="Language declared by the site's websmith.yaml, or all",
    )
    validate_pages_parser.set_defaults(func=command_validate_pages)

    validate_family_parser = subparsers.add_parser(
        "validate-family",
        help="Validate and render a multilingual page family by canonical id prefix",
    )
    validate_family_parser.add_argument("family_id", help="Canonical family id, for example archetipo")
    validate_family_parser.add_argument("--site", default=None)
    validate_family_parser.add_argument(
        "--no-render",
        action="store_true",
        help="Validate sources and inspect existing HTML without regenerating outputs",
    )
    validate_family_parser.set_defaults(func=command_validate_family)

    resolve_page_parser = subparsers.add_parser(
        "resolve-page",
        help="Resolve generated HTML back to the site's canonical Markdown source",
    )
    resolve_page_parser.add_argument("site", help="Website name under websites/")
    resolve_page_parser.add_argument("output", help="Generated HTML output path under websites/<site>/web")
    resolve_page_parser.set_defaults(func=command_resolve_page)

    sync_translations_parser = subparsers.add_parser(
        "sync-translations",
        help="Check configured translations for a canonical page id",
    )
    sync_translations_parser.add_argument("page_id", help="Canonical page id from Markdown frontmatter")
    sync_translations_parser.add_argument("--site", default=None)
    sync_translations_parser.set_defaults(func=command_sync_translations)

    parse_component_parser = subparsers.add_parser(
        "parse-component",
        help="Parse one Markdown component block without generating HTML",
    )
    parse_component_parser.add_argument("site", help="Website name under websites/")
    parse_component_parser.add_argument("file", help="Markdown file to inspect")
    parse_component_parser.add_argument("component", help="Canonical component name, for example highlights-box-sx")
    parse_component_parser.set_defaults(func=command_parse_component)

    render_root_index_parser = subparsers.add_parser(
        "render-root-index",
        help="Render a site's configured root language redirect",
    )
    render_root_index_parser.add_argument(
        "--site",
        
        default=None,
        help="Website name under websites/ (default: techreloaded for compatibility)",
    )
    render_root_index_parser.set_defaults(func=command_render_root_index)

    render_index_parser = subparsers.add_parser(
        "render-index",
        help="Render TechReloaded index.md to web/ita/index.html",
    )
    render_index_parser.add_argument("--lang", default="ita")
    render_index_parser.set_defaults(func=command_render_index)

    render_page_parser = subparsers.add_parser(
        "render-page",
        help="Render a page by canonical frontmatter id using its configured output",
    )
    render_page_parser.add_argument("page_id", help="Canonical page id from Markdown frontmatter")
    render_page_parser.add_argument(
        "--site",
        
        default=None,
        help="Website name under websites/ (default: techreloaded for compatibility)",
    )
    render_page_parser.add_argument(
        "--lang",
        default=None,
        help="Language declared by the site's manifest (default: canonical language)",
    )
    render_page_parser.add_argument(
        "--all-langs",
        action="store_true",
        help="Render every configured language that has a corresponding Markdown source",
    )
    render_page_parser.set_defaults(func=command_render_page)

    render_archetipo_parser = subparsers.add_parser(
        "render-archetipo",
        help="Render TechReloaded archetipo.md to web/ita/prodotti/archetipo/index.html",
    )
    render_archetipo_parser.add_argument("--lang", default="ita")
    render_archetipo_parser.set_defaults(func=command_render_archetipo)

    render_archetipo_beta_parser = subparsers.add_parser(
        "render-archetipo-beta",
        help="Render TechReloaded archetipo-beta.md to web/ita/prodotti/archetipo/beta.html",
    )
    render_archetipo_beta_parser.add_argument("--lang", default="ita")
    render_archetipo_beta_parser.set_defaults(func=command_render_archetipo_beta)

    render_documentazione_parser = subparsers.add_parser(
        "render-documentazione",
        help="Render archetipo-documentazione.md to web/ita/prodotti/archetipo/documentazione.html",
    )
    render_documentazione_parser.add_argument("--lang", default="ita")
    render_documentazione_parser.set_defaults(func=command_render_documentazione)

    render_team_parser = subparsers.add_parser(
        "render-team",
        help="Render team/index.md to web/ita/team/index.html",
    )
    render_team_parser.add_argument("--lang", default="ita")
    render_team_parser.set_defaults(func=command_render_team)

    render_team_pages_parser = subparsers.add_parser(
        "render-team-pages",
        help="Render team person Markdown files to web/ita/team/*.html",
    )
    render_team_pages_parser.add_argument("--lang", default="ita")
    render_team_pages_parser.add_argument("--slug", help="Render only one team person slug", default=None)
    render_team_pages_parser.set_defaults(func=command_render_team_pages)

    help_parser = subparsers.add_parser(
        "HELP", aliases=["help"], help="Elenca i comandi con scopo, sintassi ed esempi in italiano",
    )
    help_parser.add_argument(
        "topic", nargs="?", choices=sorted(subparsers.choices),
        help="Comando di cui mostrare tutte le opzioni",
    )

    def show_help(args: argparse.Namespace) -> int:
        if args.topic:
            subparsers.choices[args.topic].print_help()
        else:
            print(read_text(RESOURCE_ROOT / "docs" / "HELP.md"))
        return 0

    help_parser.set_defaults(func=show_help)

    return parser


def available_sites() -> list[str]:
    if not WEBSITES_ROOT.exists():
        return []
    return sorted(path.name for path in WEBSITES_ROOT.iterdir() if path.is_dir())


def available_manifest_sites() -> list[str]:
    return [
        site_name
        for site_name in available_sites()
        if (resolve_site_root(site_name) / SITE_MANIFEST_NAME).is_file()
    ]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    global EXPLICIT_SITE_ROOT
    EXPLICIT_SITE_ROOT = args.site_root.resolve() if args.site_root else None
    load_site_config.cache_clear()
    load_component_catalog.cache_clear()
    if args.command not in {"HELP", "help"} and hasattr(args, "site"):
        args.site = str(resolve_site_root(args.site))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
