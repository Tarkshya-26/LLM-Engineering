"""Phase 4 - deterministic tests for model-supplied rank order validation.

Covers the three defects named in the Phase 4 brief: negative-index wrapping,
out-of-range access, and unauthorized document selection. No API calls.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pro_implementation"))

from security.rank_safety import safe_reorder, validate_rank_order  # noqa: E402


class Chunk:
    def __init__(self, doc_id, merchant_id="merchant_gamma"):
        self.page_content = doc_id
        self.metadata = {"document_id": doc_id, "merchant_id": merchant_id}

    def __repr__(self):
        return self.metadata["document_id"]


def chunks(n):
    return [Chunk(f"DOC-{i}") for i in range(1, n + 1)]


def is_permutation(out, src):
    return sorted(id(c) for c in out) == sorted(id(c) for c in src)


# --- D1: negative-index wrapping -------------------------------------------

@pytest.mark.parametrize("bad", [0, -1, -3, -999])
def test_non_positive_indices_never_reach_a_subscript(bad):
    """chunks[0 - 1] is chunks[-1] in Python - silent selection from the tail."""
    assert bad not in validate_rank_order([bad, 1, 2, 3], 3)


def test_zero_index_does_not_select_the_last_chunk():
    src = chunks(3)
    out = safe_reorder(src, [0, 0, 0])
    assert out[0] is src[0], "index 0 must not wrap to the final chunk"
    assert is_permutation(out, src)


def test_all_negative_order_still_yields_full_permutation():
    src = chunks(4)
    out = safe_reorder(src, [-1, -2, -3, -4])
    assert is_permutation(out, src)
    assert out == src, "with no usable order, original order is preserved"


# --- D2: out-of-range access ------------------------------------------------

@pytest.mark.parametrize("bad", [4, 5, 99, 10**9])
def test_out_of_range_indices_are_discarded(bad):
    assert bad not in validate_rank_order([bad], 3)


def test_out_of_range_does_not_raise():
    """The baseline raises IndexError here - a DoS any merchant can trigger."""
    src = chunks(3)
    assert is_permutation(safe_reorder(src, [99, 1000, 2]), src)


def test_baseline_really_does_break_on_these():
    """Pins the defect this module exists to fix, so the contrast is testable."""
    src = chunks(3)
    with pytest.raises(IndexError):
        [src[i - 1] for i in [99]]
    assert [src[i - 1] for i in [0]] == [src[-1]], "baseline wraps index 0"


# --- D3: set mutation / unauthorized document selection ---------------------

def test_output_is_always_a_permutation_of_the_input():
    src = chunks(5)
    for order in ([5, 4, 3, 2, 1], [1], [], [3, 3, 3], [0, -2, 99], [2, 2, 1, 7]):
        assert is_permutation(safe_reorder(src, order), src), order


def test_duplicates_cannot_occupy_multiple_slots():
    src = chunks(4)
    out = safe_reorder(src, [2, 2, 2, 2])
    assert len({id(c) for c in out}) == 4


def test_omitted_chunks_are_not_silently_dropped():
    """A hijacked reranker must not be able to delete the guaranteed policy chunk."""
    src = chunks(4)
    out = safe_reorder(src, [4])
    assert is_permutation(out, src)
    assert out[0] is src[3]


def test_reranker_cannot_introduce_a_document_it_was_not_given():
    """The core anti-selection property: output is drawn only from the input.

    There is no index, however malformed, that reaches a chunk outside `src` -
    so a compromised reranker cannot pull in a document the Phase 2 authorization
    filter excluded.
    """
    src = [Chunk("GAMMA-1"), Chunk("GAMMA-2")]
    foreign = Chunk("ALPHA-SECRET", merchant_id="merchant_alpha")
    out = safe_reorder(src, [1, 2, 3, -1, 99])
    assert foreign not in out
    assert {c.metadata["merchant_id"] for c in out} == {"merchant_gamma"}


def test_permutation_holds_for_arbitrary_garbage():
    src = chunks(3)
    for order in (None, ["a", "b"], [None], [True, False], [1.5, 2.5], [[1], {2: 3}]):
        assert is_permutation(safe_reorder(src, order), src), order


def test_booleans_are_not_treated_as_indices():
    """True == 1 in Python; without an explicit bool check it silently ranks."""
    assert validate_rank_order([True, 2], 3) == [2, 1, 3]


def test_empty_chunk_list_is_safe():
    assert safe_reorder([], [1, 2, 3]) == []
