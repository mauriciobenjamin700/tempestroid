"""MkDocs hook that emits ``llms.txt`` + ``llms-full.txt`` at the site root.

This implements the `llmstxt.org <https://llmstxt.org/>`_ convention so any AI
assistant can read the whole tempestroid project from two stable URLs:

* ``/llms.txt`` — a curated, link-only index (title, summary, sectioned links
  with notes), pointing at the published documentation pages.
* ``/llms-full.txt`` — the full documentation inlined as one Markdown stream
  (README + every canonical page), so a model can ingest the project in a
  single fetch with no crawling.

Both files are written into ``config.site_dir`` during ``on_post_build`` so they
land at the GitHub Pages root next to ``index.html``. Nothing is committed to the
repo — the files are generated on every ``mkdocs build`` (locally and in the
Pages CI). The hook is dependency-free and is registered via the ``hooks:`` key
in ``mkdocs.yml``.

The index mirrors the PT-BR (default) navigation; an English mirror lives under
``/en/`` and is linked from the header so EN-speaking models can switch.
"""

from __future__ import annotations

import pathlib
from typing import Any

# Curated section order for ``llms.txt``, mirroring the MkDocs ``nav``. Each
# entry maps a human section title to the doc source paths (relative to
# ``docs_dir``) that belong to it. Any ``*.md`` file not listed here (and not an
# ``.en.md`` translation) is appended under an "Optional" section so newly added
# pages still surface without editing this hook.
SECTIONS: list[tuple[str, list[str]]] = [
    (
        "Start here",
        ["index.md", "instalacao.md", "inicio-rapido.md", "arquitetura.md"],
    ),
    (
        "User guide",
        [
            "guia/widgets.md",
            "guia/estilos.md",
            "guia/eventos.md",
            "guia/cli.md",
            "guia/exemplos.md",
            "guia/build.md",
            "guia/dispositivo-wsl.md",
        ],
    ),
    (
        "Reference",
        ["referencia/api.md", "referencia/dispositivo.md"],
    ),
    (
        "Project",
        [
            "roadmap.md",
            "plan.md",
            "plan-parity.md",
            "plan-stable.md",
            "research/android-runtime.md",
            "research/android-runbook.md",
        ],
    ),
]

# One-line project summary used as the ``llms.txt`` blockquote (EN, the lingua
# franca for AI tooling). Kept in sync with the README opening line.
SUMMARY: str = (
    "Framework for building native Android apps in typed Python: one declarative, "
    "fully typed Pydantic widget tree is diffed by a renderer-agnostic reconciler "
    "into patches, applied by two leaf renderers — Qt (desktop simulator) and "
    "Jetpack Compose (device)."
)


