"""Topic tests (Mavzulashtirilgan testlar): bilet questions grouped by the topic of the rules they test.

A student picks a topic and solves 20 random questions of it, all of them, or only the ones they got
wrong last time. A question counts as learned while the student's latest answer to it is correct.
"""
import random

from django.db.models import Q
from django.utils import timezone

from .marathon import MINUTES_PER_QUESTION
from .models import Question, TestSession, TopicGroup, UserAnswer

SOURCE = "mavzu"
QUICK_SIZE = 20
MODES = ("quick", "all", "mistakes")


def question_pool(topic):
    return Question.objects.filter(Q(mavzu=topic) | Q(extra_topics=topic), kategoriya__aktiv=True).distinct()


def latest_results(user):
    """{question_id: True/False} — whether the student's latest answer to each question was correct."""
    answers = (
        UserAnswer.objects
        .filter(session__user=user, selected_answer__isnull=False)
        .order_by("id")
        .values_list("question_id", "is_correct")
    )
    return dict(answers)


def page_groups(user):
    """The topic groups with their topics and the student's progress in each; empty groups are left out."""
    results = latest_results(user)
    by_topic = {}
    live = Question.objects.filter(kategoriya__aktiv=True)
    pairs = list(live.filter(mavzu__isnull=False).values_list("id", "mavzu_id"))
    pairs += list(live.filter(extra_topics__isnull=False).values_list("id", "extra_topics"))
    for question_id, topic_id in pairs:
        ids = by_topic.setdefault(topic_id, [])
        if question_id not in ids:
            ids.append(question_id)

    groups = []
    number = 0
    for group in TopicGroup.objects.prefetch_related("topics"):
        topics = []
        for topic in group.topics.all():
            ids = by_topic.get(topic.id)
            if not topic.aktiv or not ids:
                continue
            number += 1
            learned = sum(results.get(qid) is True for qid in ids)
            mistakes = sum(results.get(qid) is False for qid in ids)
            topics.append({
                "id": topic.id,
                "number": number,
                "name": topic.name(),
                "total": len(ids),
                "learned": learned,
                "mistakes": mistakes,
                "percent": round(learned * 100 / len(ids)),
            })
        if topics:
            groups.append({
                "slug": group.slug,
                "icon": group.icon,
                "name": group.name(),
                "topics": topics,
                "total": sum(t["total"] for t in topics),
            })
    return groups


def summary(groups):
    total = sum(g["total"] for g in groups)
    learned = sum(t["learned"] for g in groups for t in g["topics"])
    return {
        "topics": sum(len(g["topics"]) for g in groups),
        "total": total,
        "learned": learned,
        "percent": round(learned * 100 / total) if total else 0,
    }


def pick_question_ids(user, topic, mode):
    ids = list(question_pool(topic).values_list("id", flat=True))
    if mode == "mistakes":
        results = latest_results(user)
        ids = [qid for qid in ids if results.get(qid) is False]
    random.shuffle(ids)
    return ids[:QUICK_SIZE] if mode == "quick" else ids


def start(user, topic, mode):
    """Open a practice session on the topic. Raises ValueError when the mode has no questions."""
    if mode not in MODES:
        mode = "quick"
    question_ids = pick_question_ids(user, topic, mode)
    if not question_ids:
        raise ValueError("no questions")
    first = Question.objects.select_related("kategoriya").get(id=question_ids[0])
    session = TestSession.objects.create(
        user=user, category=first.kategoriya, topic=topic, test_kind="shablon", source=SOURCE,
        started_at=timezone.now(), duration_minutes=len(question_ids) * MINUTES_PER_QUESTION,
    )
    session.questions.set(question_ids)
    session.question_order = question_ids
    session.save(update_fields=["question_order"])
    return session


def restart_mode(session):
    return "all" if len(session.question_order) > QUICK_SIZE else "quick"
