# Preserving Azure DI's output: gaps found by measurement

**Status:** proposal, not applied. **Author:** parsebench-forensic bake-off session, 2026-09-07.

Every claim here is `MEASURED` against Azure `prebuilt-layout`, API `2024-11-30`, SDK
`azure-ai-documentintelligence` 1.0.2, on a scan-heavy, form-heavy forensic corpus. Where a
figure comes from a small sample it says so. Nothing here is inferred from documentation alone.

The extraction path is sound in the ways that are hardest to get right — `as_dict()` is captured
whole, and `_apply_offsets_to_result` recurses so nested spans inside `pages[].lines`,
`words` and `selectionMarks` are offset correctly. The gaps below are all at the **request**
boundary and the **consumption** boundary, not in the stitching.

---

## 1. ⚠️ `features` is never requested, so `keyValuePairs` can never be populated

`routes/extraction.py:467` calls `begin_analyze_document` with **no `features` argument.**
`routes/extraction.py:164` then reads `result["keyValuePairs"]` — **a branch that cannot fire.**

Three add-ons are **free** and are all currently missing: `keyValuePairs`, `barcodes`,
`languages`.

⚠️ **This is the single highest-value gap, because `keyValuePairs` is the best value-binding
channel Azure has.** `MEASURED` on 37 expert-adjudicated cell-binding assertions:

| channel | bound | misbound |
|---|---:|---:|
| Azure `keyValuePairs` | **22 / 37** | **0** |
| Azure markdown | 11 / 37 | — |

Same request, same document: **the markdown binds half as many values.** A pipeline reading only
markdown is discarding the better channel and paying nothing extra for it.

```python
from azure.ai.documentintelligence.models import DocumentAnalysisFeature as F
features=[F.KEY_VALUE_PAIRS, F.BARCODES, F.LANGUAGES]   # all three free
```

⚠️ Do **not** add `OCR_HIGH_RESOLUTION` reflexively. It is a paid add-on at **+60%**, and the
docs scope it to *"small text from large-size documents, like engineering drawings… A1/A2/A3"*.
`MEASURED` on letter-size pages: no effect on checkbox state or character error, +1 binding
assertion (noise).

## 2. ⚠️ `selectionMarks` are never read — checkbox state is dropped entirely

Zero occurrences in `routes/`. They live in `pages[].selectionMarks` and survive stitching, but
nothing assigns them IDs or surfaces them, and `FilteredElement` has no field for them.

`MEASURED` over 18 pages: **314 selection marks, every one carrying a polygon, a `state`
(`selected`/`unselected`) and a confidence.** Against adjudicated truth: **17/18 pages exact,
314/314 marks found, 313/314 states correct.**

**Azure is the only parser measured that emits checkbox state as a first-class located element
rather than as a glyph in prose.** For form-heavy evidence this is often the answer the document
exists to record, and a markdown-only path reduces it to `☐`/`☒` characters whose association
with a label has to be re-derived by text proximity.

## 3. ⚠️ `pages[].lines` are dropped, and granularity is worth 37 points

IDs are assigned to paragraphs, tables, key-value pairs, lists, figures and formulas — **not to
lines or words.**

`MEASURED`, identical stored Azure output, scored through one scorer against the PDF's own text
layer:

| granularity | assignment | locatable | hit@0.5 | median IoU |
|---|---|---:|---:|---:|
| paragraph | nearest | 110 | 63% | 0.79 |
| **line** | **nearest** | **209** | **100%** | **0.91** |

**Granularity moves the result 37 points on the same bytes.** Paragraph-level regions are the
coarser, lossier view, and they are the only view this codebase keeps.

⚠️ **And there is a page class where lines are the ONLY safe reader.** On a psychometric profile
page, `MEASURED`:

- Azure returns **0 tables** for the page (and 1 table for the *neighbouring* page that was
  already safe) — a `tables` consumer reads absence where there is content;
- the values come back as **80 individually located lines**, clustering into exactly **three
  bands of 22** on a shared **0.250 in** column pitch;
- **worst column misalignment across the three bands: 0.0030 in — 1.2% of the pitch.**

That page's underlying structure binds **positionally**: one run of 22 names, then 22 raw scores,
then 22 derived scores, with nothing associating a name to a value but ordinal position in a
different run. **One dropped cell shifts every later value by one and all of them stay
plausible** — a wrong score attached to the wrong scale, with no error, no missing field and no
length mismatch a consumer would notice. Binding on **x-position** makes that failure impossible:
survivors keep their true coordinates, so a drop shows up as a gap in the grid rather than a
silent renumbering. **Without lines, that page cannot be read safely at all.**

## 4. ⚠️ `unit` is INCH, and nothing here reads it

Nothing in `routes/` references `unit`, `width` or `height`. Polygons are stored raw.

