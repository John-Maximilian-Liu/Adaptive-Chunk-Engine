"""SVG security sanitization — allowlist only."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

ALLOWED_ELEMENTS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "title", "desc", "defs", "use", "symbol", "clipPath", "mask",
    "linearGradient", "radialGradient", "stop", "pattern",
}
ALLOWED_ATTRS = {
    "id", "class", "transform", "fill", "stroke", "stroke-width", "stroke-linecap",
    "stroke-linejoin", "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity",
    "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "viewBox", "xmlns", "points", "offset", "stop-color", "stop-opacity",
    "font-size", "font-family", "text-anchor", "dominant-baseline", "clip-path",
    "xlink:href", "href",
}
EVENT_ATTR_RE = re.compile(r"^on", re.I)
DANGEROUS_URL_RE = re.compile(r"^\s*(javascript:|data:text/html|data:image/svg)", re.I)


class SvgSecurityError(Exception):
    pass


def sanitize_svg(
    svg_text: str,
    *,
    max_bytes: int = 10_000_000,
    max_elements: int = 10_000,
    max_path_commands: int = 200_000,
    max_nesting_depth: int = 32,
    allow_external_references: bool = False,
    allow_scripts: bool = False,
    allow_foreign_object: bool = False,
) -> tuple[str, dict]:
    if len(svg_text.encode("utf-8")) > max_bytes:
        raise SvgSecurityError("SVG exceeds max file size")
    # Strip scripts early
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", svg_text, flags=re.I)
    cleaned = re.sub(r"<foreignObject[\s\S]*?</foreignObject>", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<(iframe|object|embed)[\s\S]*?</\1>", "", cleaned, flags=re.I)
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        raise SvgSecurityError(f"Invalid SVG XML: {exc}") from exc

    stats = {"elements": 0, "path_commands": 0, "max_depth": 0, "removed": []}

    def walk(node: ET.Element, depth: int) -> bool:
        stats["max_depth"] = max(stats["max_depth"], depth)
        if depth > max_nesting_depth:
            stats["removed"].append("max_nesting")
            return False
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
        if tag.lower() == "script" and not allow_scripts:
            stats["removed"].append("script")
            return False
        if tag.lower() == "foreignobject" and not allow_foreign_object:
            stats["removed"].append("foreignObject")
            return False
        if tag.lower() in {"iframe", "object", "embed"}:
            stats["removed"].append(tag)
            return False
        if tag not in ALLOWED_ELEMENTS:
            stats["removed"].append(tag)
            return False
        stats["elements"] += 1
        if stats["elements"] > max_elements:
            raise SvgSecurityError("SVG exceeds max element count")

        # filter attributes
        for attr in list(node.attrib.keys()):
            local = attr.split("}")[-1] if "}" in attr else attr
            if EVENT_ATTR_RE.match(local):
                del node.attrib[attr]
                stats["removed"].append(f"attr:{local}")
                continue
            if local not in ALLOWED_ATTRS and not local.startswith("data-"):
                # keep data-* for mapping; drop others
                if not local.startswith("data-"):
                    del node.attrib[attr]
                    stats["removed"].append(f"attr:{local}")
                    continue
            val = node.attrib.get(attr, "")
            if local in {"href", "xlink:href"}:
                if DANGEROUS_URL_RE.search(val) or (not allow_external_references and val.startswith("http")):
                    del node.attrib[attr]
                    stats["removed"].append("external_ref")
                    continue
                if not allow_external_references and not val.startswith("#"):
                    del node.attrib[attr]
                    stats["removed"].append("non_fragment_href")
            if local == "d":
                # rough path command count
                cmds = len(re.findall(r"[MmLlHhVvCcSsQqTtAaZz]", val))
                stats["path_commands"] += cmds
                if stats["path_commands"] > max_path_commands:
                    raise SvgSecurityError("SVG exceeds max path commands")

        # children
        keep_children = []
        for child in list(node):
            if walk(child, depth + 1):
                keep_children.append(child)
            else:
                node.remove(child)
        return True

    if not walk(root, 1):
        raise SvgSecurityError("Root element not allowed")

    # Re-serialize
    out = ET.tostring(root, encoding="unicode")
    if not out.strip().startswith("<svg") and "<svg" not in out[:200]:
        # ensure svg root name without namespace issues
        pass
    return out, stats
