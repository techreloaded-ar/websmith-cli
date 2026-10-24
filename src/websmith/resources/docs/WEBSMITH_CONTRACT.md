# Websmith Shared Contract

This document defines the technical boundary between the Websmith engine and each website built with it. `AGENTS.md` remains the binding operating contract for agents; this document explains the architecture that implements those rules.

## Design Goal

Websmith must support independent websites through one deterministic pipeline.

The engine owns repeatable transformations and validation. A site owns its content model choices, composition vocabulary, page structures, visual system, brand, languages, routes, and assets.

Adding a conforming site must not require embedding that site's name, text, selectors, components, or routes in the shared renderer.

## Two Rule Levels

### Shared Websmith rules

Shared rules apply to every migrated site:

- authoritative source layers are explicit;
- rendering is deterministic;
- generated HTML is not the durable edit target;
- editorial translation is performed by an agent, not invented by the renderer;
- component directives use canonical syntax and are validated against the target site's catalog;
- content, template structure, reusable components, CSS, configuration, renderer code, and generated output have distinct responsibilities;
- ambiguous input fails visibly rather than being guessed;
- validation precedes rendering;
- rendered links and local assets are verified.

These rules belong in `AGENTS.md`, shared documentation, and shared renderer tests.

### Site-specific rules

Site-specific rules apply only inside one `websites/<site>/` tree:

- canonical and supported languages;
- content group names and routes;
- front matter fields beyond the common minimum;
- page families and composition patterns;
- template names and DOM targets;
- component names, fields, ownership, and allowed nesting;
- navigation, footer, contact, schema, and brand behavior;
- asset locations and publication paths;
- CSS and responsive behavior;
- compatibility rules for that site's legacy sources.

These rules belong in the site's composition guide, component catalog, templates, CSS, content, and assets. Site-specific Python adapters are not part of the Websmith contract.

## Ownership Matrix

| Concern | Shared engine | Site package |
| --- | --- | --- |
| Front matter parsing | Owns parser and common errors | Declares site fields and values |
| Page identity and references | Owns resolution algorithm | Declares IDs, outputs, and routes |
| Translation checking | Compares structural contracts | Declares languages and canonical source |
| Component parsing | Owns directive grammar | Owns `catalog.yaml` vocabulary |
| Page rendering | Owns pipeline and safe DOM operations | Owns templates and selector contract |
| Visual appearance | Never invents visual rules | Owns CSS and component markup |
| Navigation and brand | Provides generic mechanisms | Owns labels, links, logo, and metadata |
| Assets | Validates and copies deterministically | Owns sources and path policy |
| Generated output | Writes and verifies | Declares output locations |
| Legacy compatibility | Provides explicit extension points | Documents and scopes compatibility |

## Expected Site Package

The target structure is:

```text
websites/<site>/
  websmith.yaml
  COMPOSITION_GUIDE.md
  EDITORIAL_GUIDE.md         (optional, site-owned editorial policy)
  contents/
    <language>/
      **/*.md
  templates/
    html/
      *.html
      components/
        catalog.yaml
        *.html
    CSS/
      *.css
  media/
  web/
```

Every migrated site has a `websites/<site>/websmith.yaml` manifest validated against `schemas/websmith-site.schema.json`. The manifest makes paths, languages, defaults, routes, brand metadata, and asset policies machine-readable. Run:

```bash
PYTHONPYCACHEPREFIX=/tmp python3 scripts/websmith.py validate-site <site>
```

The manifest declares operational data used by the renderer. It does not contain visual values, editorial copy, component definitions, secrets, or deployment credentials.

The shared page-resolution, validation, and publishing functions read canonical language, supported languages, source roots, output roots, page directories, required front matter fields, template and CSS paths, asset copy and resolution rules, logo, brand metadata, and root redirect settings from this manifest. Site-specific template bindings are declared in site-owned HTML with `data-websmith-*` attributes.

The root redirect is generated per site with:

```bash
PYTHONPYCACHEPREFIX=/tmp python3 scripts/websmith.py render-root-index --site <site>
```

