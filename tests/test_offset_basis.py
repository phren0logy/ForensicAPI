"""The stitch offset arithmetic and the service's string index basis must agree.

⚠️ This file exists because the rest of the fixture corpus CANNOT detect this class of bug.
Every stored fixture is effectively ASCII, and on ASCII the three candidate index bases --
grapheme clusters (`textElements`, the SERVICE DEFAULT), Unicode codepoints (what Python's
`len()` counts), and UTF-16 code units -- all give the same number. A sibling project proved
this by mutating its offset conversion to the identity function and watching its whole fixture
suite stay green.

`stitch_analysis_results` computes `content_offset = len(stitched_result["content"])`, which is
CODEPOINTS. So the request must pin `stringIndexType` to `unicodeCodePoint`, or every batch
after the first carries silently mis-offset spans -- invisible on English prose and wrong on
exactly the documents most likely to matter.
"""
import ast
import pathlib

import pytest

from routes.extraction import stitch_analysis_results

SRC = pathlib.Path(__file__).resolve().parents[1] / "routes" / "extraction.py"

# One combining mark (e + U+0301) and one astral character (U+1D400). On this string the three
# bases disagree: 6 grapheme clusters, 7 codepoints, 8 UTF-16 code units.
TRICKY = "éx\U0001D400y"


def _batch(content, offset):
    return {
        "content": content,
        "pages": [{"pageNumber": 1, "spans": [{"offset": offset, "length": len(content)}]}],
        "paragraphs": [{"content": content, "spans": [{"offset": offset, "length": len(content)}]}],
    }


def test_the_three_bases_actually_disagree_on_this_fixture():
    """Guard the guard: if this ever passes trivially, the fixture has lost its teeth."""
    graphemes = 4
    codepoints = len(TRICKY)
    utf16 = len(TRICKY.encode("utf-16-le")) // 2
    assert codepoints == 5
    assert utf16 == 6
    assert len({graphemes, codepoints, utf16}) == 3, "fixture no longer discriminates bases"


def test_request_pins_the_index_basis_to_match_python_len():
    """The analyze call must set string_index_type, and to the codepoint basis specifically.

    Asserted against the source rather than by making a live call, so it runs in CI with no
    credentials and fails loudly if someone removes the argument later.
    """
    tree = ast.parse(SRC.read_text())
    found = [
        kw
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "string_index_type"
    ]
    assert found, (
        "begin_analyze_document must pass string_index_type; the service default is "
        "textElements (graphemes) while stitching adds Python len() (codepoints)"
    )
    src = ast.unparse(found[0].value)
    assert "UNICODE_CODE_POINT" in src or "unicodeCodePoint" in src, (
        f"string_index_type is {src!r}; stitching adds Python len(), which counts codepoints"
    )


def test_second_batch_offsets_are_shifted_by_codepoint_length():
    """A batch stitched after non-ASCII content must be offset by codepoints, not bytes/UTF-16."""
    first = _batch(TRICKY, 0)
    second = _batch("plain", 0)
    stitched = stitch_analysis_results(first, second)

    assert stitched["content"] == TRICKY + "plain"
    offsets = [p["spans"][0]["offset"] for p in stitched["paragraphs"]]
    assert offsets[0] == 0
    assert offsets[1] == len(TRICKY), (
        f"second batch offset {offsets[1]} should be {len(TRICKY)} codepoints; "
        f"{len(TRICKY.encode('utf-16-le')) // 2} would mean a UTF-16 basis"
    )
    # And the offset must index the concatenated content correctly.
    o = offsets[1]
    assert stitched["content"][o : o + 5] == "plain"


@pytest.mark.parametrize("payload", ["é", "\U0001D400", "é\U0001D400"])
def test_span_still_points_at_its_own_text_after_stitching(payload):
    stitched = stitch_analysis_results(_batch(payload, 0), _batch("TAIL", 0))
    o = stitched["paragraphs"][1]["spans"][0]["offset"]
    assert stitched["content"][o : o + 4] == "TAIL"