def _read(path: pathlib.Path) -> str:
    """Read a UTF-8 text file, returning an empty string if it is missing.

    Args:
        path: The file to read.

    Returns:
        The file content, or ``""`` when the file does not exist.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _title_and_note(markdown: str, fallback: str) -> tuple[str, str]:
    """Extract a page title (first H1) and a short note from Markdown.

    The note is the first blockquote line if present, otherwise the first
    non-empty, non-heading paragraph line — trimmed to a single sentence-ish
    snippet so the index stays scannable.

    Args:
        markdown: The raw Markdown content of the page.
        fallback: Title to use when no H1 is found (e.g. the file stem).

    Returns:
        A ``(title, note)`` tuple; ``note`` may be an empty string.
    """
    title: str = fallback
    note: str = ""
    blockquote: str = ""
    paragraph: str = ""
    seen_h1: bool = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if not seen_h1 and line.startswith("# "):
            title = line[2:].strip()
            seen_h1 = True
            continue
        if not blockquote and line.startswith("> "):
            blockquote = line[2:].strip()
        if (
            not paragraph
            and line
            and not line.startswith(("#", ">", "!!!", "```", "|", "-", "*"))
        ):
            paragraph = line
    note = blockquote or paragraph
    # Drop Markdown emphasis/link noise from the note and clamp its length.
    note = note.replace("**", "").replace("*", "").replace("`", "")
    if len(note) > 160:
        note = note[:157].rstrip() + "…"
    return title, note


def _doc_url(site_url: str, src: str) -> str:
    """Build the absolute published URL for a doc source path.

    Mirrors MkDocs' default directory-URL scheme (``foo.md`` → ``foo/``,
    ``index.md`` → the containing directory root).

    Args:
        site_url: The site root URL (with trailing slash).
        src: The doc source path relative to ``docs_dir`` (e.g. ``guia/cli.md``).

    Returns:
        The absolute URL of the rendered page.
    """
    base = site_url if site_url.endswith("/") else site_url + "/"
    if src == "index.md":
        return base
    rel = src[: -len(".md")] if src.endswith(".md") else src
    if rel.endswith("/index"):
        rel = rel[: -len("index")]
    else:
        rel = rel + "/"
    return base + rel


def _build_index(site_url: str, docs_dir: pathlib.Path) -> str:
    """Render the ``llms.txt`` index from the curated sections.

    Args:
        site_url: The published site root URL.
        docs_dir: The MkDocs ``docs/`` directory.

    Returns:
        The full ``llms.txt`` content.
    """
    base = site_url if site_url.endswith("/") else site_url + "/"
    lines: list[str] = [
        "# tempestroid",
        "",
        f"> {SUMMARY}",
        "",
        (
            "This file follows the llmstxt.org convention. For the full project "
            "inlined as one Markdown stream, fetch "
            f"[{base}llms-full.txt]({base}llms-full.txt). The documentation is "
            "bilingual — Portuguese (default) here and English under "
            f"[{base}en/]({base}en/)."
        ),
        "",
    ]

    curated: set[str] = {src for _, items in SECTIONS for src in items}
    for section, items in SECTIONS:
        rendered: list[str] = []
        for src in items:
            path = docs_dir / src
            if not path.exists():
                continue
            title, note = _title_and_note(_read(path), pathlib.Path(src).stem)
            url = _doc_url(base, src)
            rendered.append(f"- [{title}]({url})" + (f": {note}" if note else ""))
        if rendered:
            lines.append(f"## {section}")
            lines.append("")
            lines.extend(rendered)
            lines.append("")

    # Surface any uncurated, non-translation page so the index never silently
    # drops new docs (the "no silent caps" rule).
    extras: list[str] = []
    for path in sorted(docs_dir.rglob("*.md")):
        src = path.relative_to(docs_dir).as_posix()
        if src in curated or src.endswith(".en.md"):
            continue
        title, note = _title_and_note(_read(path), path.stem)
        url = _doc_url(base, src)
        extras.append(f"- [{title}]({url})" + (f": {note}" if note else ""))
    if extras:
        lines.append("## Optional")
        lines.append("")
        lines.extend(extras)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_full(site_url: str, docs_dir: pathlib.Path) -> str:
    """Render ``llms-full.txt`` by inlining the README and every doc page.

    Args:
        site_url: The published site root URL.
        docs_dir: The MkDocs ``docs/`` directory.

    Returns:
        The full ``llms-full.txt`` content.
    """
    base = site_url if site_url.endswith("/") else site_url + "/"
    parts: list[str] = [
        "# tempestroid — full documentation",
        "",
        f"> {SUMMARY}",
        "",
        (
            "Generated from the project docs (llmstxt.org convention). Source: "
            f"{base} — index at {base}llms.txt."
        ),
        "",
    ]

    readme = docs_dir.parent / "README.md"
    if readme.exists():
        parts.append("---")
        parts.append("")
        parts.append("# File: README.md")
        parts.append("")
        parts.append(_read(readme).strip())
        parts.append("")

    for _, items in SECTIONS:
        for src in items:
            path = docs_dir / src
            if not path.exists():
                continue
            parts.append("---")
            parts.append("")
            parts.append(f"# File: docs/{src} — {_doc_url(base, src)}")
            parts.append("")
            parts.append(_read(path).strip())
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def on_post_build(config: Any, **kwargs: Any) -> None:  # noqa: ANN401
    """Write ``llms.txt`` + ``llms-full.txt`` into the built site root.

    Runs once after MkDocs (and the i18n plugin) finish building, so the files
    land at the GitHub Pages root alongside ``index.html``.

    Args:
        config: The resolved MkDocs config (provides ``site_dir``, ``site_url``,
            ``docs_dir``).
        **kwargs: Unused MkDocs hook keyword arguments.
    """
    site_dir = pathlib.Path(config["site_dir"])
    docs_dir = pathlib.Path(config["docs_dir"])
    site_url = config.get("site_url") or "https://mauriciobenjamin700.github.io/tempestroid/"

    site_dir.mkdir(parents=True, exist_ok=True)
    index = _build_index(site_url, docs_dir)
    full = _build_full(site_url, docs_dir)
    (site_dir / "llms.txt").write_text(index, encoding="utf-8")
    (site_dir / "llms-full.txt").write_text(full, encoding="utf-8")
