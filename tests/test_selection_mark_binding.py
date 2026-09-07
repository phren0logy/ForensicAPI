"""Selection marks must reach a consumer and must bind to their label.

⚠️ This file exists because the first version of the marks change was INERT. Ids were assigned
and nothing downstream read them: `extract_elements_from_azure_di` had marks in neither its
page-level nor its document-level list, so the filtered output was identical before and after.
The detection rule is the sibling project's: run it both ways and diff. These tests are that
diff, made permanent.
"""
import pytest

from routes.extraction import add_ids_to_elements, bind_selection_marks
from routes.filtering import extract_elements_from_azure_di


def _result():
    """Azure's real shapes: marks carry `span` (singular OBJECT); paragraphs carry `spans` (LIST)."""
    return {
        "content": "Is the child safe? :unselected: Yes :selected: No",
        "paragraphs": [
            {"content": "Is the child safe? :unselected: Yes", "spans": [{"offset": 0, "length": 35}]},
            {"content": ":selected: No", "spans": [{"offset": 36, "length": 13}]},
        ],
        "pages": [
            {
                "pageNumber": 1, "unit": "inch", "width": 8.5, "height": 11,
                "selectionMarks": [
                    {"state": "unselected", "confidence": 0.9,
                     "span": {"offset": 19, "length": 1}, "polygon": [1, 1, 2, 1, 2, 2, 1, 2]},
                    {"state": "selected", "confidence": 0.99,
                     "span": {"offset": 36, "length": 1}, "polygon": [3, 1, 4, 1, 4, 2, 3, 2]},
                ],
                "lines": [{"content": "Is the child safe?", "span": {"offset": 0, "length": 18},
                           "polygon": [0, 0, 1, 0, 1, 1, 0, 1]}],
            }
        ],
    }


def test_marks_get_ids_from_their_singular_span():
    """⚠️ Marks use `span`, paragraphs use `spans`. Reading only the plural form yields None."""
    r = add_ids_to_elements(_result())
    marks = r["pages"][0]["selectionMarks"]
    assert all("_id" in m for m in marks)
    assert len({m["_id"] for m in marks}) == 2, "ids must distinguish two marks on one page"


def test_page_geometry_is_recorded():
    r = add_ids_to_elements(_result())
    geom = r["pages"][0]["_geometry"]
    assert geom["unit"] == "inch", "the unit must travel with the coordinates, not be assumed"
    assert (geom["width"], geom["height"]) == (8.5, 11)


def test_every_mark_binds_to_the_paragraph_containing_it():
    r = bind_selection_marks(add_ids_to_elements(_result()))
    assert r["_selection_mark_binding"] == {"bound": 2, "total": 2}
    marks = r["pages"][0]["selectionMarks"]
    assert marks[0]["_bound_to_text"].startswith("Is the child safe?")
    assert marks[1]["_bound_to_text"] == ":selected: No"


def test_a_mark_outside_every_span_is_left_unbound_not_guessed():
    """⚠️ A mark bound to the WRONG label is worse than one left unbound."""
    r = _result()
    r["pages"][0]["selectionMarks"][0]["span"] = {"offset": 9999, "length": 1}
    out = bind_selection_marks(add_ids_to_elements(r))
    assert out["_selection_mark_binding"]["bound"] == 1
    assert "_bound_to" not in out["pages"][0]["selectionMarks"][0]


def test_marks_reach_the_filtered_view():
    """The regression that motivated this file: ids assigned, nothing surfaced."""
    r = bind_selection_marks(add_ids_to_elements(_result()))
    kinds = [e.get("elementType") for e in extract_elements_from_azure_di(r)]
    assert kinds.count("selectionMark") == 2, (
        "selection marks must appear in the filtered output; if this fails the extraction "
        "change is inert again"
    )


@pytest.mark.parametrize("shape", ["span", "spans"])
def test_span_helper_tolerates_both_azure_shapes(shape):
    from routes.extraction import _element_span

    elem = {"span": {"offset": 5, "length": 2}} if shape == "span" else {"spans": [{"offset": 5, "length": 2}]}
    assert _element_span(elem)["offset"] == 5
