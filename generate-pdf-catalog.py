#!/usr/bin/env python3
"""Generate pdfs-data.js from Internet Archive collection faisalPDF."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
PDF_METADATA_URL = "https://archive.org/metadata/faisalPDF"
PDF_DOWNLOAD_BASE = "https://archive.org/download/faisalPDF/"
PDF_DETAILS_URL = "https://archive.org/details/faisalPDF"


def norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def display_title(archive_path: str) -> str:
    name = Path(archive_path).name
    stem = Path(name).stem
    stem = stem.replace("_", " ")
    return re.sub(r"\s+", " ", stem).strip()


def archive_embed_path(path: str) -> str:
    return "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def fetch_pdfs() -> list[dict]:
    with urllib.request.urlopen(PDF_METADATA_URL, timeout=60) as resp:
        data = json.load(resp)

    entries = []
    for item in data.get("files", []):
        name = item.get("name", "")
        if not name.lower().endswith(".pdf"):
            continue
        if item.get("format") == "Metadata":
            continue
        size = int(item.get("size", 0))
        encoded = archive_embed_path(name)
        entries.append({
            "title": display_title(name),
            "archive": name,
            "size": size,
            "sizeLabel": format_size(size),
            "download": PDF_DOWNLOAD_BASE + urllib.parse.quote(name),
            "embed": f"https://archive.org/embed/faisalPDF/{encoded}#page/n1/mode/1up",
            "details": f"{PDF_DETAILS_URL}/{encoded}",
        })

    # Drop duplicate debunking letter (keep spaced filename version)
    best: dict[str, dict] = {}
    for entry in entries:
        key = norm(entry["title"])
        existing = best.get(key)
        if existing is None:
            best[key] = entry
            continue
        if " " in Path(entry["archive"]).name and "_" in Path(existing["archive"]).name:
            best[key] = entry

    pdfs = sorted(best.values(), key=lambda x: x["title"].lower())
    for index, pdf in enumerate(pdfs):
        pdf["id"] = index
    return pdfs


def write_search_pdfs(pdfs: list[dict]) -> None:
    entries = [
        {
            "type": "pdf",
            "id": pdf["id"],
            "title": pdf["title"],
            "sub": pdf.get("sizeLabel", ""),
            "href": f"pdfs.html?pdf={pdf['id']}",
        }
        for pdf in pdfs
    ]
    out = WEBSITE / "data" / "search-pdfs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
    print(f"Wrote {out} ({len(entries)} searchable PDFs)")


def main():
    pdfs = fetch_pdfs()
    out = WEBSITE / "pdfs-data.js"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-pdf-catalog.py to refresh */\n")
        handle.write(f'const PDFS_ARCHIVE_DETAILS = "{PDF_DETAILS_URL}";\n')
        handle.write(f'const PDFS_DOWNLOAD_BASE = "{PDF_DOWNLOAD_BASE}";\n\n')
        handle.write("const PDFS = ")
        json.dump(pdfs, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Wrote {out} ({len(pdfs)} PDFs)")
    write_search_pdfs(pdfs)


if __name__ == "__main__":
    main()