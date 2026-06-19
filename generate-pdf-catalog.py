#!/usr/bin/env python3
"""Generate pdfs-data.js from Internet Archive collection faisalPDF."""
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
PDF_LOCAL_ROOT = WEBSITE.parent / "www"
PDF_THUMB_OUT = WEBSITE / "thumb" / "pdfs"
PDF_METADATA_URL = "https://archive.org/metadata/faisalPDF"
PDF_DOWNLOAD_BASE = "https://archive.org/download/faisalPDF/"
PDF_DETAILS_URL = "https://archive.org/details/faisalPDF"

PDF_CATEGORIES = [
    {"id": "quran", "label": "Quran & Tafsir", "order": 1},
    {"id": "aqeedah", "label": "Aqeedah & Refutations", "order": 2},
    {"id": "ummah", "label": "Ummah & Politics", "order": 3},
    {"id": "character", "label": "Character & Family", "order": 4},
    {"id": "general", "label": "General", "order": 5},
]

CATEGORY_BY_ID = {cat["id"]: cat for cat in PDF_CATEGORIES}


def norm(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def thumb_slug(archive: str) -> str:
    return hashlib.sha1(archive.encode("utf-8")).hexdigest()[:16]


def thumb_rel(archive: str) -> str:
    return f"thumb/pdfs/{thumb_slug(archive)}.jpg"


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
    organize_pdfs(pdfs)
    attach_thumbs(pdfs)
    return pdfs


def extract_part_number(title: str) -> int | None:
    title_l = title.lower()
    if re.search(r"part\s*ii\b", title_l):
        return 2
    if re.search(r"part\s*iii\b", title_l):
        return 3
    if re.search(r"part\s*iv\b", title_l):
        return 4
    match = re.search(r"part\s*(\d+)", title_l)
    if match:
        return int(match.group(1))
    return None


def classify_pdf(pdf: dict) -> None:
    title_l = pdf["title"].lower()
    archive_l = pdf["archive"].lower()

    if "science of quran" in title_l or "science_of_quran" in archive_l:
        pdf.update({
            "category": "quran",
            "categoryLabel": "Quran & Tafsir",
            "series": "Science Of Quran",
            "part": extract_part_number(pdf["title"]),
        })
        return

    if "challenges facing the muslim ummah" in title_l:
        pdf.update({
            "category": "ummah",
            "categoryLabel": "Ummah & Politics",
            "series": "Challenges Facing the Muslim Ummah",
            "part": extract_part_number(pdf["title"]) or 1,
        })
        return

    if title_l.startswith("refuting the lie"):
        part = 1 if "kufr doona kufr" in title_l else 2
        pdf.update({
            "category": "aqeedah",
            "categoryLabel": "Aqeedah & Refutations",
            "series": "Refuting The Lie",
            "part": part,
        })
        return

    assignments: dict[str, tuple[str, str, str | None, int | None]] = {
        "tafsir surah saff": ("quran", "Quran & Tafsir", None, None),
        "towards watering down the holy quran": ("quran", "Quran & Tafsir", None, None),
        "100 fabricated hadiths": ("aqeedah", "Aqeedah & Refutations", None, None),
        "debunking the letter of the wicked scholars": ("aqeedah", "Aqeedah & Refutations", None, None),
        "murjiya refutation": ("aqeedah", "Aqeedah & Refutations", None, None),
        "are you a takfiri": ("aqeedah", "Aqeedah & Refutations", None, None),
        "7 conditions of shahada": ("aqeedah", "Aqeedah & Refutations", None, None),
        "conditions of shahada": ("aqeedah", "Aqeedah & Refutations", None, None),
        "islam the religion of the future": ("aqeedah", "Aqeedah & Refutations", None, None),
        "islam under siege": ("ummah", "Ummah & Politics", None, None),
        "the obligation to establish the khilafah": ("ummah", "Ummah & Politics", None, None),
        "shariah vs man-made laws": ("ummah", "Ummah & Politics", None, None),
        "the evil rulers of the world": ("ummah", "Ummah & Politics", None, None),
        "among your wives and children": ("character", "Character & Family", None, None),
        "personality disorders": ("character", "Character & Family", None, None),
        "natural instincts": ("character", "Character & Family", None, None),
        "who are you": ("character", "Character & Family", None, None),
        "their hearts are alike": ("character", "Character & Family", None, None),
        "adam and shaitan": ("general", "General", None, None),
        "allah (swt) has honored bani adam": ("general", "General", None, None),
        "natural disasters": ("general", "General", None, None),
    }

    for key, (cat_id, cat_label, series, part) in assignments.items():
        if key in title_l or key.replace(" ", "_") in archive_l:
            pdf.update({
                "category": cat_id,
                "categoryLabel": cat_label,
            })
            if series:
                pdf["series"] = series
            if part is not None:
                pdf["part"] = part
            return

    pdf.update({
        "category": "general",
        "categoryLabel": "General",
    })


def pdf_sort_key(pdf: dict) -> tuple:
    category = CATEGORY_BY_ID.get(pdf.get("category", "general"), CATEGORY_BY_ID["general"])
    return (
        category["order"],
        0 if pdf.get("series") else 1,
        (pdf.get("series") or "").lower(),
        pdf.get("part") if pdf.get("part") is not None else 99,
        pdf["title"].lower(),
    )


def organize_pdfs(pdfs: list[dict]) -> None:
    for pdf in pdfs:
        classify_pdf(pdf)

    ordered = sorted(pdfs, key=pdf_sort_key)
    for index, pdf in enumerate(ordered):
        pdf["sortOrder"] = index
        pdf["id"] = index

    series_count = sum(1 for pdf in pdfs if pdf.get("series"))
    print(f"Organized {len(pdfs)} PDFs into {len(PDF_CATEGORIES)} categories ({series_count} in multi-part series)")


def has_pdftoppm() -> bool:
    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def extract_pdf_thumb(local_pdf: Path, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    prefix = dest.with_suffix("")
    if dest.exists():
        dest.unlink()
    cmd = [
        "pdftoppm",
        "-f", "1",
        "-l", "1",
        "-jpeg",
        "-r", "72",
        "-singlefile",
        str(local_pdf),
        str(prefix),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        return dest.exists() and dest.stat().st_size > 500
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        dest.unlink(missing_ok=True)
        return False


def ensure_local_pdf(pdf: dict) -> Path | None:
    local = PDF_LOCAL_ROOT / pdf["archive"]
    if local.is_file():
        return local

    cache_dir = WEBSITE / ".pdf-cache"
    cache_dir.mkdir(exist_ok=True)
    cache_name = pdf["archive"].replace("/", "__")
    cache = cache_dir / cache_name
    if cache.is_file() and cache.stat().st_size > 500:
        return cache

    try:
        with urllib.request.urlopen(pdf["download"], timeout=120) as resp:
            data = resp.read()
        if len(data) < 500:
            return None
        cache.write_bytes(data)
        return cache
    except OSError:
        return None


def attach_thumbs(pdfs: list[dict]) -> None:
    if not has_pdftoppm():
        print("pdftoppm not found — skipping PDF thumbnail generation")
        return

    created = 0
    for pdf in pdfs:
        local_pdf = ensure_local_pdf(pdf)
        if not local_pdf:
            continue
        rel = thumb_rel(pdf["archive"])
        thumb_path = WEBSITE / rel
        if thumb_path.exists() and thumb_path.stat().st_mtime >= local_pdf.stat().st_mtime:
            pdf["thumb"] = rel
            continue
        if extract_pdf_thumb(local_pdf, thumb_path):
            pdf["thumb"] = rel
            created += 1
    print(f"PDF thumbnails: {sum(1 for pdf in pdfs if pdf.get('thumb'))} ready ({created} regenerated)")


def write_search_pdfs(pdfs: list[dict]) -> None:
    entries = []
    for pdf in sorted(pdfs, key=lambda item: item.get("sortOrder", item["id"])):
        sub_parts = [pdf.get("categoryLabel", "")]
        if pdf.get("series") and pdf.get("part"):
            sub_parts.append(f"{pdf['series']} · Part {pdf['part']}")
        elif pdf.get("series"):
            sub_parts.append(pdf["series"])
        entry = {
            "type": "pdf",
            "id": pdf["id"],
            "title": pdf["title"],
            "sub": " · ".join(part for part in sub_parts if part),
            "href": f"pdfs.html?pdf={pdf['id']}",
        }
        if pdf.get("thumb"):
            entry["thumb"] = pdf["thumb"]
        entries.append(entry)
    out = WEBSITE / "data" / "search-pdfs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
    print(f"Wrote {out} ({len(entries)} searchable PDFs)")


def patch_search_index_pdfs(pdfs: list[dict]) -> None:
    search_path = WEBSITE / "search-index.js"
    if not search_path.is_file():
        return

    text = search_path.read_text(encoding="utf-8")
    match = re.search(r"const SEARCH_INDEX = (\[.*\]);", text, re.S)
    if not match:
        return

    existing = json.loads(match.group(1))
    pdf_entries = []
    for pdf in sorted(pdfs, key=lambda item: item.get("sortOrder", item["id"])):
        sub_parts = [pdf.get("categoryLabel", "")]
        if pdf.get("series") and pdf.get("part"):
            sub_parts.append(f"{pdf['series']} · Part {pdf['part']}")
        elif pdf.get("series"):
            sub_parts.append(pdf["series"])
        entry = {
            "type": "pdf",
            "id": pdf["id"],
            "title": pdf["title"],
            "sub": " · ".join(part for part in sub_parts if part),
            "href": f"pdfs.html?pdf={pdf['id']}",
        }
        if pdf.get("thumb"):
            entry["thumb"] = pdf["thumb"]
        pdf_entries.append(entry)

    merged = [item for item in existing if item.get("type") != "pdf"] + pdf_entries
    with open(search_path, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-catalog.py, generate-media-catalog.py, generate-pdf-catalog.py */\n")
        handle.write("const SEARCH_INDEX = ")
        json.dump(merged, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Patched {search_path} ({len(pdf_entries)} PDF search entries)")


def main():
    pdfs = fetch_pdfs()
    out = WEBSITE / "pdfs-data.js"
    display_pdfs = sorted(pdfs, key=lambda pdf: pdf.get("sortOrder", pdf["id"]))
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-pdf-catalog.py to refresh */\n")
        handle.write(f'const PDFS_ARCHIVE_DETAILS = "{PDF_DETAILS_URL}";\n')
        handle.write(f'const PDFS_DOWNLOAD_BASE = "{PDF_DOWNLOAD_BASE}";\n\n')
        handle.write("const PDF_CATEGORIES = ")
        json.dump(PDF_CATEGORIES, handle, ensure_ascii=False, indent=2)
        handle.write(";\n\n")
        handle.write("const PDFS = ")
        json.dump(display_pdfs, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Wrote {out} ({len(pdfs)} PDFs)")
    write_search_pdfs(pdfs)
    patch_search_index_pdfs(pdfs)


if __name__ == "__main__":
    main()