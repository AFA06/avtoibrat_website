"""Import the existing library once. Later deploys never overwrite admin edits."""
import json
from pathlib import Path
from django.db import migrations


def seed(apps, schema_editor):
    Topic = apps.get_model('avto', 'LectureTopic')
    Page = apps.get_model('avto', 'LecturePage')
    from avto.lectures import TITLES, DESCRIPTIONS
    alias = schema_editor.connection.alias
    for lang in ('uz', 'ru'):
        data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'lectures' / f'{lang}.json').read_text())
        for deck in data:
            i = deck['number'] - 1
            topic, _ = Topic.objects.using(alias).get_or_create(slug=deck['slug'], defaults={
                'title': TITLES['uz'][i], 'title_kr': TITLES['uz-kr'][i], 'title_ru': TITLES['ru'][i],
                'description': DESCRIPTIONS['uz'][i], 'description_kr': DESCRIPTIONS['uz-kr'][i],
                'description_ru': DESCRIPTIONS['ru'][i], 'order': i, 'published': True,
            })
            Page.objects.using(alias).bulk_create([
                Page(topic=topic, language=lang, title=s['title'], text='\n\n'.join(s['paragraphs']),
                     kind=s['kind'], is_cover=s['number'] < (3 if lang == 'ru' and deck['slug'] == 'service' else 2), source_image=s['image'], source_thumbnail=s['thumbnail'],
                     source_video=s.get('video', ''), order=s['number'], published=True)
                for s in deck['slides']
            ])


class Migration(migrations.Migration):
    dependencies = [('avto', '0040_editable_lectures')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
