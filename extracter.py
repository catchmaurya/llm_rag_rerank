#!/usr/bin/env python3
"""
Universal-ish extractor -> TXT

Converts many common document types to plain text:
- .txt
- .md
- .html / .htm
- .pdf
- .docx
- .pptx
- .csv
- .xlsx
- .json
- .rtf (best-effort)
- Folders (recursively walk)

Notes:
- For scanned PDFs or images, OCR is optional: install Tesseract and pytesseract.
- For Confluence/Quip: export to DOCX/PDF/HTML first, then run this script.

Install (minimal working set):
    pip install pypdf python-docx python-pptx beautifulsoup4 html5lib markdown openpyxl chardet

Optional:
    pip install pandas
    pip install pytesseract pillow

Usage:
    python extractor.py /path/to/file_or_folder --out corpus_text
"""

import os, sys, re, json, traceback, pathlib
from dataclasses import dataclass
from typing import List

def _try_import(name):
    try:
        return __import__(name)
    except Exception:
        return None

pypdf = _try_import("pypdf")
docx = _try_import("docx")      # python-docx
pptx = _try_import("pptx")      # python-pptx
bs4 = _try_import("bs4")
markdown = _try_import("markdown")
openpyxl = _try_import("openpyxl")
chardet = _try_import("chardet")
pytesseract = _try_import("pytesseract")
PIL = _try_import("PIL")

@dataclass
class ExtractResult:
    text: str
    warnings: List[str]

def detect_encoding(binary: bytes) -> str:
    if chardet:
        try:
            res = chardet.detect(binary)
            return res.get("encoding") or "utf-8"
        except Exception:
            return "utf-8"
    return "utf-8"

def read_text_file(fp: str) -> ExtractResult:
    with open(fp, "rb") as f:
        data = f.read()
    enc = detect_encoding(data)
    return ExtractResult(text=data.decode(enc, errors="ignore"), warnings=[])

def read_pdf_file(fp: str) -> ExtractResult:
    if not pypdf:
        return ExtractResult("", ["pypdf not installed"])
    try:
        reader = pypdf.PdfReader(fp)
        parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(parts)
        warn = [] if text.strip() else ["No text extracted; maybe scanned (needs OCR)"]
        return ExtractResult(text, warn)
    except Exception as e:
        return ExtractResult("", [f"PDF error: {e}"])

def read_docx_file(fp: str) -> ExtractResult:
    if not docx: return ExtractResult("", ["python-docx not installed"])
    try:
        d = docx.Document(fp)
        lines = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                lines.append("\t".join(c.text for c in row.cells))
        return ExtractResult("\n".join(lines), [])
    except Exception as e:
        return ExtractResult("", [f"DOCX error: {e}"])

def read_pptx_file(fp: str) -> ExtractResult:
    if not pptx: return ExtractResult("", ["python-pptx not installed"])
    try:
        prs = pptx.Presentation(fp)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"): texts.append(shape.text)
        return ExtractResult("\n".join(texts), [])
    except Exception as e:
        return ExtractResult("", [f"PPTX error: {e}"])

def read_md_file(fp: str) -> ExtractResult:
    with open(fp, "r", encoding="utf-8", errors="ignore") as f: raw = f.read()
    if markdown and bs4:
        try:
            html = markdown.markdown(raw)
            soup = bs4.BeautifulSoup(html, "html5lib")
            return ExtractResult(soup.get_text("\n"), [])
        except Exception as e:
            return ExtractResult(raw, [f"MD->HTML failed {e}"])
    return ExtractResult(raw, ["markdown/bs4 not installed"])

def read_html_file(fp: str) -> ExtractResult:
    with open(fp, "r", encoding="utf-8", errors="ignore") as f: raw = f.read()
    if bs4:
        soup = bs4.BeautifulSoup(raw, "html5lib")
        for tag in soup(["script","style","noscript"]): tag.decompose()
        return ExtractResult(soup.get_text("\n"), [])
    return ExtractResult(raw, ["bs4 not installed"])

def read_xlsx_file(fp: str) -> ExtractResult:
    if not openpyxl: return ExtractResult("", ["openpyxl not installed"])
    wb = openpyxl.load_workbook(fp, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"# Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            parts.append("\t".join(str(c) if c else "" for c in row))
    return ExtractResult("\n".join(parts), [])

def read_json_file(fp: str) -> ExtractResult:
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            obj = json.load(f)
        return ExtractResult(json.dumps(obj, indent=2, ensure_ascii=False), [])
    except Exception as e:
        return ExtractResult("", [f"JSON error: {e}"])

def extract_to_text(fp: str) -> ExtractResult:
    ext = pathlib.Path(fp).suffix.lower()
    if ext in [".txt", ".log"]: return read_text_file(fp)
    if ext in [".md", ".markdown"]: return read_md_file(fp)
    if ext in [".html", ".htm"]: return read_html_file(fp)
    if ext == ".pdf": return read_pdf_file(fp)
    if ext == ".docx": return read_docx_file(fp)
    if ext == ".pptx": return read_pptx_file(fp)
    if ext == ".xlsx": return read_xlsx_file(fp)
    if ext == ".json": return read_json_file(fp)
    return read_text_file(fp)  # fallback

def save_txt(out_root: str, in_root: str, file_path: str, result: ExtractResult):
    rel = os.path.relpath(file_path, start=in_root)
    rel_noext = os.path.splitext(rel)[0]
    out_path = os.path.join(out_root, rel_noext + ".txt")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.text)
    return out_path

def walk_and_extract(input_path: str, out_root: str):
    stats = {"ok":0,"fail":0,"files":[]}
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for name in files:
                fp = os.path.join(root,name)
                try:
                    res = extract_to_text(fp)
                    save_txt(out_root,input_path,fp,res)
                    stats["ok"]+=1
                except Exception as e:
                    stats["fail"]+=1
                    stats["files"].append({"in":fp,"error":str(e)})
    else:
        res = extract_to_text(input_path)
        save_txt(out_root, os.path.dirname(input_path) or ".", input_path, res)
        stats["ok"]+=1
    return stats

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("path",help="file or folder")
    ap.add_argument("--out",default="corpus_text")
    args=ap.parse_args()
    os.makedirs(args.out,exist_ok=True)
    s=walk_and_extract(args.path,args.out)
    print("Done:",s)

