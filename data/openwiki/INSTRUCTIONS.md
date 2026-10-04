# OpenWiki brief: FastAPI user documentation wiki

## Purpose

This repository is a snapshot of the FastAPI **user documentation** (see SOURCE.md).
The wiki you write will be the knowledge base for a question-answering experiment:
an LLM reads the wiki index, opens the pages it needs, and answers questions from
FastAPI users ranging from beginners to professionals. Write for that reader.

## Scope

- Document the content of `docs/en/docs/**/*.md` and the example code they include
  from `docs_src/` (and `fastapi/openapi/docs.py`, which one page includes).
- `{* path/to/file.py ln[a:b] hl[...] *}` in a page means the example code at that path
  is shown inline (only lines a..b when `ln[...]` is given). Read the referenced file
  when the example matters.
- `SOURCE.md` and `corpus.json` are metadata about the snapshot. Do not document them.
- There is no application to document here: do not write architecture, build,
  deployment-of-this-repo, or contributor pages about this repository itself.

## Organization

- Organize pages by user-facing topic, following the documentation's own structure
  (tutorial, advanced user guide, how-to recipes, deployment, etc.), not by file.
- Every documentation page under `docs/en/docs` should be covered by at least one wiki page.

## Content rules

- Preserve concrete, answerable facts: parameter and argument names, default values,
  types, status codes, import paths, class and function names, CLI commands, version
  requirements, and the order of steps in procedures.
- Keep short code examples when they show how to use an API; do not paraphrase code
  into prose when the code itself is the answer.
- Do not generalize away specifics, and do not add behavior that the documentation
  does not state.
- Write in English, matching the source documentation.

## Sources section (required)

End every page with a `## Sources` section listing each documentation page the wiki
page is based on, as repository-root paths, one per line, for example:

```
## Sources
- docs/en/docs/tutorial/body.md
- docs/en/docs/tutorial/body-fields.md
```

Use exactly these paths (no URLs, no anchors). They are used to map wiki pages back
to the original documents.
