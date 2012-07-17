from django import forms

from akcrm.crm.models import ContactRecord
from akcrm.search.models import SearchQuery

class ContactForm(forms.ModelForm):

    class Meta:
        model = ContactRecord
        exclude = ("adjustments",)

    akid = forms.CharField(widget=forms.HiddenInput, required=True)
    notes = forms.CharField(widget=forms.Textarea(attrs={"sidebar": "sidebar", "style": "width: 100%"}), required=False)


class SearchSaveForm(forms.Form):
    slug = forms.SlugField(max_length=64)
    title = forms.CharField(max_length=128)
    description = forms.CharField(widget=forms.Textarea(), required=False)
    querystring = forms.CharField()

    def clean(self):
        cleaned_data = super(SearchSaveForm, self).clean()
        slug = cleaned_data['slug']
        try:
            SearchQuery.objects.get(slug=slug)
        except SearchQuery.DoesNotExist:
            pass
        else:
            msg = 'Slug already exists. Please choose another.'
            self._errors['slug'] = self.error_class([msg])
            del cleaned_data['slug']
        return cleaned_data
