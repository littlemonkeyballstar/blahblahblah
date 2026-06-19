#!/usr/bin/env python3
"""Generate videos-data.js and clips-data.js from Internet Archive + local thumbs."""
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent
VIDEO_SRC = WEBSITE.parent / "www" / "Sheikh Faisal Video Lectures"
VIDEO_THUMB_OUT = WEBSITE / "thumb" / "videos"
VIDEOS_ARCHIVE = "https://archive.org/metadata/FaisalVideos"
CLIPS_ARCHIVE = "https://archive.org/metadata/the-creed-of-the-shia"
CLIPS_ARCHIVE_BASE = "https://archive.org/download/the-creed-of-the-shia/"
BLOCKED = {"__ia_thumb.jpg", "__ia_thumb.png"}

# Full-length videos hosted on the clips IA item but listed under Video Lectures.
PROMOTED_VIDEOS_FROM_CLIPS = [
    {
        "file": "The Creed Of the shia .mp4",
        "title": "The creed of the Shia",
    },
]

# Lectures to hide from the public video library
EXCLUDED_VIDEOS = {
    "02.Sheikh Abdullah Faisal - Unity The Way Forward.mp4",
    "03.Sheikh Abdullah Faisal - Them versus Us.mp4",
    "04.Sheikh Abdullah Faisal - The Muslim Home.mp4",
    "05.Sheikh Abdullah Faisal - The Jinn.mp4",
    "06.Sheikh Abdullah Faisal - The Devil's Deception of The Shia.mp4",
    "07.Sheikh Abdullah Faisal - The Devil's Deception of The Saudi Salafis.mp4",
    "08.Sheikh Abdullah Faisal - The Devil's Deception of The Qadiani.mp4",
    "09.Sheikh Abdullah Faisal - The Devil's Deception of The Murji.mp4",
    "10.Sheikh Abdullah Faisal - Tawba.mp4",
    "11.Sheikh Abdullah Faisal - Signs Before The Day of Judgement.mp4",
    "12.Sheikh Abdullah Faisal - Natural Instincts.mp4",
    "13.Sheikh Abdullah Faisal - Muslim Character.mp4",
    "14.Sheikh Abdullah Faisal - Love and Hate for Allah's Sake.mp4",
    "15.Sheikh Abdullah Faisal - Ideological Warfare.mp4",
    "16.Sheikh Abdullah Faisal - Human Rights.mp4",
    "17.Sheikh Abdullah Faisal - Democracy   The Greatest Shirk.mp4",
    "18.Sheikh Abdullah Faisal - Cancers in the Body of The Ummah.mp4",
    "19.Sheikh Abdullah Faisal   Al Isra Wal Mira'aj.mp4",
}


