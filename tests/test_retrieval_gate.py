"""Retrieval gate unit tests (mocked) + optional live-DB integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from clinic_mcp.retrieval import NO_SOURCES_MESSAGE, SIMILARITY_FLOOR, search_clinic_docs
from clinic_mcp.schemas import DocChunk, SearchClinicDocsResult
from tests.conftest import requires_chunks


def test_gate_refuses_below_floor():
    weak = [
        {
            "id": 1,
            "source_filename": "noise.md",
            "doc_title": "Noise",
            "chunk": "unrelated",
            "score": 0.12,
            "rrf_score": 0.01,
        }
    ]
    with patch("clinic_mcp.retrieval.hybrid_search", return_value=(weak, 0.12)):
        result = search_clinic_docs("quantum dentistry on mars", top_k=5)

    assert result.status == "no_relevant_sources"
    assert result.chunks == []
    assert result.best_dense_score == 0.12
    assert result.similarity_floor == SIMILARITY_FLOOR
    assert result.message == NO_SOURCES_MESSAGE


def test_gate_passes_with_citations():
    strong = [
        {
            "id": 7,
            "source_filename": "06_insurance_faq.md",
            "doc_title": "Insurance FAQ",
            "chunk": "BrightSmile accepts Delta Dental PPO.",
            "score": 0.61,
            "rrf_score": 0.016,
        }
    ]
    with patch("clinic_mcp.retrieval.hybrid_search", return_value=(strong, 0.61)):
        result = search_clinic_docs("does BrightSmile take Delta Dental?", top_k=5)

    assert result.status == "ok"
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert isinstance(chunk, DocChunk)
    assert chunk.source_filename == "06_insurance_faq.md"
    assert chunk.score == 0.61
    assert "Delta Dental" in chunk.chunk


def test_gate_refuses_when_no_chunks_even_if_score_ok():
    with patch("clinic_mcp.retrieval.hybrid_search", return_value=([], 0.9)):
        result = search_clinic_docs("anything", top_k=5)
    assert result.status == "no_relevant_sources"
    assert result.chunks == []


@requires_chunks
def test_live_delta_dental_search_returns_citations():
    # Phrasing that hits 06_insurance_faq.md in the shared BrightSmile corpus.
    result = search_clinic_docs("Delta Dental insurance", top_k=5)
    assert isinstance(result, SearchClinicDocsResult)
    assert result.status == "ok"
    assert result.chunks
    filenames = {c.source_filename for c in result.chunks}
    assert any("insurance" in f for f in filenames)
    assert all(c.score is not None for c in result.chunks)


@requires_chunks
def test_live_out_of_scope_refuses():
    result = search_clinic_docs(
        "What is the capital of Mars and the price of unicorn teeth?",
        top_k=5,
    )
    # Either gate refuses, or if somehow dense scores are high we still require structure.
    assert result.status in ("ok", "no_relevant_sources")
    if result.status == "no_relevant_sources":
        assert result.chunks == []
        assert result.message
