from django import forms

from akcrm.crm.models import ContactRecord
from akcrm.search.models import SearchQuery

class ContactForm(forms.ModelForm):

    class Meta:
        model = ContactRecord
        exclude = ("adjustments",)

    akid = forms.CharField(widget=forms.HiddenInput, required=True)
    notes = forms.CharField(widget=forms.Textarea(attrs={"sidebar": "sidebar", "style": "width: 100%"}), required=False)


class SearchQueryForm(forms.ModelForm):

    class Meta:
        model = SearchQuery

    querystring = forms.CharField(widget=forms.HiddenInput, required=True)
