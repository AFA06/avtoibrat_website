"""Current question ordering and collection edits; test-session snapshots are never changed."""
from uuid import uuid4
from django.db.models import F, Q, BigIntegerField, OuterRef, Subquery, Max
from django.db.models.functions import Coalesce
from .models import Question, SimilarGroup, TestCategory, TopicQuestionOrder


def ordered(questions):
    return questions.annotate(_placement_order=Coalesce('placement_order', F('pk'), output_field=BigIntegerField())).order_by('_placement_order', 'pk')


def ordered_topic(questions, topic):
    custom = TopicQuestionOrder.objects.filter(topic=topic, question_id=OuterRef('pk')).values('position')[:1]
    last = TopicQuestionOrder.objects.filter(topic=topic).order_by().values('topic').annotate(last=Max('position')).values('last')[:1]
    return questions.annotate(_placement_order=Coalesce(Subquery(custom), Subquery(last)+F('pk'), F('placement_order'), F('pk'), output_field=BigIntegerField())).order_by('_placement_order', 'pk')


def place(question, position, scope='bilet'):
    # Serialize placement changes across categories as the same question can be
    # shared between several topics. IDs and answer/history relations stay fixed.
    list(TestCategory.objects.select_for_update().order_by('pk').values_list('pk', flat=True))
    if scope == 'topic':
        topic = question.mavzu
        pool = Question.objects.filter(Q(mavzu=topic) | Q(extra_topics=topic), use_in_topics=True, is_archived=False).exclude(pk=question.pk).distinct()
        ids = list(ordered_topic(pool, topic).values_list('pk', flat=True))
        ids.insert(min((position or len(ids)+1)-1, len(ids)), question.pk)
        TopicQuestionOrder.objects.bulk_create([TopicQuestionOrder(topic=topic, question_id=pk, position=n) for n, pk in enumerate(ids, 1)], update_conflicts=True, update_fields=['position'], unique_fields=['topic', 'question'])
        return
    all_ids = list(ordered(Question.objects.exclude(pk=question.pk)).values_list('pk', flat=True))
    pool = Question.objects.exclude(pk=question.pk).filter(is_archived=False)
    pool = pool.filter(kategoriya_id=question.kategoriya_id, use_in_bilet=True)
    target = list(ordered(pool).values_list('pk', flat=True))
    if position is None:
        # New questions append. Ordinary edits keep their existing position.
        if question.placement_order is not None:
            return
        position = len(target)+1
    if position <= len(target):
        index = all_ids.index(target[position-1])
    else:
        index = len(all_ids)
    all_ids.insert(index, question.pk)
    Question.objects.bulk_update([Question(pk=pk, placement_order=n) for n, pk in enumerate(all_ids, 1)], ['placement_order'])


def assign_sets(question, selected, position=None, new_name='', new_name_ru=''):
    # Version changed collections: previous attempts retain the original group
    # and question order, while future attempts use the newly edited collection.
    selected_ids = {g.pk for g in selected}
    ids = SimilarGroup.objects.filter(aktiv=True, collection__in=('signs', 'images', 'answers', 'mixed')).filter(Q(pk__in=selected_ids) | Q(questions=question)).values('pk')
    groups = SimilarGroup.objects.select_for_update().filter(pk__in=ids, aktiv=True)
    for group in groups:
        before = list(dict.fromkeys(group.question_order))
        after = [pk for pk in before if pk != question.pk]
        if group.pk in selected_ids:
            if position is None and question.pk in before:
                after = before
            else:
                after.insert(min((position or len(after)+1)-1, len(after)), question.pk)
        if after == before:
            if group.pk in selected_ids and not group.is_manual and not question.auto_similar:
                group.is_manual = True
                group.origin_signature = group.signature
                group.signature = 'manual-'+uuid4().hex
                group.save(update_fields=['is_manual', 'origin_signature', 'signature'])
            continue
        group.aktiv = False
        group.save(update_fields=['aktiv'])
        # Even an empty override suppresses automatic recreation of the old set.
        replacement = SimilarGroup.objects.create(
            collection=group.collection, topic_id=group.topic_id, kind=group.kind,
            number=group.number, aktiv=bool(after), is_manual=True,
            origin_signature=group.origin_signature or (group.signature if not group.is_manual else ''),
            signature='manual-'+uuid4().hex, question_order=after,
            manual_title=group.manual_title, manual_title_ru=group.manual_title_ru,
        )
        replacement.questions.set(after)
    if new_name:
        group = SimilarGroup.objects.create(collection='mixed', kind='aralash', is_manual=True,
            manual_title=new_name, manual_title_ru=new_name_ru, signature='manual-'+uuid4().hex,
            question_order=[question.pk], number=SimilarGroup.objects.filter(collection='mixed').count()+1)
        group.questions.add(question)
