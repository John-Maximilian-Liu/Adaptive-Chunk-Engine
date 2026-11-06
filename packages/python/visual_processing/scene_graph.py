"""Visual scene graph validation and deterministic SVG rendering."""
from __future__ import annotations

from typing import Any

from canonical_schemas.visual import VisualEdge, VisualGroup, VisualNode, VisualSceneGraph
from shared.ids import new_id


def validate_scene_graph(graph: VisualSceneGraph | dict[str, Any]) -> VisualSceneGraph:
    if isinstance(graph, dict):
        graph = VisualSceneGraph.model_validate(graph)
    errors = []
    node_ids = {n.node_id for n in graph.nodes}
    for n in graph.nodes:
        if not n.label and n.node_type == "unknown":
            errors.append(f"node {n.node_id} missing label")
        if n.bbox and len(n.bbox) != 4:
            errors.append(f"node {n.node_id} invalid bbox")
    for e in graph.edges:
        if e.source_node_id not in node_ids:
            errors.append(f"edge {e.edge_id} source missing")
        if e.target_node_id not in node_ids:
            errors.append(f"edge {e.edge_id} target missing")
    for g in graph.groups:
        for nid in g.node_ids:
            if nid not in node_ids:
                errors.append(f"group {g.group_id} references missing node {nid}")
    graph.validation_errors = errors
    graph.validated = len(errors) == 0
    return graph


def render_semantic_svg(graph: VisualSceneGraph, *, width: int = 400, height: int = 300) -> str:
    """Deterministic SVG from validated scene graph — LLM never emits trusted final SVG."""
    if not graph.validated:
        graph = validate_scene_graph(graph)
        if not graph.validated:
            raise ValueError(f"Scene graph invalid: {graph.validation_errors}")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Semantic reconstruction</title>",
    ]
    # groups
    for g in graph.groups:
        parts.append(f'<g id="{g.group_id}" data-label="{_esc(g.label)}">')
        for nid in g.node_ids:
            node = next(n for n in graph.nodes if n.node_id == nid)
            parts.append(_render_node(node))
        parts.append("</g>")
    # ungrouped nodes
    grouped = {nid for g in graph.groups for nid in g.node_ids}
    for n in graph.nodes:
        if n.node_id not in grouped:
            parts.append(_render_node(n))
    # edges
    for e in graph.edges:
        src = next(n for n in graph.nodes if n.node_id == e.source_node_id)
        tgt = next(n for n in graph.nodes if n.node_id == e.target_node_id)
        x1, y1 = _center(src)
        x2, y2 = _center(tgt)
        eid = e.svg_element_id or e.edge_id
        parts.append(
            f'<line id="{eid}" data-edge-type="{_esc(e.edge_type)}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" />'
        )
        if e.label:
            parts.append(f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2}" font-size="10">{_esc(e.label)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _render_node(node: VisualNode) -> str:
    bbox = node.bbox or [10, 10, 90, 50]
    x, y, x2, y2 = bbox
    w, h = max(x2 - x, 20), max(y2 - y, 16)
    sid = node.svg_element_id or node.node_id
    return (
        f'<g id="{sid}" data-node-type="{_esc(node.node_type)}">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#e8f0fe" stroke="#1a73e8" stroke-width="1.5" />'
        f'<text x="{x + 4}" y="{y + h/2 + 4}" font-size="12">{_esc(node.label)}</text>'
        f"</g>"
    )


def _center(node: VisualNode) -> tuple[float, float]:
    b = node.bbox or [0, 0, 40, 20]
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