Its destinations, alternates, labels, canonical URL, title, and description come from the selected manifest. Its visual structure remains site-owned in the root template declared by `root_redirect.template`.

Sites that do not yet match this structure are legacy or incomplete sites. Shared tools must report that state accurately; they must not describe a missing content tree as aligned or infer another site's conventions.

## Composition Guide Contract

Every migrated site must provide `websites/<site>/COMPOSITION_GUIDE.md`. It should document:

- canonical source language and translation workflow;
- actual source, template, CSS, asset, and output paths;
- supported page types and templates;
- stable DOM targets used during rendering;
- component-catalog location and site-specific composition guidance;
- site commands that work in the current implementation;
- legacy exceptions and migration status;
- output and asset verification particular to the site.

It should explain where and how to make a change. It must not duplicate exact visual values already owned by CSS.

## Optional Editorial Guide

A site may provide `websites/<site>/EDITORIAL_GUIDE.md` for its audience, voice, writing guidance, content formats, and editorial publication workflow. Agents consult it when writing or revising content. On request, an agent interviews the editor and produces or updates the guide from the answers, following `AGENTS.md`.

This is site-owned editorial knowledge, not renderer configuration or a requirement for site conformance. Technical composition remains in the composition guide and component catalog; remote deployment remains governed by the shared Git workflow.

## Component Catalog Contract

Every migrated site with component directives must provide its own catalog, normally at:

```text
websites/<site>/templates/html/components/catalog.yaml
```

The catalog is the site's semantic design-system vocabulary. At minimum, each component should declare:

- `name`;
- `owned_by`;
- `layout_role`;
- required and optional fields;
- required and optional item fields where relevant;
- purpose and usage guidance.

No component is implicitly global. Equal component names in two sites do not imply equal HTML, fields, layout, or behavior.

The renderer should ultimately load known components and field requirements from the selected site's catalog rather than maintain shared hardcoded lists.

## Renderer Boundary

The shared renderer may:

- load a selected site's declared configuration;
- parse Markdown and YAML front matter;
- validate component syntax against that site's catalog;
- resolve page IDs, translations, links, outputs, and assets;
- apply declared data to stable template DOM targets;
- copy declared static assets;
- generate and verify final HTML.

The shared renderer must not:

- hardcode a site name, company name, domain, email, logo, language set, or navigation label;
- assume Italian is canonical for every site;
- treat one site's content directories or routes as universal;
- keep a global component vocabulary shared accidentally by all sites;
- translate editorial copy;
- synthesize sections or component variants absent from sources and templates;
- silently repair ambiguous or invalid input.

Site-specific Python adapters are not loaded. Layout and component behavior must be expressed through site-owned templates, catalogs, CSS, content, and declarative `data-websmith-*` bindings.

### Declarative template bindings

Page and component templates may use the same site-agnostic binding vocabulary:

- `data-websmith-text="path"` replaces an element's text;
- `data-websmith-inline="path"` renders inline Markdown; the legacy `data-websmith-inline-optional` spelling follows the same missing-value removal rule and must not preserve preview copy in generated HTML;
- `data-websmith-markdown="path"` renders a Markdown value inside an element;
- `data-websmith-attribute="attribute:path"` assigns one or more attributes;
- `data-websmith-attribute-prefix-if-bare` and `data-websmith-attribute-template` perform generic, explicitly declared attribute composition;
- `data-websmith-repeat="path"` clones its `data-websmith-repeat-item` child for a list or comma-separated value;
- `data-websmith-if="path"` removes an optional element when its value is absent;
- `data-websmith-if-not="path"` removes an element when its value is present;
- `data-websmith-if-any="path;other.path"` removes an optional container when all declared values are absent;
- `data-websmith-class-if-contains="class:path:value"` conditionally adds a class;
- `data-websmith-class-if-present="class:path"` adds a validated class when the declared value exists;
- `data-websmith-class-from` and `data-websmith-classes-from` derive one or more validated CSS class names from data;
- `data-websmith-format="zero-pad:n"` applies an explicit scalar format;
- `data-websmith-choice="path|default"` selects exactly one template-owned `data-websmith-value` variant and rejects missing or ambiguous matches;
- `data-websmith-component="path"` renders a nested component through that component's own catalog contract;
- `data-websmith-content-href="id"` resolves a logical page id, with optional `data-websmith-fragment`;
- `data-websmith-language="language-id"` resolves the corresponding language output;
- `data-websmith-output-path="attribute:path"` emits a path relative to the generated page.
- `data-websmith-content-mode="append"` preserves template-owned introductory nodes before appending the rendered Markdown body; the default mode is `replace`;
- `data-websmith-toc` marks the template-owned list that receives links derived deterministically from level-two Markdown headings.