def norm(text: str) -> str:
    """Normalize title/filename for matching (safe for titles like '02.Christianity…')."""
    text = text.lower().strip()
    text = re.sub(r"\.(mp4|m4v|webm|jpg|jpeg|png|webp)$", "", text, flags=re.I)
    text = re.sub(r"\s*\(\d+\)$", "", text)
    text = re.sub(r"\s*_thumb$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_video_number_prefix(stem: str) -> str:
    """02.Title, 03.Title, 08.Title, or 06.35 Title → drop leading episode numbers."""
    stem = re.sub(r"^\d+\.\d+\s+", "", stem)
    stem = re.sub(r"^\d+\.", "", stem)
    return stem.strip()


def display_video_title(filename: str) -> str:
    return strip_video_number_prefix(Path(filename).stem)


def has_video_number_prefix(stem: str) -> bool:
    return bool(re.match(r"^\d+\.", stem))


def dedupe_videos_by_title(videos: list[dict]) -> list[dict]:
    """Keep one entry per display title; prefer files without a numeric prefix."""
    best: dict[str, dict] = {}
    for video in videos:
        key = norm(video["title"])
        existing = best.get(key)
        if existing is None:
            best[key] = video
            continue
        new_prefixed = has_video_number_prefix(Path(video["file"]).stem)
        old_prefixed = has_video_number_prefix(Path(existing["file"]).stem)
        if old_prefixed and not new_prefixed:
            best[key] = video
    return list(best.values())


def clean_clip_title(title: str) -> str:
    """Turn raw IA filenames into readable display titles."""
    title = title.replace("_", " ")
    title = re.sub(r"#\w+", "", title)
    title = re.sub(r"\s+-\s*Trim\s*$", "", title, flags=re.I)
    title = re.sub(r"\s*\(\d+\)\s*$", "", title)
    # YouTube-style ids (11 chars with at least one digit — avoids stripping words like "journalists")
    title = re.sub(r"\s+(?=\S{11}$)\S*\d\S*\s*$", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


# Clips to hide from the public clips library (normalized stems / archive names)
EXCLUDED_CLIP_NORMS = {
    norm("awdfgg"),
    norm("recpect to a dead person"),
    # Old placeholder names superseded by renamed IA uploads
    norm("0426 (1)"),
    norm("0504"),
    norm("0530 (2)"),
    norm("0601 (1)"),
    norm("0604 (1)"),
    norm("short"),
    norm("video_2026-05-17_13-25-14"),
    norm("video_2026-05-17_13-27-53"),
    norm("video_2026-05-17_13-30-00"),
    norm("video_2026-05-17_13-32-38"),
    norm("video_2026-05-17_13-33-53"),
    # Duplicate of renamed upload
    norm("comfort in the truth"),
    norm("alwaraalbara"),
    norm("The Creed Of the shia "),
}

# Polished display title for every clip (keyed by normalized IA filename stem)
_CLIP_TITLES_RAW = [
    ("0510", "Refusing to takfir Mushrikeen (polytheists) — Shaykh Abdullah Faisal"),
    ("2 They Will Fight You Until You Leave Islam", "They will fight you until you leave Islam"),
    ("A Controversial Ruling  Seeking Help from Non(1)", "A controversial ruling: seeking help from non-Muslims"),
    ("A kaffir has no protecter!", "A kafir has no protector!"),
    (
        "All the kaffirs have their own brand in islam! - Shaykh Abdullah Faisal",
        "All the kuffar have their own brand in Islam — Shaykh Abdullah Faisal",
    ),
    ("Allah is sufficient to take revange", "Allah is sufficient to take revenge against them"),
    ("Cure to scitzo", "Cure for schizophrenia"),
    (
        "DO NOT TAKE MY ENEMY AS YOUR FRIENDby Shaykh Abdu",
        "Do not take my enemy as your friend — Shaykh Abdullah Faisal",
    ),
    (
        "DONT_KEEP_ISLAM_IN_THE_FOUR_CORNERS_OF_THE_MASJID_#foryoupage_#fyp",
        "Don't keep Islam in the four corners of the masjid",
    ),
    ("Democracy is the greatest shirk", "Democracy is the greatest shirk"),
    (
        "Did Jesus preach Jihad  Sheikh Abdullah al Faisal Answers",
        "Did Jesus preach jihad? — Shaykh Abdullah Faisal answers",
    ),
    ("Dismantaling shariya (WIth captions)", "The shirk in dismantling shariya"),
    ("Dismantling Sharia  Minor Sin or Major Disbel", "Dismantling sharia: minor sin or major disbelief"),
    (
        "Every Big Evil Empire Has Its Endby Shaykh Abdull",
        "Every big evil empire has its end — Shaykh Abdullah Faisal",
    ),
    ("Every man needs to know this before marriage", "Every man needs to know this before marriage"),
    ("Explosive Claim  Sheikh Albani's Link to Free", "Explosive claim: Sheikh Albani's link to Freemasonry"),
    ("Exposing Ibn Baz’s Aid to the Kuffar", "Exposing Ibn Baz's aid to the kuffar"),
    ("Exposing the evil world order - The jews", "Exposing the evil world order — the Jews"),
    (
        "Extremist vs. Islamic View  Are All Muslims G(1)",
        "Extremist vs Islamic view: are all Muslims grave worshippers?",
    ),
    ("Hero or Killer  The Biased Criticism of Sadda", "Hero or killer: the biased criticism of Saddam"),
    ("How did ALI (ra) Deal with the Khawarij (Puritans)", "How did Ali (ra) deal with the Khawarij?"),
    ("How do we deal with those who reject dawla1", "How do we deal with people who reject the dawla?"),
    ("Hypocrites Rushing To Join The Kuffar", "Hypocrites rushing to join the kuffar"),
    ("Ideological Warfare  The Only Battle That Tru(1)", "Ideological warfare: the only battle that truly matters"),
    (
        "If They Put The Sun In My Right Hand & Moon In My",
        "If they put the sun in my right hand and the moon in my left, I would not cease",
    ),
    ("Ignoring Invasion, Fixating on Women Driving", "Ignoring invasion, fixating on women driving"),
    ("Is it nessesery to takfir (muslims by name)", "Is it necessary to takfir Muslims by name?"),
    ("Jews & Christians Will Never Be Pleased With You", "Jews and Christians will never be pleased with you"),
    ("Jokers in the Pack - Refuting the Ashaa", "Jokers in the pack — refuting the Ash'ari"),
    ("Living in humulation while ummah suffers (ptsd)", "Living in humiliation while the ummah suffers (PTSD)"),
    ("Only a sincere beliver finds comfort in the truth!", "Only a sincere believer finds comfort in the truth"),
    (
        "Oppression causes apostasy(Forced Marriages as ex",
        "Oppression causes apostasy (forced marriages as an example)",
    ),
    (
        "Shamsis_teacher_Abu_Khadeeja_exposed_as_a_homosexual_pedophile_i0zSl3gpFog",
        "Shamsi's teacher Abu Khadeeja exposed",
    ),
    ("Shaykh faisal funny", "Shaykh Faisal (humorous clip)"),
    ("The 'Headless Chicken' Mentality of Modern Ex", "The headless chicken mentality of modern extremists"),
    ("The Battle Between Truth & Falsehood Never Ends", "The battle between truth and falsehood never ends"),
    ("The Evil Scholar is a lizard - Shaykh Abdullah Faisal", "The evil scholar is a lizard — Shaykh Abdullah Faisal"),
    ("The Importance of hijra - shaykh abdullah faisal", "The importance of hijra — Shaykh Abdullah Faisal"),
    ("The Sin of Refusing to Call a Kafir a Kafir", "The sin of refusing to call a kafir a kafir"),
    ("The Ummah is Sick & The Scholars are to Blame", "The ummah is sick and the scholars are to blame"),
    ("The killing of journalists", "The killing of journalists"),
    ("The lie about Jihad", "The lie about jihad"),
    (
        "The man who goes out in Jihad",
        "The man who goes out in Jihad, facing the enemy, will attain the highest honor "
        "and remain elevated above all others. — Shaykh Abdullah Faisal",
    ),
    ("They Control what you learn about isllam", "They control what you learn about Islam"),
    ("They Will Fight You Until You Leave Islam (Baqara", "They will fight you until you leave Islam (Surah Baqarah)"),
    (
        "Those Who Label the Mujahideen as Khawarij by Shaykh Abdullah Faisal",
        "Those who label the mujahideen as khawarij — Shaykh Abdullah Faisal",
    ),
    ("Those who follow their evil and corrupted desires", "Those who follow their evil and corrupted desires"),
    ("WHY ALLAH BLESS THE KUFFAR1 - Trim", "Why does Allah bless the kuffar?"),
    ("Who Is 'The Other'  Defining 'The Excuser' In(1)", "Who is 'the other'? Defining 'the excuser' in Islam"),
    ("Why do christians love jews and hate muslims", "Why do Christians love Jews and hate Muslims?"),
    ("Your Choice of Spouse Reveals Your True Faith", "Your choice of spouse reveals your true faith"),
    ("al wala al bara", "Al-wala wal-bara"),
    (
        "allah wil dump you and your wicked schohler in the hellfire",
        "Allah will dump you and your wicked scholar in the Hellfire",
    ),
    ("amj and faisal refuting hazami's", "AMJ and Faisal refuting Hazami"),
    ("baqara 216", "Surah al-Baqarah 216"),
    ("blind follwing wickeed schohlers", "Blind following wicked scholars will dump you in the Hellfire"),
    ("booti", "Refuting al-Bouti"),
    ("dealing with thise who reject dawla", "How do we deal with people who reject the dawla? (2)"),
    ("demanding shariya", "Demanding the implementation of sharia"),
    ("falling into the vicous webb of the shaytan", "Falling into the vicious web of the shaytan"),
    ("giving up better for worse", "Giving up the better for the worse"),
    ("ibn baz", "Why is ibn Baz a kaffir?"),
    (
        "if you are mot practicing u will get a personality",
        "If you are not practicing, you will develop a personality disorder",
    ),
    ("if you dont do jihad it will come to your door!!", "If you don't do jihad, it will come to your door"),
    ("ignore the jailoom", "Never Argue with a Jahiloon"),
    ("importance of hijra 2", "The importance of hijra (part 2)"),
    ("is dawla khawarij", "Is the dawla khawarij?"),
    ("man made izims skizims", "The shame of man-made law"),
    ("murfti of the taghut", "The mufti of the taghut"),
    ("narrsasit", "Narcissist personality disorder"),
    ("reality of truth 12", "The reality of truth (part 12)"),
    ("reject taghut", "Reject the taghut"),
    ("sdadwf", "Refuting those who put false conditions on jihad"),
    ("sign of a khawarij", "Signs of the khawarij"),
    ("signs of a hypocrite clip", "Signs of a hypocrite"),
    ("solution is living at dar al islam", "The solution is living in dar al-Islam"),
    ("tahakum", "Tahakum — ruling by other than what Allah revealed"),
    ("taliban breaks buddah ", "The Taliban destroys the Buddha statues"),
    ("the spy who killed imam al awlaki", "The spy who killed Imam Anwar al-Awlaki"),
    ("wicked scholars Abdullah faisal shaykh", "Wicked scholars — Shaykh Abdullah Faisal"),
]
CLIP_TITLE_OVERRIDES = {norm(stem): title for stem, title in _CLIP_TITLES_RAW}


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) > 8 and len(b) > 8 and (a in b or b in a):
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def fetch_metadata(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def build_thumb_index() -> dict[str, str]:
    """Index all images in thumb/videos/ and source thumb/ folder."""
    index: dict[str, str] = {}
    VIDEO_THUMB_OUT.mkdir(parents=True, exist_ok=True)

    folders = [VIDEO_THUMB_OUT]
    src_thumb = VIDEO_SRC / "thumb"
    if src_thumb.is_dir():
        folders.append(src_thumb)

    for folder in folders:
        for src in folder.iterdir():
            if src.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            if src.name in BLOCKED:
                continue
            if folder == src_thumb:
                dest = VIDEO_THUMB_OUT / src.name
                if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                    shutil.copy2(src, dest)
            rel = f"thumb/videos/{src.name}"
            for key in (norm(src.stem), norm(src.name)):
                if key:
                    index.setdefault(key, rel)
    return index


def find_thumb(filename: str, local_index: dict[str, str], archive_map: dict[str, str]) -> str | None:
    key = norm(filename)
    if key in local_index:
        return local_index[key]

    best_rel = None
    best_score = 0.0
    for k, rel in local_index.items():
        score = similarity(key, k)
        if score > best_score and score >= 0.92:
            best_score = score
            best_rel = rel
    if best_rel:
        return best_rel

    if key in archive_map:
        return archive_map[key]
    for k, rel in archive_map.items():
        if similarity(key, k) >= 0.92:
            return rel
    return None


def build_clips_archive_thumb_map(meta: dict) -> dict[str, str]:
    archive_thumb_map: dict[str, str] = {}
    for item in meta.get("files", []):
        name = item.get("name", "")
        if "the-creed-of-the-shia.thumbs/" in name and name.endswith(".jpg") and "_000001." in name:
            base = name.split("/")[-1]
            stem = re.sub(r"_000001\.jpg$", "", base)
            archive_thumb_map[norm(stem)] = f"https://archive.org/download/the-creed-of-the-shia/{name}"
    return archive_thumb_map


def append_promoted_videos(videos: list[dict], clips_meta: dict) -> list[dict]:
    """Add selected full-length videos from the clips archive to the video library."""
    if not PROMOTED_VIDEOS_FROM_CLIPS:
        return videos

    thumb_map = build_clips_archive_thumb_map(clips_meta)
    existing_titles = {norm(video["title"]) for video in videos}

    for spec in PROMOTED_VIDEOS_FROM_CLIPS:
        title = spec["title"]
        if norm(title) in existing_titles:
            continue
        filename = spec["file"]
        stem = Path(filename).stem
        thumb = find_thumb(stem + ".mp4", {}, thumb_map) or find_thumb(filename, {}, thumb_map)
        videos.append({
            "id": len(videos),
            "title": title,
            "file": filename,
            "archive": filename,
            "thumb": thumb,
            "stream": CLIPS_ARCHIVE_BASE + urllib.parse.quote(filename),
        })
        existing_titles.add(norm(title))

    return videos


def build_videos():
    meta = fetch_metadata(VIDEOS_ARCHIVE)
    local_index = build_thumb_index()

    archive_thumb_map: dict[str, str] = {}
    for item in meta.get("files", []):
        name = item.get("name", "")
        if "FaisalVideos.thumbs/" in name and name.endswith(".jpg") and "_000001." in name:
            base = name.split("/")[-1]
            stem = re.sub(r"_000001\.jpg$", "", base)
            archive_thumb_map[norm(stem)] = f"https://archive.org/download/FaisalVideos/{name}"

    all_mp4 = [
        f["name"] for f in meta.get("files", [])
        if f.get("name", "").endswith(".mp4") and not f["name"].startswith("FaisalVideos.thumbs")
    ]
    chosen = []
    seen = set()
    for name in sorted(all_mp4):
        if name in EXCLUDED_VIDEOS:
            continue
        plain = name.replace(".ia.mp4", ".mp4")
        if name.endswith(".ia.mp4") and plain in all_mp4:
            continue
        dedupe_key = plain.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chosen.append(name)

    videos = []
    for name in chosen:
        videos.append({
            "id": len(videos),
            "title": display_video_title(name),
            "file": name,
            "archive": name,
            "thumb": find_thumb(name, local_index, archive_thumb_map),
            "stream": "https://archive.org/download/FaisalVideos/" + urllib.parse.quote(name),
        })

    videos = dedupe_videos_by_title(videos)
    for index, video in enumerate(videos):
        video["id"] = index
    return videos


def build_clips(meta: dict | None = None):
    if meta is None:
        meta = fetch_metadata(CLIPS_ARCHIVE)
    archive_thumb_map = build_clips_archive_thumb_map(meta)

    all_mp4 = [f["name"] for f in meta.get("files", []) if f.get("name", "").endswith(".mp4")]
    chosen = []
    seen = set()

    for name in sorted(all_mp4):
        plain = name.replace(".ia.mp4", ".mp4")
        dedupe_key = plain.lower()
        if name.endswith(".ia.mp4") and plain in all_mp4:
            continue
        if dedupe_key in seen:
            continue
        stem = Path(name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        if norm(stem) in EXCLUDED_CLIP_NORMS:
            continue
        seen.add(dedupe_key)
        chosen.append(name)

    clips = []
    for name in chosen:
        stem = Path(name).stem
        if stem.endswith(".ia"):
            stem = stem[:-3]
        thumb = find_thumb(stem + ".mp4", {}, archive_thumb_map)
        if not thumb:
            thumb = find_thumb(name, {}, archive_thumb_map)

        stem_key = norm(stem)
        title = CLIP_TITLE_OVERRIDES.get(stem_key, clean_clip_title(stem))
        clips.append({
            "id": len(clips),
            "title": title,
            "file": name,
            "archive": name,
            "thumb": thumb,
            "stream": "https://archive.org/download/the-creed-of-the-shia/" + urllib.parse.quote(name),
        })

    return clips


def write_js(filename: str, const_name: str, base_const: str, base_url: str, items: list):
    path = WEBSITE / filename
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-media-catalog.py to refresh */\n")
        handle.write(f'const {base_const} = "{base_url}";\n\n')
        handle.write(f"const {const_name} = ")
        json.dump(items, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Wrote {path} ({len(items)} items)")


def write_search_index(videos: list[dict], clips: list[dict]) -> None:
    audio_path = WEBSITE / "data" / "search-audio.json"
    audio_entries = []
    if audio_path.is_file():
        with open(audio_path, encoding="utf-8") as handle:
            audio_entries = json.load(handle)

    video_entries = []
    for video in videos:
        entry = {
            "type": "video",
            "id": video["id"],
            "title": video["title"],
            "sub": "Video lecture",
            "href": f"videos.html?video={video['id']}",
        }
        if video.get("thumb"):
            entry["thumb"] = video["thumb"]
        video_entries.append(entry)

    clip_entries = []
    for clip in clips:
        entry = {
            "type": "clip",
            "id": clip["id"],
            "title": clip["title"],
            "sub": "Short clip",
            "href": f"clips.html?clip={clip['id']}",
        }
        if clip.get("thumb"):
            entry["thumb"] = clip["thumb"]
        clip_entries.append(entry)

    pdf_entries = []
    pdf_path = WEBSITE / "data" / "search-pdfs.json"
    if pdf_path.is_file():
        with open(pdf_path, encoding="utf-8") as handle:
            pdf_entries = json.load(handle)

    search_index = audio_entries + video_entries + clip_entries + pdf_entries
    out = WEBSITE / "search-index.js"
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("/* Auto-generated — run generate-catalog.py, generate-media-catalog.py, generate-pdf-catalog.py */\n")
        handle.write("const SEARCH_INDEX = ")
        json.dump(search_index, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")
    print(f"Wrote {out} ({len(search_index)} searchable items)")


def main():
    clips_meta = fetch_metadata(CLIPS_ARCHIVE)
    videos = append_promoted_videos(build_videos(), clips_meta)
    clips = build_clips(clips_meta)
    write_js("videos-data.js", "VIDEOS", "VIDEOS_ARCHIVE_BASE", "https://archive.org/download/FaisalVideos/", videos)
    write_js("clips-data.js", "CLIPS", "CLIPS_ARCHIVE_BASE", CLIPS_ARCHIVE_BASE, clips)
    write_search_index(videos, clips)

    v_thumbs = sum(1 for v in videos if v.get("thumb"))
    c_thumbs = sum(1 for c in clips if c.get("thumb"))
    print(f"Videos: {len(videos)} ({v_thumbs} with thumbnails)")
    print(f"Clips: {len(clips)} ({c_thumbs} with thumbnails)")

    build_home_pool = WEBSITE / "build-home-previews-pool.py"
    if build_home_pool.is_file():
        subprocess.run([sys.executable, str(build_home_pool)], check=False, cwd=WEBSITE)


if __name__ == "__main__":
    main()