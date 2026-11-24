from django import forms
from .lecture_models import LectureTopic, LecturePage


class TopicForm(forms.ModelForm):
    class Meta:
        model = LectureTopic
        fields = ('title', 'title_kr', 'title_ru', 'description', 'description_kr', 'description_ru', 'published')
        widgets = {key: forms.Textarea(attrs={'rows': 2}) for key in ('description', 'description_kr', 'description_ru')}


class PageForm(forms.ModelForm):
    remove_video = forms.BooleanField(label='Hozirgi videoni olib tashlash', required=False)

    class Meta:
        model = LecturePage
        fields = ('title', 'text', 'kind', 'image', 'video', 'is_cover', 'published')
        widgets = {'text': forms.Textarea(attrs={'rows': 8}), 'image': forms.FileInput(attrs={'accept': 'image/png,image/jpeg,image/webp'}), 'video': forms.FileInput(attrs={'accept': 'video/mp4'})}
        help_texts = {'text': 'Har bir yangi abzatsni yangi qatordan yozing.', 'image': 'PNG, JPG yoki WEBP, 10 MB gacha. Bo‘sh qoldirsangiz, eski rasm qoladi.'}

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and getattr(image, 'size', 0) > 10 * 1024 * 1024:
            raise forms.ValidationError('Rasm 10 MB dan oshmasligi kerak.')
        if image and getattr(image, 'content_type', '') and image.image.format not in ('PNG', 'JPEG', 'WEBP'):
            raise forms.ValidationError('PNG, JPG yoki WEBP rasm tanlang.')
        if image and hasattr(image, 'image') and image.image.width * image.image.height > 25_000_000:
            raise forms.ValidationError('Rasm 25 megapikseldan oshmasligi kerak.')
        return image

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if video and hasattr(video, 'content_type'):
            if video.size > 30 * 1024 * 1024 or not video.name.lower().endswith('.mp4'):
                raise forms.ValidationError('Video MP4 formatida, 30 MB gacha bo‘lishi kerak.')
            head = video.read(32); video.seek(0)
            if b'ftyp' not in head:
                raise forms.ValidationError('MP4 video fayli yaroqsiz.')
        return video

    def clean(self):
        data = super().clean()
        if not data.get('image') and not self.instance.source_image:
            self.add_error('image', 'Sahifa rasmini tanlang.')
        return data


class MultipleInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFiles(forms.FileField):
    def clean(self, data, initial=None):
        return [super(MultipleFiles, self).clean(item, initial) for item in (data if isinstance(data, (list, tuple)) else [data])]


class ImportForm(forms.Form):
    files = MultipleFiles(label='PDF yoki sahifa rasmlari', widget=MultipleInput(attrs={'accept': '.pdf,.png,.jpg,.jpeg,.webp'}))
    def clean_files(self):
        files = self.cleaned_data['files']
        if len(files) > 100 or sum(f.size for f in files) > 50 * 1024 * 1024:
            raise forms.ValidationError('Bir martada 100 tagacha fayl, jami 50 MB gacha yuklang.')
        if any(not f.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.webp')) for f in files):
            raise forms.ValidationError('PDF, PNG, JPG yoki WEBP tanlang. PowerPoint faylini avval PDF sifatida saqlang.')
        return files
