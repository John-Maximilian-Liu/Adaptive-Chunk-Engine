"""Document parsers with Docling preferred path and local fallbacks."""
from document_parsers.base import ParseResult, ParserAdapter, get_parser_for
from document_parsers.registry import list_parsers

__all__ = ["ParseResult", "ParserAdapter", "get_parser_for", "list_parsers"]
