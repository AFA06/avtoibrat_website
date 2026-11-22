"""Two focused similarity tests: road signs and road situations.

Only questions with a verified image/wording match are included. Sign questions
require matching pictures. Situation matches share a topic; distinct pictures
cannot be joined just because their question stems use the same words.
Matched families remain adjacent, with exact duplicates asked once.
Rebuilding retires old groups without deleting students' attempts.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace

from django.db import transaction

IMAGE_SAME = 20          # of 256 bits: the same picture (other size, crop, watermark)
IMAGE_LOOKALIKE = 35     # same sign shape / colours / layout
TEXT_WITH_IMAGE = 0.4
TEXT_STYLE = 0.6
MIN_WORDS = 5
HASH_SIZE = 16

_WORD = re.compile(r"[a-z']{3,}|\d+")


# ------------------------------------------------------------------ features
def image_hash(fileobj) -> int | None:
    """256-bit difference hash: compares neighbouring pixels of a 17x16 grey thumbnail."""
    from PIL import Image

    try:
        img = Image.open(fileobj).convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.LANCZOS)
    except Exception:
        return None
    px = list(img.getdata())
    value = 0
    for row in range(HASH_SIZE):
        for col in range(HASH_SIZE):
            i = row * (HASH_SIZE + 1) + col
            value = value << 1 | (px[i] > px[i + 1])
    return value


def distance(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    return bin(a ^ b).count("1")


def words(text: str) -> list[str]:
    text = (text or "").lower()
    for quote in ("‘", "ʻ", "’", "`", "ʼ"):
        text = text.replace(quote, "'")
    return _WORD.findall(text)


def normalized_content(text: str) -> tuple[str, ...]:
    """Ignore typography, while retaining short words, numbers and negation."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    for quote in ("‘", "ʻ", "’", "`", "ʼ", "'"):
        text = text.replace(quote, "")
    return tuple(re.findall(r"\d+(?:[.,]\d+)*|[^\W\d_]+|[<>≤≥=+%/−-]", text))


def duplicate_ids(items: list[Item]) -> set[int]:
    """Compare complete question + choices + correct answers, then the picture.
    A resized/watermarked copy may hash differently; matching only five bits
    missed those copies. Never discard a distinct answer or compare to a copy
    already discarded (which would create unsafe transitive merges).
    """
    kept = defaultdict(list)
    duplicates = set()
    for item in sorted(items, key=lambda i: i.id):
        key = (item.collection, normalized_content(item.text), tuple(sorted(item.answers)))
        for other in kept[key]:
            delta = distance(item.image, other.image)
            same_picture = (item.image is None and other.image is None) or (
                delta is not None and delta <= IMAGE_LOOKALIKE)
            if same_picture:
                duplicates.add(item.id)
                break
        else:
            kept[key].append(item)
    return duplicates


def tfidf_vectors(docs: dict[int, list[str]]) -> dict[int, dict[str, float]]:
    df = Counter(w for ws in docs.values() for w in set(ws))
    n = len(docs) or 1
    out = {}
    for qid, ws in docs.items():
        counts = Counter(ws)
        vec = {w: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
        out[qid] = {w: x / norm for w, x in vec.items() if x}
    return out


def text_similarities(vectors: dict[int, dict[str, float]], minimum: float) -> dict[tuple[int, int], float]:
    """Cosine of every pair at or above `minimum`, through an inverted index (no 1 200 x 1 200 loop)."""
    index = defaultdict(list)
    for qid, vec in vectors.items():
        for w, x in vec.items():
            index[w].append((qid, x))
    out = {}
    for a, vec in vectors.items():
        dots = defaultdict(float)
        for w, x in vec.items():
            for b, y in index[w]:
                if b > a:
                    dots[b] += x * y
        for b, s in dots.items():
            if s >= minimum:
                out[(a, b)] = s
    return out


# ------------------------------------------------------------------ the plan (pure: easy to test)
@dataclass
class Item:
    id: int
    text: str
    topics: frozenset[int]
    main_topic: int | None
    image: int | None = None
    section: int | None = None        # the topic's group (e.g. «Yo‘l belgilari»)
    collection: str = ""
    answers: tuple = ()  # Normalized answer texts and their correctness, independent of order.


@dataclass
class PlannedSet:
    question_ids: list[int]
    topic_id: int | None
    kind: str                     # rasm | matn | aralash
    collection: str = ""

    @property
    def signature(self) -> str:
        ids = ",".join(map(str, sorted(self.question_ids)))
        # «images» can hold the same questions as another set; older sets keep their original signature.
        return hashlib.sha1((f"images:{ids}" if self.collection == "images" else ids).encode()).hexdigest()


@dataclass
class Plan:
    sets: list[PlannedSet] = field(default_factory=list)
    duplicates: int = 0
    links: Counter = field(default_factory=Counter)


def _link(a: Item, b: Item, text: float) -> tuple[float, str] | None:
    """(strength, reason) when the two questions are look-alikes, else None."""
    d = distance(a.image, b.image)
    if d is not None and d <= IMAGE_SAME:
        return 2.0 + text, "rasm"
    if d is not None and d <= IMAGE_LOOKALIKE and text >= TEXT_WITH_IMAGE:
        return 1.0 + text + (IMAGE_LOOKALIKE - d) / IMAGE_LOOKALIKE, "rasm"
    specific = len(words(a.text)) >= MIN_WORDS and len(words(b.text)) >= MIN_WORDS
    if text >= TEXT_STYLE and specific and a.topics & b.topics:
        return text, "matn"
    return None


def _closeness(a: Item, b: Item, text: float) -> float:
    """How alike two questions are, for ordering inside a set."""
    d = distance(a.image, b.image)
    picture = 0.0 if d is None else max(0.0, 1 - d / (2 * IMAGE_LOOKALIKE))
    return text + picture


def _ordered(ids: list[int], items: dict[int, Item], sims) -> list[int]:
    """Start from the question with most look-alikes, then always go to the closest one left."""
    def sim(a, b):
        return sims.get((min(a, b), max(a, b)), 0.0)

    def close(a, b):
        return _closeness(items[a], items[b], sim(a, b))

    left = set(ids)
    current = max(sorted(ids), key=lambda q: sum(close(q, o) for o in ids if o != q))
    order = [current]
    left.discard(current)
    while left:
        current = max(sorted(left), key=lambda q: close(current, q))
        order.append(current)
        left.discard(current)
    return order


def _dominant_topic(ids: list[int], items: dict[int, Item]) -> int | None:
    counts = Counter(items[q].main_topic for q in ids if items[q].main_topic)
    return min(counts, key=lambda t: (-counts[t], t)) if counts else None


def plan(items: list[Item]) -> Plan:
    """Three tests, built only from verified matching pairs. Connected families
    stay together; never pad a family with unrelated questions from its topic."""
    result = Plan()
    eligible = [i for i in items if i.collection in ("signs", "situations")
                and (i.collection != "signs" or i.image is not None)]
    by_id = {i.id: i for i in eligible}
    sims = text_similarities(tfidf_vectors({i.id: words(i.text) for i in eligible}), TEXT_WITH_IMAGE)
    duplicates = duplicate_ids(eligible)
    result.duplicates = len(duplicates)
    for category in ("signs", "situations"):
        live = [i for i in eligible if i.collection == category and i.id not in duplicates]
        parent = {i.id: i.id for i in live}
        matched = set()

        def root(q):
            while parent[q] != q:
                parent[q] = parent[parent[q]]
                q = parent[q]
            return q

        for index, a in enumerate(live):
            for b in live[index + 1:]:
                # Similar-looking scenes from unrelated rules are misleading.
                if category == "situations" and not a.topics & b.topics:
                    continue
                score = sims.get((min(a.id, b.id), max(a.id, b.id)), 0)
                link = _link(a, b, score)
                if not link or category == "signs" and link[1] != "rasm":
                    continue
                if category == "situations" and link[1] == "matn":
                    if a.image is not None or b.image is not None:
                        continue
                    if min(len(words(a.text)), len(words(b.text))) < 8:
                        continue
                parent[root(b.id)] = root(a.id)
                matched.update((a.id, b.id))
                result.links[link[1]] += 1
        families = defaultdict(list)
        for qid in sorted(matched):
            families[root(qid)].append(qid)
        order = []
        for family in sorted(families.values(), key=lambda ids: (_dominant_topic(ids, by_id) or 0, min(ids))):
            order.extend(_ordered(family, by_id, sims))
        if order:
            result.sets.append(PlannedSet(order, None, "rasm" if category == "signs" else "aralash", category))
    images = _same_picture_set(items)
    if images:
        result.sets.append(images)
    return result


def _same_picture_set(items: list[Item]) -> PlannedSet | None:
    """«Rasmlar bo‘yicha»: questions outside the road-sign topics that show the same picture but ask something different.
    Only near-identical pictures link (resize, crop, watermark); exact repeats of a question are left out."""
    pictured = [replace(i, collection="images") for i in items if i.image is not None and i.collection != "signs"]
    duplicates = duplicate_ids(pictured)
    live = [i for i in pictured if i.id not in duplicates]
    by_id = {i.id: i for i in live}
    parent = {i.id: i.id for i in live}

    def root(q):
        while parent[q] != q:
            parent[q] = parent[parent[q]]
            q = parent[q]
        return q

    matched = set()
    for index, a in enumerate(live):
        for b in live[index + 1:]:
            d = distance(a.image, b.image)
            if d is None or d > IMAGE_SAME:
                continue
            parent[root(b.id)] = root(a.id)
            matched.update((a.id, b.id))
    families = defaultdict(list)
    for qid in sorted(matched):
        families[root(qid)].append(qid)
    sims = text_similarities(tfidf_vectors({q: words(by_id[q].text) for q in matched}), TEXT_WITH_IMAGE)
    order = []
    for family in sorted(families.values(), key=lambda ids: (_dominant_topic(ids, by_id) or 0, min(ids))):
        order.extend(_ordered(family, by_id, sims))
    return PlannedSet(order, None, "rasm", "images") if order else None


# ------------------------------------------------------------------ database
def load_items() -> list[Item]:
    from .models import Question

    items = []
    qs = (Question.objects.filter(is_archived=False, kategoriya__aktiv=True)
          .select_related("mavzu__group").prefetch_related("extra_topics", "javoblar").order_by("id"))
    for q in qs:
        image = None
        if q.rasm:
            try:
                with q.rasm.open("rb") as f:
                    image = image_hash(f)
            except Exception:
                image = None
        if image in (0, (1 << (HASH_SIZE * HASH_SIZE)) - 1):
            image = None  # A blank picture is not evidence of similarity.
        topics = {t.id for t in q.extra_topics.all() if t.aktiv}
        if q.mavzu_id and q.mavzu.aktiv:
            topics.add(q.mavzu_id)
        section_slug = q.mavzu.group.slug if q.mavzu_id and q.mavzu.aktiv else ""
        collection = "signs" if section_slug == "yol-belgilari" else "situations" if section_slug in {
            "chorrahalar", "ishoralar-va-chiziqlar", "asosiy-manyovrlar", "maxsus-vaziyatlar",
            "umumiy-qoidalar", "tashish",
        } else ""
        answers = tuple(sorted((normalized_content(a.matn_uzb), normalized_content(a.matn_uz_kr),
                                normalized_content(a.matn_rus), a.togri) for a in q.javoblar.all()))
        items.append(Item(q.id, q.matn_uzb, frozenset(topics), q.mavzu_id, image,
                          q.mavzu.group_id if q.mavzu_id else None, collection, answers))
    return items


@transaction.atomic
def rebuild(items: list[Item] | None = None) -> dict:
    """Write the planned sets. A set with the same questions as before keeps its id (and the students'
    results); sets that no longer exist are switched off, never deleted, so old results stay readable."""
    from .models import SimilarGroup

    result = plan(load_items() if items is None else items)
    numbers = Counter()
    seen = set()
    created = updated = 0
    for s in result.sets:
        numbers[s.topic_id] += 1
        group = SimilarGroup.objects.filter(signature=s.signature).first()
        fields = dict(collection=s.collection, topic_id=s.topic_id, kind=s.kind, number=numbers[s.topic_id], aktiv=True,
                      question_order=s.question_ids)
        if group is None:
            group = SimilarGroup.objects.create(signature=s.signature, **fields)
            created += 1
        else:
            for k, v in fields.items():
                setattr(group, k, v)
            group.save()
            updated += 1
        group.questions.set(s.question_ids)
        seen.add(group.id)
    retired = SimilarGroup.objects.filter(aktiv=True).exclude(id__in=seen).update(aktiv=False)
    return {
        "sets": len(result.sets),
        "questions": sum(len(s.question_ids) for s in result.sets),
        "by_kind": dict(Counter(s.kind for s in result.sets)),
        "links": dict(result.links),
        "duplicates": result.duplicates,
        "created": created,
        "kept": updated,
        "retired": retired,
    }
