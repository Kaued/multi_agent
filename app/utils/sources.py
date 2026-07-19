import re

SOURCE_LINE_PATTERN = re.compile(
    r"^-\s+(.+?)\s+—\s+(https?://\S+)\s*$",
    flags=re.MULTILINE,
)
_LINE_PATTERN = re.compile(r"^.*$", flags=re.MULTILINE)
_SOURCE_HEADINGS = {"source", "sources", "font", "fonte", "fontes"}


def find_source_heading(content: str) -> re.Match[str] | None:
    """Find source headings despite Markdown and singular/plural variations."""
    for line in _LINE_PATTERN.finditer(content):
        normalized = line.group().strip().lstrip("#").strip()
        normalized = normalized.replace("*", "").replace("_", "").strip()
        heading = normalized.partition(":")[0].strip().casefold()
        if heading in _SOURCE_HEADINGS:
            return line
    return None


def ensure_sources_section(content: str, sources: list[tuple[str, str]]) -> str:
    """Replace any model-written source appendix with one verified section."""
    if not sources:
        return content

    heading = find_source_heading(content)
    answer = content[: heading.start()].rstrip() if heading else content.rstrip()
    unique_sources: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for title, url in sources:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_sources.append((title, url))

    source_lines = "\n".join(f"- {title} — {url}" for title, url in unique_sources)
    return f"{answer}\n\nSources\n\n{source_lines}"
