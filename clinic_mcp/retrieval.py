"""Hybrid retrieval: dense (pgvector) + full-text (tsvector), fused with RRF.

Copied/adapted from docs-rag-chatbot so this repo keeps retrieval local while
reading the shared `chunks` table.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from clinic_mcp import db
from clinic_mcp.embed import embed_one
from clinic_mcp.schemas import DocChunk, SearchClinicDocsResult

load_dotenv()

RRF_K = 60
CANDIDATES = 20
SIMILARITY_FLOOR = float(os.environ.get("SIMILARITY_FLOOR", "0.35"))

NO_SOURCES_MESSAGE = (
    "No relevant sources found in the clinic knowledge base for this query. "
    "Do not invent clinic policies, prices, or insurance details."
)


def dense_search(query_vec, n=CANDIDATES):
    return db.fetchall(
        """
        SELECT id, source_filename, doc_title, chunk,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_vec, query_vec, n),
    )


def keyword_search(query, n=CANDIDATES):
    return db.fetchall(
        """
        SELECT id, source_filename, doc_title, chunk,
               ts_rank(tsv, plainto_tsquery('english', %s)) AS score
        FROM chunks
        WHERE tsv @@ plainto_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s
        """,
        (query, query, n),
    )


def rrf_fuse(lists, k=RRF_K):
    scores = {}
    payloads = {}
    for results in lists:
        for rank, row in enumerate(results):
            cid = row["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            payloads[cid] = row
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for cid, rrf_score in ranked:
        row = dict(payloads[cid])
        row["rrf_score"] = rrf_score
        out.append(row)
    return out


def hybrid_search(query: str, k: int = 5) -> tuple[list[dict], float]:
    """
    Returns (chunks, best_dense_score).
    best_dense_score is the top cosine similarity — used as the anti-hallucination gate.
    """
    query_vec = embed_one(query)
    dense = dense_search(query_vec)
    keyword = keyword_search(query)

    best_dense = float(dense[0]["score"]) if dense else 0.0
    fused = rrf_fuse([dense, keyword])[:k]

    dense_by_id = {r["id"]: float(r["score"]) for r in dense}
    for row in fused:
        row["score"] = dense_by_id.get(row["id"], float(row.get("score") or 0.0))

    return fused, best_dense


def search_clinic_docs(query: str, top_k: int = 5) -> SearchClinicDocsResult:
    """Public tool helper: hybrid search + similarity floor gate."""
    chunks, best_dense = hybrid_search(query, k=top_k)

    if best_dense < SIMILARITY_FLOOR or not chunks:
        return SearchClinicDocsResult(
            status="no_relevant_sources",
            query=query,
            similarity_floor=SIMILARITY_FLOOR,
            best_dense_score=round(best_dense, 4),
            message=NO_SOURCES_MESSAGE,
            chunks=[],
        )

    return SearchClinicDocsResult(
        status="ok",
        query=query,
        similarity_floor=SIMILARITY_FLOOR,
        best_dense_score=round(best_dense, 4),
        message=None,
        chunks=[
            DocChunk(
                source_filename=c["source_filename"],
                doc_title=c["doc_title"],
                chunk=c["chunk"],
                score=round(float(c["score"]), 4),
                rrf_score=round(float(c["rrf_score"]), 6),
            )
            for c in chunks
        ],
    )
