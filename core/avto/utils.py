def serialize_questions(questions):
    data = []

    for q in questions:
        data.append({
            "id": q.id,
            "text": q.text,
            "image": q.image.url if q.image else None,
            "answers": [
                {
                    "id": a.id,
                    "text": a.text,
                    "is_correct": a.is_correct
                }
                for a in q.answers.all()
            ]
        })

    return data


