# v0.3.3 PDF and Web Intake Design

## Purpose

Extend the Document Intake Layer so non-AI users can bring in common source types before question discovery:

- text-based PDFs with basic annotation signals
- saved HTML files or public static webpages
- scanned PDFs or images when optional local OCR is explicitly enabled

The goal is not to build browser automation, web search, or visual understanding. The goal is to preserve more user-provided context and attention signals so ProblemBridge can ask better follow-up questions.

## Scope

### PDF intake

Document intake will keep the existing text extraction path for text-based PDFs and add a best-effort annotation extraction path.

It should capture:

- PDF highlight annotations when available
- PDF text/comment annotations when available
- page numbers for annotation records when available
- annotation text, color, and nearby extracted text when available

It should write annotation records into the existing annotation outputs:

- `annotation_map.json`
- `comment_threads.md`
- `priority_marks.md`
- `source_manifest.json` via `annotation_count`
- `problem_seed.md` via extracted annotation signals

PDF annotation extraction is advisory. If a PDF parser cannot expose annotations, intake should keep extracting text and add a warning instead of failing the whole package.

### HTML and webpage intake

Document intake will support:

- uploaded `.html` and `.htm` files
- a public URL field in the Streamlit workbench

For HTML sources, intake should extract:

- page title
- headings
- paragraph/list text
- simple table rows
- links as a structured table

For URL sources, intake should fetch only a public static page over HTTP(S), apply the same HTML extraction path, and record the source URL in the manifest.

### Optional OCR intake

OCR is optional and disabled by default. If enabled, document intake should attempt OCR only when normal text extraction returns no text or when the uploaded file is an image.

OCR should support:

- image files such as `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, and `.bmp`
- scanned or image-only PDFs when the local OCR stack is available

OCR should not require an API key. The default runtime may not have OCR installed. Missing OCR dependencies or missing system OCR binaries should produce a clear warning instead of failing the upload.

## Out of Scope

This version will not support:

- OCR as a required dependency
- guaranteed scanned PDF extraction on machines without a local OCR stack
- image or figure interpretation
- PDF embedded image interpretation
- PDF handwritten markup recognition
- JavaScript-rendered webpage execution
- login-required webpages
- crawling multiple pages from a site
- automatic web search
- bypassing robots, paywalls, or access controls

## Data Model

Reuse `DocumentExtraction` and `AnnotationMark`.

Add only minimal fields if needed:

- `source_url` for URL-backed HTML extraction
- `page_number` for PDF annotations
- OCR status can be stored in extraction warnings and manifest metadata

If adding fields would cause too much churn, page and URL can be stored in `AnnotationMark.context` and manifest metadata for this version.

## Output Behavior

Existing output files stay stable:

- `extracted_text.md`
- `extracted_tables/`
- `annotation_map.json`
- `highlighted_spans.csv`
- `comment_threads.md`
- `priority_marks.md`
- `source_manifest.json`
- `extraction_warnings.md`
- `problem_seed.md`

HTML links should be exported as a CSV table, for example `extracted_tables/<source>_links.csv`, with columns:

- `text`
- `url`

HTML tables should continue using `ExtractedTable`.

## UI Behavior

The Streamlit Document intake page should:

- accept `.html` and `.htm` uploads
- accept image uploads for optional OCR
- include a URL input area for one or more public webpages
- explain that URL intake works for public static pages only
- include an "Enable optional OCR" control
- show URL and HTML extraction warnings in the existing warnings panel
- show annotation and link outputs in the existing "All intake files" area

The UI must not imply that the system understands images, interprets figures, executes websites, or reads private/login-only pages.

## Error Handling

PDF annotation extraction:

- if annotations are missing, continue with no annotation records
- if annotation parsing fails, keep PDF text extraction and add an extraction warning
- if PDF text extraction fails, preserve the current warning behavior

URL extraction:

- reject non-HTTP(S) URLs
- timeout quickly
- record HTTP or parsing failures as extraction warnings
- do not retry or crawl

OCR extraction:

- if OCR is disabled, image files should return a warning explaining how to enable optional OCR
- if OCR is enabled but dependencies are missing, return a warning explaining that optional OCR is unavailable locally
- if OCR runs but returns no text, return a warning that no OCR text was extracted
- if OCR succeeds, store the extracted text in `extracted_text.md`

HTML extraction:

- tolerate malformed HTML
- skip scripts, styles, navigation-heavy boilerplate where simple local parsing allows
- keep useful raw text if structured extraction is incomplete

## Testing

Add tests for:

- PDF annotation records exported into `annotation_map.json`
- PDF annotation signals included in `problem_seed.md`
- optional OCR engine used for image files when enabled
- optional OCR engine used for image-only PDFs when normal PDF text extraction returns no text
- image upload without OCR returns a clear warning
- `.html` extraction of title, headings, paragraphs, links, and simple tables
- URL intake rejects non-HTTP(S) URLs
- URL intake can parse a mocked local HTTP response without external network
- UI/docs mention `.html`, URL intake, PDF annotations, and static-page boundaries

Full verification remains:

```bash
.venv\Scripts\python.exe -m pytest
git diff --check
```
