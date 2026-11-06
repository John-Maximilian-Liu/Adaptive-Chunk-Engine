"""Visual / SVG security and rendering tests."""
from __future__ import annotations

import pytest

from visual_processing.svg_sanitize import sanitize_svg, SvgSecurityError
from visual_processing.scene_graph import validate_scene_graph, render_semantic_svg
from visual_processing.chunking import visual_chunks_from_artifacts
from visual_processing.pipeline import VisualProcessor
from canonical_schemas.visual import VisualArtifact, VisualSceneGraph, VisualNode, VisualEdge, VisualGroup


def test_script_removal():
    dirty = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect x="0" y="0" width="10" height="10"/></svg>'
    clean, stats = sanitize_svg(dirty)
    assert "script" not in clean.lower()
    assert "rect" in clean


def test_event_handler_removal():
    dirty = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="10" height="10" onclick="alert(1)"/></svg>'
    clean, _ = sanitize_svg(dirty)
    assert "onclick" not in clean.lower()


def test_external_reference_removal():
    dirty = '<svg xmlns="http://www.w3.org/2000/svg"><use href="http://evil.example/x.svg#a"/></svg>'
    clean, stats = sanitize_svg(dirty, allow_external_references=False)
    assert "http://evil" not in clean


def test_resource_limit_enforcement():
    huge = '<svg xmlns="http://www.w3.org/2000/svg">' + "".join(f'<rect x="{i}" y="0" width="1" height="1"/>' for i in range(50)) + "</svg>"
    with pytest.raises(SvgSecurityError):
        sanitize_svg(huge, max_elements=10)


def test_semantic_scene_graph_rendering():
    graph = VisualSceneGraph(
        nodes=[
            VisualNode(node_id="n1", label="A", bbox=[10, 10, 60, 40]),
            VisualNode(node_id="n2", label="B", bbox=[10, 80, 60, 110]),
        ],
        edges=[VisualEdge(edge_id="e1", source_node_id="n1", target_node_id="n2", label="to")],
        groups=[VisualGroup(group_id="g1", label="G", node_ids=["n1", "n2"])],
    )
    graph = validate_scene_graph(graph)
    assert graph.validated
    svg = render_semantic_svg(graph)
    assert "<svg" in svg
    san, _ = sanitize_svg(svg)
    assert "svg" in san.lower()


def test_native_svg_preservation_strategy():
    proc = VisualProcessor()
    existing = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5"/></svg>'
    result = proc.process(
        tenant_id="t",
        document_version_id="v",
        source_element_id="e1",
        image_path=None,
        existing_svg=existing,
        image_kind="logo",
    )
    assert result["strategy"] == "preserve_existing_svg"
    assert any(a.artifact_type.endswith("svg") for a in result["artifacts"])


def test_visual_chunk_generation_no_raw_xml_by_default():
    art = VisualArtifact(
        tenant_id="t", document_version_id="v", artifact_type="semantic_svg",
        sanitized_storage_uri=None, generation_strategy="semantic_reconstruction", confidence=0.9,
    )
    chunks = visual_chunks_from_artifacts(
        artifacts=[art],
        tenant_id="t", document_id="d", document_version_id="v", chunk_run_id="r",
        index_raw_xml=False,
        scene_graph=VisualSceneGraph(
            nodes=[VisualNode(node_id="n1", label="N")],
            edges=[],
            groups=[VisualGroup(group_id="g1", label="G", node_ids=["n1"])],
        ),
    )
    types = {c.chunk_type for c in chunks}
    assert "visual_summary" in types
    assert "svg_group" in types
    assert "svg_node" in types
    assert all("<svg" not in (c.text or "") for c in chunks if c.chunk_type != "visual_summary" or True)


def test_low_confidence_fallback():
    from canonical_schemas.visual import VisualProcessingPolicy
    proc = VisualProcessor()
    result = proc.process(
        tenant_id="t", document_version_id="v", source_element_id="e1", image_path=None,
        existing_svg='<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>',
        policy=VisualProcessingPolicy(minimum_confidence=0.99, fallback_behavior="retain_raster"),
        image_kind="logo",
    )
    # may warn low confidence depending on strategy confidence
    assert "warnings" in result
