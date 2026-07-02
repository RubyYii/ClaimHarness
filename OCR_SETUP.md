# OCR Setup Guide

OCR is optional. ClaimHarness and ProblemBridge can run without it. Install OCR only when you want to read scanned PDFs or image files in the Document Intake page.

![OCR setup flow](docs/figures/ocr-setup-flow.svg)

## What OCR Adds

Without OCR, Document Intake can already read text-based PDF, Word, Markdown, TXT, CSV, HTML, public static webpages, and basic document annotations.

With OCR enabled, Document Intake can also try to extract rough text from:

- scanned PDFs
- `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, and `.bmp` files

OCR does not understand images, charts, figures, handwriting intent, or professional meaning. It only turns visible printed text into rough editable text.

## Install the Python OCR Extra

From the repository root:

```bash
pip install -e ".[ui,ocr]"
```

If you already installed the project, running the same command again is fine. It adds the optional Python packages used by OCR:

- `pytesseract`
- `pdf2image`
- `Pillow`

![OCR install stack](docs/figures/ocr-install-stack.svg)

## Install System OCR Tools

The Python packages are not enough by themselves. OCR also needs system tools.

### Windows

1. Install Tesseract OCR from the UB-Mannheim Windows installer:
   <https://github.com/UB-Mannheim/tesseract/wiki>

2. During installation, keep the default folder when possible:

```text
C:\Program Files\Tesseract-OCR
```

3. Make sure this folder is on the Windows `PATH`.

4. For scanned PDF OCR, install Poppler for Windows and add its `bin` folder to `PATH`.
   The `pdf2image` project links to the current Windows Poppler package:
   <https://pdf2image.readthedocs.io/en/latest/installation.html#installing-poppler>

5. Reopen PowerShell or restart the local web app.

### macOS

If Homebrew is installed:

```bash
brew install tesseract poppler
```

Then reinstall or update the Python OCR extra:

```bash
pip install -e ".[ui,ocr]"
```

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install tesseract-ocr poppler-utils
pip install -e ".[ui,ocr]"
```

For Chinese scans, also install Simplified Chinese language data:

```bash
sudo apt install tesseract-ocr-chi-sim
```

## Chinese OCR

For Chinese scanned documents, Tesseract needs the `chi_sim` language data. Check it with:

```bash
tesseract --list-langs
```

Look for:

```text
eng
chi_sim
```

If `chi_sim` is missing:

- Windows: rerun the UB-Mannheim installer and include Chinese language data, or copy `chi_sim.traineddata` into the `tessdata` folder.
- macOS: use Homebrew Tesseract language packages if available, or install the traineddata file manually into Tesseract's `tessdata` folder.
- Ubuntu / Debian: run `sudo apt install tesseract-ocr-chi-sim`.

## Check Installation

Open a new terminal after installation and run:

```bash
tesseract --version
pdftoppm -h
tesseract --list-langs
```

Expected:

- `tesseract --version` prints a version number.
- `pdftoppm -h` prints Poppler help text.
- `tesseract --list-langs` includes `eng`; include `chi_sim` for Chinese scans.

![OCR check result](docs/figures/ocr-check-result.svg)

## Use OCR in the Local App

1. Start the local UI:

```bash
streamlit run apps/problem_bridge_wizard.py
```

2. Open **Document intake**.
3. Upload a scanned PDF or image file.
4. Turn on **Enable optional OCR for images and image-only PDFs**.
5. Click **Generate document intake package**.

The extracted OCR text appears in:

- `extracted_text.md`
- `problem_seed.md`
- the downloadable output zip

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `tesseract` is not recognized | Tesseract is not installed or not on `PATH` | Install Tesseract, add it to `PATH`, then reopen terminal/app |
| `pdftoppm` is not recognized | Poppler is missing or not on `PATH` | Install Poppler and add `bin` to `PATH` |
| English works but Chinese is poor | `chi_sim` language data is missing | Install `chi_sim` traineddata |
| OCR returns messy text | Scan quality is low or layout is complex | Use clearer scans, crop margins, or treat OCR as rough intake only |
| OCR option is off | OCR is disabled by default | Enable optional OCR in Document Intake |

## Safety Boundary

OCR is only a text extraction aid. It does not verify claims, interpret charts, identify clinical meaning, or replace professional review. Always review extracted text before using it for ProblemBridge or ClaimHarness.

## Sources

- Tesseract installation documentation: <https://tesseract-ocr.github.io/tessdoc/Installation.html>
- UB-Mannheim Windows installer: <https://github.com/UB-Mannheim/tesseract/wiki>
- pdf2image Poppler installation notes: <https://pdf2image.readthedocs.io/en/latest/installation.html>
- Homebrew: <https://brew.sh/>
