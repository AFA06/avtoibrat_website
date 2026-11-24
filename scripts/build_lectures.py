#!/usr/bin/env python3
"""Build web assets from the school's PPTX decks and matching rendered PDFs.

Render each source deck to PDF first, naming it uz-1.pdf … ru-7.pdf.
Usage: python scripts/build_lectures.py --slides 'Slides ' --pdfs /path/to/pdfs
Requires Pillow and Poppler's pdftoppm/pdfinfo; no runtime conversion on the server.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main", "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
SLUGS = ["warning", "priority", "prohibition", "mandatory", "information", "service", "additional"]
ROMAN = {s: i for i, s in enumerate(["I", "II", "III", "IV", "V", "VI", "VII"], 1)}


def source_info(path):
    number = ROMAN[re.split(r"[ _]", path.name)[0]]
    russian = any(s in path.name for s in ("предупреж", "приорет", "запрещ", "предпис", "Информационно", "знаки сервиса", "Знаки_дополнитель"))
    return ("ru" if russian else "uz"), number


def extract(path):
    # Follow presentation relationships, rather than guessing from XML filenames.
    with ZipFile(path) as z:
        rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        presentation = ET.fromstring(z.read("ppt/presentation.xml"))
        size = presentation.find("p:sldSz", NS)
        slides = []
        for item in presentation.findall("p:sldIdLst/p:sldId", NS):
            rid = item.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = targets[rid]
            target = target.lstrip("/") if target.startswith("/") else "ppt/" + target
            xml = ET.fromstring(z.read(target))
            paragraphs = [re.sub(r"\s+", " ", "".join(t.text or "" for t in p.findall(".//a:t", NS))).strip() for p in xml.findall(".//a:p", NS)]
            paragraphs = list(dict.fromkeys(p for p in paragraphs if p))
            text = "\n".join(paragraphs)
            example = bool(re.search(r"[?？]|\b[Бб]илет\b|\b[Сс]авол\b", text))
            candidates = [p for p in paragraphs if re.match(r"^[1-7]\.\d", p)]
            if source_info(path)[0] == "ru":
                russian_titles = [p for p in candidates if not re.search("[ҚқҒғҲҳЎў]", p)]
                # Some Russian decks retain an old Uzbek sign-title box behind
                # its Russian replacement. Keep the translated title in text.
                if russian_titles:
                    paragraphs = [p for p in paragraphs if p not in candidates or p in russian_titles]
                candidates = list(reversed(russian_titles or candidates))
            title = next(iter(candidates), next((p for p in paragraphs if len(p) > 10), ""))
            slide = {"number": len(slides) + 1, "title": title[:140], "paragraphs": paragraphs, "kind": "example" if example else "rule"}
            rel_path = posixpath.join(posixpath.dirname(target), "_rels", posixpath.basename(target) + ".rels")
            if rel_path in z.namelist():
                for rel in ET.fromstring(z.read(rel_path)):
                    media = posixpath.normpath(posixpath.join(posixpath.dirname(target), rel.get("Target", "")))
                    if rel.get("TargetMode") != "External" and media.lower().endswith(".mp4") and media in z.namelist():
                        slide["_video_source"] = media
                        break
            slides.append(slide)
        return slides, int(size.get("cx")) / int(size.get("cy"))


def attach_videos(path, slides, output):
    with ZipFile(path) as source:
        for slide in slides:
            media = slide.pop("_video_source", None)
            if media:
                data = source.read(media)
                name = hashlib.sha256(data).hexdigest()[:24] + ".mp4"
                (output / name).write_bytes(data)
                slide["video"] = "lectures/" + name


def build_deck(path, pdfs, output):
    lang, number = source_info(path)
    key = f"{lang}-{number}"
    pdf = pdfs / f"{key}.pdf"
    slides, ratio = extract(path)
    attach_videos(path, slides, output)
    info = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
    count = int(re.search(r"Pages:\s+(\d+)", info)[1])
    if count != len(slides):
        raise ValueError(f"{key}: {count} rendered pages != {len(slides)} source slides")
    # Stream RGB pages through one Poppler process: no large PNG scratch files
    # and no repeated parsing of the same PDF for every slide.
    def token(stream):
        value = bytearray()
        while True:
            char = stream.read(1)
            if not char:
                raise ValueError(f"{key}: incomplete rendered page header")
            if char == b"#" and not value:
                stream.readline()
                continue
            if char.isspace():
                if value:
                    return bytes(value)
            else:
                value.extend(char)

    with subprocess.Popen(["pdftoppm", "-scale-to", "1600", str(pdf)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as renderer:
        for slide in slides:
            if token(renderer.stdout) != b"P6":
                raise ValueError(f"{key}: expected RGB page")
            width, height = int(token(renderer.stdout)), int(token(renderer.stdout))
            if token(renderer.stdout) != b"255":
                raise ValueError(f"{key}: unexpected colour depth")
            pixels = renderer.stdout.read(width * height * 3)
            if len(pixels) != width * height * 3:
                raise ValueError(f"{key}: incomplete rendered page")
            with Image.frombytes("RGB", (width, height), pixels) as image:
                # PDF exports use the native slide size (no paper margins).
                if abs(image.width / image.height - ratio) > .03:
                    raise ValueError(f"{key}: PDF must use slide dimensions, not print paper dimensions")
                buf = io.BytesIO()
                image.save(buf, "WEBP", quality=82, method=4)
                data = buf.getvalue()
                digest = hashlib.sha256(data).hexdigest()[:24]
                (output / f"{digest}.webp").write_bytes(data)
                image.thumbnail((320, 220))
                image.save(output / f"{digest}-thumb.webp", "WEBP", quality=76, method=4)
                slide["image"] = f"lectures/{digest}.webp"
                slide["thumbnail"] = f"lectures/{digest}-thumb.webp"
        if renderer.wait():
            raise ValueError(f"{key}: page renderer failed")
    print(f"{key}: {len(slides)} pages", flush=True)
    return lang, number, {"slug": SLUGS[number-1], "number": number, "ratio": round(ratio, 5), "slides": slides, "source": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slides", type=Path, required=True)
    parser.add_argument("--pdfs", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "core/static/lectures"
    output.mkdir(parents=True, exist_ok=True)
    decks = {"uz": {}, "ru": {}}
    paths = sorted(args.slides.glob("*.pptx"))
    if len(paths) != 14 or len({source_info(p) for p in paths}) != 14:
        raise ValueError("Expected seven distinct topics in both Uzbek and Russian")
    with ThreadPoolExecutor(max_workers=1) as pool:
        for lang, number, deck in pool.map(lambda path: build_deck(path, args.pdfs, output), paths):
            decks[lang][number] = deck
    for lang, topics in decks.items():
        target = ROOT / f"core/avto/data/lectures/{lang}.json"
        target.write_text(json.dumps([topics[n] for n in sorted(topics)], ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Built {sum(len(d['slides']) for v in decks.values() for d in v.values())} slides")


if __name__ == "__main__":
    main()
