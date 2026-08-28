"""Phase 4 - deterministic validation of model-supplied rank orders.

=============================================================================
THREAT MODEL
=============================================================================
The reranker is an LLM that reads untrusted chunk text and emits a list of
integers. The baseline then does:

    return [chunks[i - 1] for i in order]

Three defects, all reachable by an attacker who can steer the reranker's output
(the chunk text it reads is merchant-controlled, and the prompt delimits chunks
with "# CHUNK ID: n:" which merchant text can imitate):

  D1. NEGATIVE-INDEX WRAPPING. i = 0 gives chunks[-1]; i = -3 gives chunks[-3].
      Python indexes from the end silently. The attacker selects from the tail of
      the candidate list rather than being rejected.

  D2. OUT-OF-RANGE ACCESS. i > len(chunks) raises IndexError, which propagates
      through @retry and eventually fails the request. A denial of service that
      any merchant can trigger by getting text into the corpus.

  D3. SET MUTATION. Duplicates let one chunk occupy several context slots -
      the attacker's document crowds out policy. Omissions silently drop chunks,
      including the authoritative policy Phase 3 guaranteed.

=============================================================================
THE PROPERTY BEING ENFORCED
=============================================================================
    THE RERANKER MAY PERMUTE. IT MAY NOT CHOOSE THE SET.

Output is always exactly a permutation of the input: same multiset, same length.
Reordering is a relevance judgement and the model is allowed to make it.
Membership is an authorization-adjacent decision and the model is not.

This is what makes "unauthorized document selection" structurally impossible
here: `safe_reorder` only ever emits chunks that were passed in, so it cannot
introduce a chunk the Phase 2 filter excluded - there is no code path by which an
index, however malformed, reaches outside the input list.

=============================================================================
FAILURE MODES
=============================================================================
F1. A model that returns a useless order still gets its permutation applied.
    This validates STRUCTURE, not ranking quality. A hijacked reranker can still
    push policy to the bottom of the list - and if it falls outside FINAL_K it is
    effectively dropped. Phase 3's reserved policy slots are what defends that;
    this function defends the set.
F2. Non-integer or malformed JSON is handled upstream by pydantic. If that
    validation is ever relaxed, `safe_reorder` still coerces defensively.
"""


def validate_rank_order(order, length: int) -> list[int]:
    """Turn arbitrary model output into a valid 1-based permutation of 1..length.

    Deterministic and total: every possible input produces a valid permutation.
    There is no rejection path, because failing the request is exactly the denial
    of service D2 describes.

    Rules, in order:
      1. discard anything that is not an int (bools are not ints here - True
         would otherwise silently mean index 1)
      2. discard anything outside [1, length] - this is what kills D1 and D2,
         since 0 and negatives never reach a subscript
      3. drop repeats, keeping first occurrence - kills the duplicate half of D3
      4. append missing indices in ascending order - kills the omission half of
         D3, so a chunk can never be silently removed from the candidate set
    """
    seen, cleaned = set(), []
    for value in order or []:
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if not (1 <= value <= length):
            continue
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)

    cleaned.extend(i for i in range(1, length + 1) if i not in seen)
    return cleaned


def safe_reorder(chunks, order):
    """Apply a model-supplied order as a strict permutation of `chunks`."""
    if not chunks:
        return []
    validated = validate_rank_order(order, len(chunks))
    reordered = [chunks[i - 1] for i in validated]

    # The invariant this module exists to provide. Cheap, and it turns any future
    # regression in validate_rank_order into a crash rather than a silent
    # change to which documents reach the model.
    assert len(reordered) == len(chunks), "safe_reorder must return a permutation"
    return reordered
