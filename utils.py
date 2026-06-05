"""
Text processing utilities shared across all layers.

count_words() and strip_markdown() are the single canonical implementations.
Every layer — database (word count storage), export (PDF/DOCX/EPUB),
and pages (live counter display) — imports from here.
"""
import re

# Pre-compiled patterns
_FENCED_CODE     = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_IMAGE           = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_LINK            = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HTML_TAG        = re.compile(r"<[^>]+>")
_HEADING         = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_ITALIC     = re.compile(r"\*{1,3}(.+?)\*{1,3}", re.DOTALL)
_STRIKETHROUGH   = re.compile(r"~~(.+?)~~", re.DOTALL)
_INLINE_CODE     = re.compile(r"`+(.+?)`+", re.DOTALL)
_HORIZONTAL_RULE = re.compile(r"^\s*[-*_]{3,}\s*$", re.MULTILINE)
_BLOCKQUOTE      = re.compile(r"^>\s?", re.MULTILINE)
_LIST_MARKER     = re.compile(r"^\s*[-*+]\s+|^\s*\d+\.\s+", re.MULTILINE)
_MULTI_SPACE     = re.compile(r"  +")


def strip_markdown(text: str) -> str:
    """Remove all Markdown syntax, returning plain prose text."""
    if not text:
        return ""
    text = _FENCED_CODE.sub(" ", text)
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _HEADING.sub("", text)
    text = _BOLD_ITALIC.sub(r"\1", text)
    text = _STRIKETHROUGH.sub(r"\1", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HORIZONTAL_RULE.sub("", text)
    text = _BLOCKQUOTE.sub("", text)
    text = _LIST_MARKER.sub("", text)
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def count_words(text: str) -> int:
    """Count real prose words, ignoring all Markdown markup."""
    if not text or not text.strip():
        return 0
    return len(strip_markdown(text).split())
