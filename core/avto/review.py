"""The questions a student got wrong in a finished test, with the right answer, for reviewing the mistakes."""
from django.urls import reverse

from .models import Question, UserAnswer


def mistakes(session, language):
    """One item per wrongly answered question, in the order of the test (skipped questions are not listed)."""
    wrong = {
        ua.question_id: ua
        for ua in UserAnswer.objects.filter(session=session, is_correct=False, selected_answer__isnull=False)
        .select_related("selected_answer")
    }
    questions = Question.objects.filter(id__in=wrong).prefetch_related("javoblar")
    by_id = {q.id: q for q in questions}
    items = []
    for number, question_id in enumerate(session.question_order, 1):
        question = by_id.get(question_id)
        if not question:
            continue
        correct = question.correct_answer_for(language)
        items.append({
            "number": number,
            "text": question.get_text(language),
            "image": question.rasm.url if question.rasm else None,
            "chosen": wrong[question_id].selected_answer.get_text(language),
            "correct": correct.get_text(language) if correct else "",
            "explanation": (
                f"{reverse('question_explanation', args=[question_id])}?lang={language}"
                if question.explanation_for(language) else None
            ),
        })
    return items