`MEASURED`: on PDF input Azure reports `unit: "inch"` — on **all 18 gold pages across both
strata**, including 10 full-page scans, and never mixed within a document. Page dimensions come
back as e.g. `8.5 x 11`.

⚠️ **Any consumer that assumes points or pixels is wrong by a factor of 72.** The only safe
denominator is Azure's own `pages[].width`/`height`, never the source PDF's — they are in
different units. **Store `unit` and the page dimensions alongside every polygon**, or normalise
to page fractions at extraction time and record that you did.

## 5. ⚠️ The stitch offset arithmetic and the index basis disagree

`stringIndexType` is never set, so the service defaults to **`textElements`** (grapheme
clusters). `stitch_analysis_results` computes `content_offset = len(stitched_result["content"])`
— **Python `len()`, which counts codepoints.**

The two coincide for ASCII and diverge on any combining mark, and diverge further on astral
characters. Every stitched batch after the first would carry spans that are silently a few units
off, in a way that is invisible on ordinary English text and appears only on the documents most
likely to matter.

**Fix, one line:** pass `string_index_type="unicodeCodePoint"` so the basis matches the
arithmetic already in the code. (`utf16CodeUnit` also works but then the arithmetic must change.)

⚠️ **A test corpus of ASCII fixtures cannot detect this.** A sibling project proved that by
mutating its offset conversion to the identity function and watching its whole fixture suite stay
green. If you add a regression test, it needs **one combining mark and one astral character**.

## 6. Preserve the rotated quad — Azure is the only parser that returns one

`MEASURED` on deliberately skewed input: Azure returned genuine **non-axis-aligned quadrilaterals
on 168/168 elements at 7°**, where another hosted parser squared every one of them on the same
pixels.

The current code stores `polygon` raw, which is correct and worth protecting. **Any downstream
conversion to `(x0, y0, x1, y1)` silently discards the rotation**, and on a skewed scan an
axis-aligned box around a rotated line can be substantially larger than the text it claims to
locate. If a rectangle is needed for an index, keep the quad as well.

## 7. `FilteredElement` has no geometry, so the `llm_ready` path drops the locator

`FilteredElement` carries content, role, page number, element type and table indices — **no
polygon, no bounding region, no page dimensions.**

That is defensible for an LLM prompt payload. It is **not** defensible as the only retained form,
because cite-and-highlight, checkbox association, table-cell binding and the line-grid reading in
§3 all need geometry. **Recommend making the geometry-preserving output the durable artefact and
the filtered view a projection of it** — never the other way round.

## 8. Operational findings for the batching path

- ⚠️ **A server-side `Code: Timeout` is real and is not a warnings payload.** `MEASURED`: it
  surfaces as an **SDK exception with an empty result** — not a `succeeded` result carrying
  `warnings`, and not a `failed` operation with `error.details[]`. `retries_used: 2`, total
  **383.7 s** across three attempts, `chars: 0`, no `AnalyzeResult` at all.
  *Caveat: observed on a single-page submission, which cannot distinguish whole-operation failure
  from per-page failure on a multi-page request.*
- **Input size provokes it, not page count.** The failing page was a **~26 MB** rasterised page;
  the same page as a native PDF took ~8 s, and re-rendered at 300 dpi JPEG (**0.73 MB**) it
  succeeded with no retries. A client-side size guard before submit is cheap insurance.
- **Longest successful single-page request: 26.8 s.** A poll wall-clock cap should allow well
  beyond that.
- `analyze_range` tasks are dispatched through `asyncio.gather` with **no concurrency limit**.
  `MEASURED`: **zero 429s, zero throttling** — but only over **97 pages**, which does not test a
  worker dispatching a large document at full width. Treat the absence of throttling as untested
  rather than as headroom, and note the SKU is not visible from the client.

## What NOT to change

- **Keep capturing `as_dict()` whole.** A curated capture on the sibling project dropped table
  `boundingRegions` and made Azure score zero on region labels while it was returning 46 tables
  with a polygon on every one. The bug looked exactly like a parser weakness.
- **Keep the recursive offset application.** It already handles nested spans correctly, which is
  the part most implementations get wrong.
- **Keep markdown as an output.** Just stop treating it as the only one: `<!-- PageBreak -->` and
  `<!-- PageFooter=... -->` carry structure worth parsing, and the markdown is a *lossy
  projection* of a response that contains strictly more.

## Suggested order

1. **§1 `features`** — one line, free, unlocks the best binding channel and a dead code branch.
2. **§5 `string_index_type`** — one line, prevents silent span corruption in every stitched doc.
3. **§2 selection marks** — the primary dimension for form evidence.
4. **§4 unit/page dimensions** — cheap, prevents a 72× error.
5. **§3 lines** — largest payload increase; the §3 page class is the argument for it.
6. **§8 size guard and concurrency cap** — before any high-volume deployment.
