"""Pure helpers of the search functions in retrieve.py (SQL itself is exercised by scripts/rag_spike.py)."""
from backend.pipeline.retrieve import or_tsquery_text, query_terms, rrf_fuse


def test_query_terms_drops_stop_words_and_dedupes_keeping_order():
    assert query_terms("how do I stop a disk, stop it NOW") == ["stop", "disk", "NOW"]


def test_query_terms_keeps_command_and_message_tokens():
    assert query_terms("terminal error 3123 no server process linked") == \
        ["terminal", "error", "3123", "server", "process", "linked"]
    assert "#PROCESSINFO" in query_terms("what does #PROCESSINFO return")
    assert "$DATA00" in query_terms("revive $DATA00")


def test_or_tsquery_text_joins_with_or():
    assert or_tsquery_text("stop a disk") == "stop or disk"
    assert or_tsquery_text("the of a") == ""


def test_rrf_prefers_items_ranked_well_by_both_lists():
    fused = rrf_fuse([["a", "b"], ["c", "b"]], k=60)
    order = [i for i, _ in fused]
    assert order[0] == "b"                       # rank 2 + rank 2 beats rank 1 + absent
    assert set(order) == {"a", "b", "c"}


def test_rrf_top_and_deterministic_ties():
    fused = rrf_fuse([["x", "y"], ["y", "x"]], top=1)
    assert fused[0][0] == "x"                    # exact tie -> id order
    assert len(fused) == 1


def test_rrf_empty_lists():
    assert rrf_fuse([[], []]) == []
