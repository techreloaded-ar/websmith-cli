# AGENTS.md

This file is the shared operating contract for all agents working in this repository, including Codex and Claude.

Do not duplicate or override these rules in tool-specific files. If a tool requires its own instruction file, that file must point back here.

## Scope And Rule Precedence

Websmith is a deterministic, Markdown-first static website workflow intended to support multiple independent sites.

Rules have two levels:

1. this file defines behavior shared by every Websmith site;
2. `websites/<site>/COMPOSITION_GUIDE.md` defines that site's composition, templates, selectors, components, assets, languages, and current commands; an optional `websites/<site>/EDITORIAL_GUIDE.md` defines its editorial policy.

The shared technical contract and the boundary between common and site-owned concerns are documented in `docs/WEBSMITH_CONTRACT.md`.

Before changing a site:

1. identify the target directory under `websites/`;
2. read this file;
3. read that site's `COMPOSITION_GUIDE.md` before changing page structure, templates, components, CSS, assets, or renderer behavior;
4. consult that site's component catalog before adding or modifying component directives.

If a site has no composition guide or component catalog, do not borrow rules or components from another site. Report the missing site contract and limit work to operations whose source and behavior are already unambiguous.

## Current Architecture

The target source model for a Websmith site is:

```text
websites/<site>/websmith.yaml                      site manifest
websites/<site>/contents/**/*.md                   primary content source
websites/<site>/templates/html/*.html              WYSIWYG page templates
websites/<site>/templates/html/components/*.html   visual components
websites/<site>/templates/html/components/catalog.yaml
                                                   component contract
websites/<site>/templates/CSS/                     site visual rules
websites/<site>/web/**/*.html                      generated output
scripts/websmith.py                                renderer and validation CLI
```

Not every site has completed this migration. Inspect the target site and its guide rather than assuming that TechReloaded's directory names, languages, templates, or components apply globally.

## Source Of Truth

For a migrated Websmith page, Markdown with YAML front matter is the primary source of knowledge. Generated HTML is an inspectable and publishable artifact, not the long-term source of truth.

Collaborators may edit generated HTML temporarily while iterating visually. When that happens, the agent must:

1. inspect the modified HTML;
2. identify content, order, structure, or style changes;
3. update the corresponding Markdown source, template, component, CSS, asset, or deterministic renderer rule;
4. regenerate the affected HTML;
5. verify that the generated output preserves the requested change.

Do not leave a durable fix only in generated HTML.

For a legacy site that has not adopted Markdown-first sources, follow its documented source model. Do not silently migrate or reinterpret legacy content as part of an unrelated change.

## Optional Editorial Guide

Every Websmith site may provide `websites/<site>/EDITORIAL_GUIDE.md` to define its audience, tone of voice, writing guidance, content formats, and editorial publication workflow, together with other site-specific editorial decisions.

Before writing or revising editorial content, read this guide when present and apply it within that site only. Its absence does not block ordinary content work and must not trigger an unsolicited interview. Do not borrow another site's editorial policy or treat existing copy as an explicitly agreed policy.

On user request, the agent conducts an interview with the site's editor to clarify editorial decisions, then creates or updates the site's `EDITORIAL_GUIDE.md` from the answers. Do not invent preferences or turn unanswered questions into agreed rules. The detailed interview method is to be defined with the user.

The editorial guide governs editorial decisions; the composition guide and component catalog govern technical composition. It does not authorize remote publication or change the Git deployment workflow. Creating the guide is an agentic task, not a renderer feature or an additional CLI command.

## Canonical Content Update Flow

The site's composition guide identifies its canonical language, configured translations, and exact commands.

When changing content:

1. edit the Markdown file in the site's canonical language first;
2. propagate the editorial change to every configured translation that exists;
3. preserve structural equivalence across translations;
4. validate every affected source;
5. render every affected language output;
6. inspect the generated HTML for requested text, links, components, metadata, and asset paths.

When the request names an HTML file or a visible page, resolve that output back to its canonical source first, then execute the same flow. The operator should not need to reason about the Markdown/HTML dualism.

## Agentic Translation Rules

Translation is an agentic editorial step, not a renderer feature.

The renderer must remain deterministic. It may validate and compare structure, resolve links, and generate HTML, but it must not invent or translate editorial content.

When propagating a canonical Markdown change to another language:

- preserve heading hierarchy, component directives, item boundaries, tables, code blocks, asset references, and logical content references;
- preserve technical front matter required for rendering and traceability;
- translate editorial text naturally, including metadata, hero copy, CTA labels, body copy, table text, and FAQ text;
- keep names, product identifiers, commands, file paths, code, component names, and logical references stable unless the source explicitly changes them;
- translate the target Markdown source, never the generated HTML;
- stop and report ambiguity instead of inventing product knowledge.

Use the site's documented translation-validation command before and after translation when one is available.

## Component Directives

Markdown component directives are binding layout instructions. Their vocabulary is local to a site.