A component catalog may declare `render.resolve_content.items` to hydrate repeated
items from canonical Markdown references before applying bindings. The declaration
specifies the item-relative `reference` path, the target context key through `as`,
and whether the reference is `required`. References use the canonical `[content-id]`
syntax and expose the resolved `id`, `anchor`, `page` front matter, and Markdown
`body`; unresolved required references block rendering.

The engine interprets these operations without knowing the semantic role of the element or the name of the component. Missing templates, invalid selectors, unresolved content ids, unknown languages, and ambiguous or missing assets are contract errors and block output.

Page front matter is exposed unchanged under `page`. A template therefore binds
directly to source paths such as `page.profile.name` or `page.hero.title`. The
shared renderer must not create semantic intermediate contexts, aliases, fallback
field names, or content-specific selector logic.

Templates remain WYSIWYG: every bound element contains realistic preview content
and every bound attribute has a usable preview value. During rendering a present
source value replaces that preview value completely. When the referenced source
value is absent, the renderer removes the bound node or omits that bound content;
the preview value never survives in generated HTML. `data-websmith-if` remains
useful for removing a larger template-owned container based on one source path.

### Bidirectional placement validation

The selected template is the placement contract for the Markdown source.
Validation happens in both directions before any output write:

1. every template binding is matched against the source; an absent value skips
   that bound node and is not by itself an error;
2. every populated, non-technical front matter leaf must be consumed by at least
   one template binding or another declared renderer destination;
3. every populated repeated-item leaf must be consumed inside its repeat template;
4. a non-empty Markdown body requires a template-owned body destination;
5. unmatched source values or an unplaced body block rendering and are reported
   with their complete source paths.

For example, if `page.telefono` exists in Markdown but the selected template has
no destination for it, rendering stops. If the template contains a WYSIWYG node
bound to `page.qualifica` and the Markdown omits `qualifica`, that node is removed.

Technical fields consumed by routing, translation, publication, validation, or
page lifecycle do not need visible placeholders. This set must remain explicit,
minimal, and shared. Declaring editorial fields technical merely to bypass unused
content validation is forbidden.

A component catalog entry can make its preview file the rendering source:

```yaml
render:
  template: component-name.html
  selector: .component-preview > .component-root
  defaults:
    optional_field: site-owned-default
```

Changing the selected HTML fragment or its bindings changes subsequent output without changing Python code. A component without a complete catalog rendering contract is rejected; the renderer does not create fallback HTML.

## Migration Rule

Multi-site support must be introduced without changing existing published output unintentionally.

For each site migration:

1. capture representative output and validation behavior;
2. introduce configuration and site-owned rules;
3. route the existing site through the shared pipeline;
4. compare HTML semantics, metadata, links, components, and assets;
5. document intentional differences;
6. only then remove superseded site hardcoding.

TechReloaded is the current reference implementation. It is evidence for the shared contract, not the definition of all future sites.

## Definition Of A Conforming Site

A site conforms to the Websmith shared contract when:

- its `websmith.yaml` passes shared schema and resource validation;
- its authoritative sources and generated outputs are identifiable;
- its composition guide exists and is site-specific;
- its component directives validate against its own catalog;
- all declared pages and translations resolve deterministically;
- all local rendered assets exist;
- rendering it does not require changing shared code for site-specific names, paths, selectors, or copy;
- rebuilding produces stable output from the same inputs.
