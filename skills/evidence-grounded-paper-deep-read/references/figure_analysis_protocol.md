# Figure And Table Analysis Protocol

Use this protocol for every major figure and table. The final report must integrate visuals into the task, motivation, method, or experiment logic; do not create a separate figure-reading section.

## Cropping Requirement

Use the best available figure asset in this order:

1. Publisher/source assets if provided separately by the user.
2. Complete embedded figure image extracted directly from the PDF.
3. A precise rendered crop from the PDF page.
4. A marked unresolved extraction limitation.

Full-page previews are only for inspection and bbox selection.

## Direct Extraction Requirement

Before cropping, inspect `figure_manifest.json` for `embedded_image` or `embedded_image_pypdf` items. These are PDF image objects extracted directly from the file. Prefer them only when visual inspection shows the object is the complete figure/table needed in the report.

Do not assume every embedded image object is a complete figure. In many papers, a figure is assembled from:

- multiple bitmap panels,
- vector lines and shapes,
- selectable text labels,
- overlaid annotations,
- logos or decorative images.

If the extracted object is only a subpanel, background bitmap, or missing labels, use rendered cropping instead.

Recommended workflow:

1. Render or inspect the page containing the visual.
2. Determine the bounding box around the figure/table, including all subpanels, legends, axes, labels, and internal annotations, while excluding unrelated page text when possible.
3. Run `scripts/crop_pdf_region_verified.py` with the page number, bbox, and a margin.
4. Inspect the generated manifest. If `verification.status` is `needs_review`, enlarge or shift the bbox and crop again.
5. Reference only the verified cropped image in the report using a relative path.
6. If exact cropping is impossible, mark the visual as unavailable or unresolved; do not present a full-page preview as if it were the figure.

Use file names such as:

```text
figure-001-overall-framework.png
table-002-main-results.png
```

## Integration Guidance

Place visuals where the reader needs them:

- Problem/task figures belong in the section explaining what the authors did.
- Motivation or gap diagrams belong in the section explaining why the authors did it.
- Architecture, algorithm, module, pipeline, and formula diagrams belong in the method section.
- Result tables, ablation tables, qualitative examples, and metric curves belong in the experiment section.

Introduce each visual with a sentence explaining why it appears there. After the image, continue the surrounding explanation. The report should read like one coherent analysis, not like a gallery.

## Figure Checklist

For each figure:

- Identify the figure number, caption, and page.
- Embed the cropped image if available.
- State which section of the paper it supports.
- Explain the visual structure from left to right or top to bottom.
- Explain arrows, colors, modules, axes, legends, and labels.
- Connect each visual component to the method or experiment text.
- State the main claim the figure supports.
- State what the figure does not prove.
- Add beginner notes for specialized notation.

## Table Checklist

For each table:

- Identify the table number, caption, and page.
- Explain rows, columns, metrics, and symbols.
- Identify the best result and whether higher/lower is better.
- Compare the proposed method with the strongest baseline.
- Explain whether improvements are large, small, consistent, or mixed.
- Check whether statistical significance is reported.
- Note missing settings, datasets, or unclear details.

## Captions And Nearby Text

Do not explain a figure from the image alone. Use:

- Caption.
- Paragraph before the figure.
- Paragraph after the figure.
- Section heading.
- Any later text that references the figure.

When captions and body text disagree, report the discrepancy.

## Extraction Failures

If an embedded figure cannot be extracted:

- Render the page as a page preview image.
- Use the page preview only to choose a crop region.
- Crop the visual with `scripts/crop_pdf_region.py`.
- If cropping still fails, mark the figure as `unresolved extraction limitation`.
- Explain any visibility limitations.

If no image can be produced, still include a text-only explanation from caption and body evidence.