Before adding or modifying a component, consult:

```text
websites/<site>/templates/html/components/catalog.yaml
```

The catalog defines the exact component name, `owned_by`, `layout_role`, required and optional fields, item fields, deprecation state, and usage guidance. Never assume that a component from one site exists or behaves the same way in another site.

Canonical syntax:

```md
<!-- component: component-name -->
field: value
body: Markdown text.
<!-- /component -->
```

For item-based components:

```md
<!-- component: container-name, columns: 4 -->

<!-- item -->
<!-- component: embedded-component -->
title: Example
body: Supporting text.

<!-- /component -->
```

Shared rules:

- always use `<!-- component: name -->`, including the colon;
- close container and standalone components with `<!-- /component -->`;
- start every repeated item with `<!-- item -->`;
- use the technical field names declared by the site's catalog;
- respect `owned_by` and `layout_role`;
- do not introduce legacy markers or legacy field names in migrated content;
- do not replace a declared component with generic markup or an invented variant;
- if a component or field is missing or ambiguous, stop and report it instead of inventing a substitute.

Legacy parsing may exist for migration only. Do not create new legacy syntax.

## Responsibility Boundaries

Markdown contains editorial content, metadata, component data, block ordering, and logical references.

Templates contain WYSIWYG page structure, fixed template-owned elements, and stable DOM targets used by the renderer.

Component files contain reusable HTML composition, supported parameters, and realistic preview examples.

CSS contains visual rules: typography, color, spacing, layout, responsive behavior, and interaction states. If a visual value is duplicated elsewhere, source CSS wins.

Site configuration and composition guides describe behavior and ownership. They must not duplicate pixel-level visual rules from CSS.

Renderer code performs deterministic transformations only. It must not invent content, guess an ambiguous structure, or embed one site's editorial or visual decisions in shared behavior.

Generated HTML contains no source-only decisions. Previous versions belong in Git history, not in version-suffixed files inside publishable output directories.

## Template Placement Contract

For a migrated page, the Markdown front matter names the WYSIWYG HTML template and the template declares where source values are placed through generic `data-websmith-*` bindings.

The renderer must enforce both directions of this contract before writing output:

- when a template binding has no corresponding Markdown value, remove the bound preview node or omit that bound content; preview content must never leak into generated HTML;
- when a non-technical Markdown value is not consumed by any template binding, component directive, body target, or deterministic shared operation, stop and report the unused source path;
- when the Markdown body is non-empty, the template must declare its body destination; otherwise stop and report the unplaced body;
- technical routing and lifecycle fields consumed by Websmith do not require visible HTML placeholders;
- any placement-contract error must occur before HTML, CSS, or assets are written.

Nested mappings are organizational containers: their populated leaf values are what must be consumed. Repeated records must be checked item by item. A site may not silence unused editorial data by classifying it as technical.

## Assets

Local assets referenced by a page must exist in the generated site at the path emitted in HTML.

When adding or changing an asset reference:

1. identify the site-owned source asset;
2. follow that site's documented copy or resolution rules;
3. render the page;
4. verify the final path relative to the generated HTML file.

Do not rely on an asset from another site's source or output tree.

## Standard Workflow

### HELP command

When the user writes `HELP` (or `help`), explain the available Websmith commands
in Italian using `docs/HELP.md`: purpose, syntax, and examples. For `HELP <command>`,
focus on that command and verify its current options with
`python3 scripts/websmith.py HELP <command>`. HELP is informational: do not run
the listed operations. If a site is specified, consult its composition guide
and distinguish supported site commands from TechReloaded compatibility commands.

For page, content, component, or layout work:

1. inspect the target site's source and current output;
2. validate its `websmith.yaml` manifest when present;
3. read the site composition guide and, for component work, its catalog;
4. make the change in the authoritative source layer;
5. run the validation commands supported by that site;
6. render every affected page and language;
7. inspect generated HTML and local assets;
8. keep unrelated or legacy migration work out of the change.

Command syntax is currently not uniform across all sites. Use the commands documented by the target site's composition guide and verify `python3 scripts/websmith.py --help` rather than extrapolating from another site.

## Quality Rules

Before finishing work:

- validate front matter after Markdown changes when the command is supported;
- validate pages before rendering when changing Markdown, components, links, or assets;
- render every changed page and configured language;
- treat render failures as source-contract violations;
- never bypass validation or patch generated HTML to hide a source problem;
- inspect generated output for requested content, links, components, metadata, and asset paths;
- do not revert unrelated collaborator changes;
- do not delete legacy files or assets unless cleanup was explicitly requested and their non-use was verified.

## Git And Collaboration

Team coordination happens through GitHub.

Remote deployment runs from Git pushes and updates hosting outside this workflow. Do not perform direct hosting or FTP actions unless explicitly requested.

Keep commits focused by responsibility: instructions, renderer/tooling, content, components/CSS, or cleanup. Do not mix broad cleanup, site migration, and editorial work unless the user explicitly requests a combined change.
