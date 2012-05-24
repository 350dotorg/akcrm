from django import forms

from akcrm.crm.models import ContactRecord

class ContactForm(forms.ModelForm):

    class Meta:
        model = ContactRecord
        exclude = ("adjustments",)

    akid = forms.CharField(widget=forms.HiddenInput, required=True)
    notes = forms.CharField(widget=forms.Textarea(attrs={"sidebar": "sidebar", "style": "width: 100%"}), required=False)
    
