"""O‘xshash savollar: sets of look-alike questions that students often mix up.

Two questions are linked when one of these holds:

  1. the same picture: their images are near-identical (perceptual hash distance <= IMAGE_SAME);
  2. a look-alike picture with similar wording: the images have the same shape and colours
     (distance <= IMAGE_LOOKALIKE, e.g. two red prohibition circles) and the question texts are
     similar (cosine >= TEXT_WITH_IMAGE);
  3. the same question style in the same topic: the texts are clearly alike (cosine >= TEXT_STYLE),
     both say something specific (at least MIN_WORDS words, so generic stems such as
     «Bu yo‘l belgisi:» never link on their own), and they share a topic.

Sets are built from the strongest links first and never grow past MAX_SET questions. Pairs that end
up alone are combined per topic into a «jamlanma» set. Inside a set, each question is followed by the
one most like it, so look-alikes stand side by side and the student has to spot the difference.
Exact duplicates (the same question in several bilets) are asked only once.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.db import transaction

IMAGE_SAME = 20          # of 256 bits: the same picture (other size, crop, watermark)
IMAGE_LOOKALIKE = 35     # same sign shape / colours / layout
TEXT_WITH_IMAGE = 0.4
TEXT_STYLE = 0.6
DUPLICATE_TEXT = 0.98
MIN_WORDS = 5
MAX_SET = 20
MIN_SET = 3
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


@dataclass
class PlannedSet:
    question_ids: list[int]
    topic_id: int | None
    kind: str                     # rasm | matn | aralash

    @property
    def signature(self) -> str:
        return hashlib.sha1(",".join(map(str, sorted(self.question_ids))).encode()).hexdigest()


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
    result = Plan()
    by_id = {i.id: i for i in items}
    vectors = tfidf_vectors({i.id: words(i.text) for i in items})
    sims = text_similarities(vectors, TEXT_WITH_IMAGE)

    # exact duplicates: same text and same picture → keep the first one
    duplicate_of = {}
    for (a, b), s in sorted(sims.items()):
        d = distance(by_id[a].image, by_id[b].image)
        same_picture = d is not None and d <= 5 or (by_id[a].image is None and by_id[b].image is None)
        if s >= DUPLICATE_TEXT and same_picture and b not in duplicate_of:
            duplicate_of[b] = duplicate_of.get(a, a)
    result.duplicates = len(duplicate_of)
    live = [i for i in items if i.id not in duplicate_of]
    ids = [i.id for i in live]

    edges = []
    for x, a in enumerate(ids):
        for b in ids[x + 1:]:
            link = _link(by_id[a], by_id[b], sims.get((a, b), 0.0))
            if link:
                edges.append((link[0], a, b, link[1]))
    edges.sort(key=lambda e: (-e[0], e[1], e[2]))

    parent = {q: q for q in ids}
    members = {q: [q] for q in ids}
    reasons = {q: set() for q in ids}

    def root(q):
        while parent[q] != q:
            parent[q] = parent[parent[q]]
            q = parent[q]
        return q

    for _strength, a, b, reason in edges:
        ra, rb = root(a), root(b)
        if ra == rb or len(members[ra]) + len(members[rb]) > MAX_SET:
            continue
        if len(members[ra]) < len(members[rb]):
            ra, rb = rb, ra
        parent[rb] = ra
        members[ra] += members.pop(rb)
        reasons[ra] |= reasons.pop(rb) | {reason}
        result.links[reason] += 1

    clusters = [(sorted(m), reasons[r]) for r, m in members.items() if len(m) > 1]
    big = [(m, r) for m, r in clusters if len(m) >= MIN_SET]
    small = [m for m, r in clusters if len(m) < MIN_SET]

    for m, r in big:
        result.sets.append(PlannedSet(_ordered(m, by_id, sims), _dominant_topic(m, by_id),
                                      "rasm" if "rasm" in r else "matn"))

    # pairs left alone: one «jamlanma» per topic, at most MAX_SET questions each
    per_topic = defaultdict(list)
    for m in small:
        per_topic[_dominant_topic(m, by_id)].append(m)
    for topic, pairs in sorted(per_topic.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        chunk: list[int] = []
        for m in sorted(pairs):
            if chunk and len(chunk) + len(m) > MAX_SET:
                result.sets.append(PlannedSet(chunk, topic, "aralash"))
                chunk = []
            chunk += _ordered(m, by_id, sims)
        if chunk:
            result.sets.append(PlannedSet(chunk, topic, "aralash"))

    _absorb_tiny_sets(result, by_id)
    result.sets.sort(key=lambda s: (s.topic_id is None, s.topic_id or 0, {"rasm": 0, "matn": 1, "aralash": 2}[s.kind],
                                    s.question_ids[0]))
    return result


def _absorb_tiny_sets(result: Plan, items: dict[int, Item]) -> None:
    """A set of fewer than MIN_SET questions is too short for a test: add it to the smallest set of the
    same topic that has room, else of the same section; otherwise join the other tiny sets of its section."""
    def section(s):
        return items[s.question_ids[0]].section

    def home(tiny, same):
        room = [s for s in result.sets if s is not tiny and len(s.question_ids) >= MIN_SET and same(s)
                and len(s.question_ids) + len(tiny.question_ids) <= MAX_SET]
        return min(room, key=lambda s: (len(s.question_ids), s.question_ids[0])) if room else None

    for tiny in sorted([s for s in result.sets if len(s.question_ids) < MIN_SET], key=lambda s: s.question_ids[0]):
        target = home(tiny, lambda s: s.topic_id == tiny.topic_id) or home(tiny, lambda s: section(s) == section(tiny))
        if target is None:
            continue
        target.question_ids += tiny.question_ids
        if target.kind != tiny.kind:
            target.kind = "aralash"
        result.sets.remove(tiny)

    leftovers = defaultdict(list)
    for tiny in [s for s in result.sets if len(s.question_ids) < MIN_SET]:
        leftovers[section(tiny)].append(tiny)
    for group in leftovers.values():
        if len(group) < 2:
            continue
        merged = PlannedSet([q for s in group for q in s.question_ids][:MAX_SET],
                            _dominant_topic([q for s in group for q in s.question_ids], items), "aralash")
        for s in group:
            result.sets.remove(s)
        result.sets.append(merged)


# ------------------------------------------------------------------ database
def load_items() -> list[Item]:
    from .models import Question

    items = []
    qs = (Question.objects.filter(is_archived=False, kategoriya__aktiv=True)
          .select_related("mavzu").prefetch_related("extra_topics").order_by("id"))
    for q in qs:
        image = None
        if q.rasm:
            try:
                with q.rasm.open("rb") as f:
                    image = image_hash(f)
            except Exception:
                image = None
        topics = {t.id for t in q.extra_topics.all()}
        if q.mavzu_id:
            topics.add(q.mavzu_id)
        items.append(Item(q.id, q.matn_uzb, frozenset(topics), q.mavzu_id, image,
                          q.mavzu.group_id if q.mavzu_id else None))
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
        fields = dict(topic_id=s.topic_id, kind=s.kind, number=numbers[s.topic_id], aktiv=True,
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
