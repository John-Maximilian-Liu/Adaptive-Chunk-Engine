"""Generate searchable visual chunks — never index raw SVG XML by default."""
from __future__ import annotations

from typing import Any, Optional

from canonical_schemas.chunk import CanonicalChunk, LocatorRef
from canonical_schemas.visual import VisualArtifact, VisualSceneGraph
from shared.hashing import stable_json_hash
from visual_processing.scene_graph import validate_scene_graph


def visual_chunks_from_artifacts(
    *,
    artifacts: list[VisualArtifact],
    tenant_id: str,
    document_id: str,
    document_version_id: str,
    chunk_run_id: str,
    experiment_id: Optional[str] = None,
    index_raw_xml: bool = False,
    scene_graph: Optional[VisualSceneGraph] = None,
) -> list[CanonicalChunk]:
    chunks: list[CanonicalChunk] = []
    ordinal = 0

    for art in artifacts:
        if art.artifact_type == "ocr" and art.content_text:
            chunks.append(_mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "image_ocr", art.content_text, art))
            ordinal += 1
        elif art.artifact_type == "caption" and art.content_text:
            chunks.append(_mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "image_caption", art.content_text, art))
            ordinal += 1
        elif art.artifact_type in {"semantic_svg", "geometric_svg", "native_svg"}:
            summary = f"Visual artifact {art.visual_artifact_id} generated via {art.generation_strategy}"
            chunks.append(_mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "visual_summary", summary, art))
            ordinal += 1
            if index_raw_xml and art.sanitized_storage_uri:
                # explicitly off by default
                from pathlib import Path
                xml = Path(art.sanitized_storage_uri).read_text(encoding="utf-8")
                chunks.append(_mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "visual_summary", xml, art))
                ordinal += 1

    if scene_graph:
        graph = validate_scene_graph(scene_graph)
        for g in graph.groups:
            text = f"SVG group {g.label}: nodes={', '.join(g.node_ids)}"
            c = _mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "svg_group", text, None)
            c.svg_group_id = g.group_id
            c.visual_artifact_id = None
            chunks.append(c)
            ordinal += 1
        for n in graph.nodes:
            text = f"SVG node {n.label} ({n.node_type})"
            c = _mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "svg_node", text, None)
            c.svg_element_id = n.svg_element_id or n.node_id
            chunks.append(c)
            ordinal += 1
        for e in graph.edges:
            text = f"SVG relationship {e.source_node_id} -[{e.label or e.edge_type}]-> {e.target_node_id}"
            c = _mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, "svg_relationship", text, None)
            c.svg_element_id = e.svg_element_id or e.edge_id
            chunks.append(c)
            ordinal += 1

    return chunks


def _mk(tenant_id, document_id, document_version_id, chunk_run_id, experiment_id, ordinal, chunk_type, text, art: Optional[VisualArtifact]) -> CanonicalChunk:
    c = CanonicalChunk(
        chunk_run_id=chunk_run_id,
        document_id=document_id,
        document_version_id=document_version_id,
        experiment_id=experiment_id,
        tenant_id=tenant_id,
        ordinal=ordinal,
        chunk_type=chunk_type,
        text=text,
        embedding_text=text,
        canonical_strategy="visual_derived",
        adapter_id="visual.chunking",
        provider="visual_processing",
        provider_version="1.0.0",
        indexable=True,
        visual_artifact_id=art.visual_artifact_id if art else None,
        locators=[LocatorRef(
            page=art.page if art else None,
            slide=art.slide if art else None,
            sheet=art.sheet if art else None,
            bbox=art.bbox if art else None,
            element_id=art.source_element_id if art else None,
            locator_type="image_region" if art and art.artifact_type in {"ocr", "raster"} else "svg_element",
        )] if art else [],
        parameters={"generation_strategy": art.generation_strategy if art else None},
        configuration_hash=stable_json_hash({"type": chunk_type}),
        confidence=art.confidence if art else None,
    )
    return c.finalize_measurements()
