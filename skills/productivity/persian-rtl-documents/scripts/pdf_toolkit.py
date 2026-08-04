#!/usr/bin/env python
"""pdf_toolkit.py — PDF, OCR, and Persian/RTL toolkit

Usage:
    from pdf_toolkit import *

    # Persian text rendering
    render_persian_image("سلام دنیا", "output.png")

    # OCR
    result = ocr_image("scan.png", lang="fas+eng")

    # PDF operations
    texts = pdf_extract_text("document.pdf")
    pdf_ocr_page("scanned.pdf", page_num=0, lang="fas+eng")
    pdf_create_with_persian("output.pdf", [{'text': 'متن فارسی'}])
"""
import os
import sys
from pathlib import Path

# ─── Configuration ───
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = r"C:\Users\netcon\playground\tessdata"
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

# ─── Imports ───
import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import cv2
import numpy as np
from bidi.algorithm import get_display
import arabic_reshaper

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ═══════════════════════════════════════════════════════════════
# Persian / RTL text helpers
# ═══════════════════════════════════════════════════════════════

def reshape_persian(text: str) -> str:
    """Reshape and reorder Persian/Arabic text for display."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def render_persian_image(text: str, output_path: str = "persian_text.png",
                         font_path: str = "C:/Windows/Fonts/tahoma.ttf",
                         font_size: int = 60, padding: int = 40,
                         bg_color="white", text_color="black",
                         width: int = 1200, height: int = 200) -> str:
    """Render Persian text to a clean image optimized for OCR.
    Uses reshape only (no get_display) for OCR compatibility."""
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    # Reshape for connected forms but do NOT use get_display()
    reshaped = arabic_reshaper.reshape(text)
    bbox = draw.textbbox((0, 0), reshaped, font=font)
    text_width = bbox[2] - bbox[0]
    x = width - padding - text_width
    y = (height - font_size) // 2
    draw.text((x, y), reshaped, font=font, fill=text_color)

    # Preprocess for OCR
    img_gray = img.convert('L')
    img_np = np.array(img_gray)
    _, img_binary = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    img_padded = cv2.copyMakeBorder(img_binary, 20, 20, 20, 20,
                                     cv2.BORDER_CONSTANT, value=255)
    cv2.imwrite(output_path, img_padded)
    return output_path


# ═══════════════════════════════════════════════════════════════
# OCR helpers
# ═══════════════════════════════════════════════════════════════

def ocr_image(image_path: str, lang: str = "fas+eng",
              preprocess: bool = True) -> str:
    """OCR an image file with Tesseract."""
    img = Image.open(image_path)
    if preprocess:
        img_gray = img.convert('L')
        img_np = np.array(img_gray)
        img_binary = cv2.adaptiveThreshold(
            img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2)
        img_denoised = cv2.medianBlur(img_binary, 3)
        img = Image.fromarray(img_denoised)
    config = f'--tessdata-dir {TESSDATA_DIR}'
    return pytesseract.image_to_string(img, lang=lang, config=config).strip()


def ocr_image_psm(image_path: str, lang: str = "fas+eng",
                  psm: int = 7, preprocess: bool = True) -> str:
    """OCR with specific PSM mode. Use psm=7 for single Persian lines."""
    img = Image.open(image_path)
    if preprocess:
        img_gray = img.convert('L')
        img_np = np.array(img_gray)
        _, img_binary = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img = Image.fromarray(img_binary)
    config = f'--tessdata-dir {TESSDATA_DIR} --psm {psm}'
    return pytesseract.image_to_string(img, lang=lang, config=config).strip()


# ═══════════════════════════════════════════════════════════════
# PDF helpers
# ═══════════════════════════════════════════════════════════════

def pdf_extract_text(pdf_path: str) -> dict:
    """Extract text from all pages of a PDF. Returns {page_num: text}."""
    results = {}
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        results[i] = page.get_text()
    doc.close()
    return results


def pdf_extract_images(pdf_path: str, output_dir: str = "pdf_images") -> list:
    """Extract all images from a PDF. Returns list of image file paths."""
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            path = os.path.join(output_dir, f"page{page_num+1}_img{img_idx+1}.{ext}")
            with open(path, "wb") as f:
                f.write(base_image["image"])
            image_paths.append(path)
    doc.close()
    return image_paths


def pdf_page_to_image(pdf_path: str, page_num: int = 0, dpi: int = 200) -> str:
    """Convert a PDF page to PNG for OCR."""
    doc = fitz.open(pdf_path)
    pix = doc[page_num].get_pixmap(dpi=dpi)
    output_path = f"page_{page_num+1}.png"
    pix.save(output_path)
    doc.close()
    return output_path


def pdf_ocr_page(pdf_path: str, page_num: int = 0,
                 lang: str = "fas+eng", dpi: int = 200) -> str:
    """OCR a specific page of a PDF."""
    img_path = pdf_page_to_image(pdf_path, page_num, dpi)
    return ocr_image(img_path, lang=lang)


def pdf_ocr_all(pdf_path: str, lang: str = "fas+eng", dpi: int = 200) -> dict:
    """OCR all pages. Returns {page_num: text}."""
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    doc.close()
    return {i: pdf_ocr_page(pdf_path, i, lang, dpi) for i in range(num_pages)}


def pdf_create_with_persian(output_path: str, pages: list) -> str:
    """Create PDF with Persian text.
    pages: list of dicts with 'text', optional 'font_size' (default 16), 'margin' (default 50).
    Uses Tahoma font for proper Arabic glyph rendering."""
    doc = fitz.open()
    font_file = "C:/Windows/Fonts/tahoma.ttf"
    for pc in pages:
        page = doc.new_page(width=595, height=842)
        rect = fitz.Rect(pc.get('margin', 50), pc.get('margin', 50),
                         595 - pc.get('margin', 50), 842 - pc.get('margin', 50))
        page.insert_textbox(rect, pc['text'], fontsize=pc.get('font_size', 16),
                            fontfile=font_file, fontname="tahoma",
                            align=fitz.TEXT_ALIGN_RIGHT, color=(0, 0, 0))
    doc.save(output_path)
    doc.close()
    return output_path


def get_available_languages() -> list:
    """List available Tesseract languages in local tessdata."""
    return [f.replace('.traineddata', '') for f in os.listdir(TESSDATA_DIR)
            if f.endswith('.traineddata')]


if __name__ == "__main__":
    print(f"Languages: {get_available_languages()}")
    print(f"Toolkit ready. Use functions: ocr_image, pdf_extract_text, etc.")
