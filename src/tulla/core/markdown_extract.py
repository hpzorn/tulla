"""Shared markdown extraction helpers for phase output parsing.

Provides reusable functions for extracting structured data from the
markdown files that Claude produces during discovery and planning phases.

Used by phase ``parse_output()`` methods to populate semantic IntentFields.
"""

from __future__ import annotations

import re
from typing import Any


def extract_section(
    content: str,
    heading: str,
    *,
    level: int = 2,
) -> str:
    """Extract markdown section text under *heading* until the next heading.

    Parameters:
        content: Full markdown document.
        heading: Heading text to search for (without ``#`` prefix).
        level: Heading level (2 = ``##``, 3 = ``###``).

    Returns:
        Section body text, or empty string if heading not found.
    """
    hashes = "#" * level
    pattern = rf"{hashes}\s+{re.escape(heading)}\s*\n(.*?)(?=\n{'#' * level}\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_table_rows(section: str) -> list[dict[str, str]]:
    """Parse a markdown table into a list of dicts keyed by header names.

    Handles standard GFM tables::

        | Col A | Col B | Col C |
        |-------|-------|-------|
        | val1  | val2  | val3  |

    Returns:
        List of ``{header: value}`` dicts, one per data row.
        Empty list if no valid table found.
    """
    lines = [
        line.strip()
        for line in section.strip().splitlines()
        if line.strip()
    ]
    if len(lines) < 2:
        return []

    # Find header row (first row starting and ending with |)
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("|") and line.endswith("|"):
            header_idx = i
            break
    if header_idx is None:
        return []

    headers = _parse_table_cells(lines[header_idx])
    if not headers:
        return []

    rows: list[dict[str, str]] = []
    for line in lines[header_idx + 1 :]:
        if not (line.startswith("|") and line.endswith("|")):
            continue
        # Skip separator rows like |---|---|---|
        if re.match(r"^\|[\s:-]+\|", line):
            continue
        cells = _parse_table_cells(line)
        row = {}
        for j, header in enumerate(headers):
            row[header] = cells[j] if j < len(cells) else ""
        rows.append(row)

    return rows


def count_table_rows(section: str) -> int:
    """Count markdown table data rows (excludes header and separator rows)."""
    return len(extract_table_rows(section))


def extract_bullet_items(section: str) -> list[str]:
    """Extract bullet point items from a markdown section.

    Recognises ``-``, ``*``, and ``1.`` list markers.  Multi-line items
    (continuation lines indented under a bullet) are joined into a single
    string.

    Returns:
        List of item strings with leading markers stripped.
    """
    items: list[str] = []
    current: list[str] = []

    for line in section.splitlines():
        stripped = line.strip()
        # Bullet or numbered-list start
        match = re.match(r"^[-*]\s+(.+)", stripped) or re.match(
            r"^\d+\.\s+(.+)", stripped,
        )
        if match:
            if current:
                items.append(" ".join(current))
            current = [match.group(1).strip()]
        elif stripped and current:
            # Continuation line
            current.append(stripped)

    if current:
        items.append(" ".join(current))

    return items


def extract_checklist_items(section: str) -> list[str]:
    """Extract ``- [ ] item`` or ``- [x] item`` checklist items."""
    items: list[str] = []
    for line in section.splitlines():
        match = re.match(r"^\s*-\s+\[[ xX]\]\s+(.+)", line)
        if match:
            items.append(match.group(1).strip())
    return items


def trim_text(text: str, max_chars: int = 500) -> str:
    """Trim *text* to *max_chars* at a sentence boundary.

    Prefers breaking at ``.``, ``!``, or ``?`` followed by a space.
    Falls back to a hard cut with ``...`` suffix.
    """
    if len(text) <= max_chars:
        return text

    # Look for the last sentence boundary before max_chars.
    truncated = text[:max_chars]
    last_sentence_end = max(
        truncated.rfind(". "),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_sentence_end > max_chars // 2:
        return truncated[: last_sentence_end + 1]

    return truncated.rstrip() + "..."


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def extract_rq_sections(content: str) -> list[dict[str, str]]:
    """Split markdown into per-RQ sections.

    Finds all ``### RQ{N}: [title]`` headings and returns each as a dict
    with ``id``, ``title``, and ``body`` keys.

    Returns:
        List of ``{"id": "RQ1", "title": "How does X work?", "body": "..."}``
        dicts.  Empty list if no RQ headings found.
    """
    parts = re.split(r"(?=###\s+RQ\d+:)", content)
    sections: list[dict[str, str]] = []
    for part in parts:
        match = re.match(r"###\s+(RQ\d+):\s*([^\n]+)\n(.*)", part, re.DOTALL)
        if match:
            sections.append({
                "id": match.group(1),
                "title": match.group(2).strip(),
                "body": match.group(3).strip(),
            })
    return sections


def extract_field(section: str, field_name: str) -> str:
    """Extract value after ``**field_name**:`` from a markdown section.

    Parameters:
        section: Markdown text to search.
        field_name: Bold field name (without ``**`` delimiters).

    Returns:
        Trimmed value string, or empty string if not found.
    """
    m = re.search(rf"\*\*{re.escape(field_name)}\*\*:\s*(.+)", section)
    return m.group(1).strip() if m else ""


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _parse_table_cells(row: str) -> list[str]:
    """Split a markdown table row into trimmed cell values."""
    # Strip leading/trailing pipes, then split by |
    inner = row.strip().strip("|")
    return [cell.strip() for cell in inner.split("|")]
