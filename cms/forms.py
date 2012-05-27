from actionkit import Client
from actionkit.models import CoreTag, CorePage
from django import forms
from django.conf import settings

from akcrm.cms.models import AllowedTag

class AllowedTagForm(forms.Form):

    tag_name = forms.CharField(required=True)

    def clean_tag_name(self):
        tag_name = self.cleaned_data['tag_name'].strip()
        if AllowedTag.objects.filter(tag_name=tag_name).exists():
            raise forms.ValidationError("A tag with this name has already been installed.")
        return tag_name

    def create_core_tag(self, new_tag_name):
        actionkit = Client()
        tag = actionkit.Tag.create(dict(name=new_tag_name))
        return tag['id']

    def create_tag_page(self, tag_id):
        actionkit = Client()
        page = actionkit.ImportPage.create(dict(name="activator_tag_page_%s" % tag_id))
        actionkit.ImportPage.save(dict(id=page['id'], tags=[
                    tag_id, settings.AKTIVATOR_TAG_PAGE_TAG_ID]))
        return page['id']

    def save(self):
        tag_name = self.cleaned_data['tag_name'].strip()
        try:
            core_tag = CoreTag.objects.using("ak").get(name=tag_name)
        except CoreTag.DoesNotExist:
            tag_id = self.create_core_tag(tag_name)
        else:
            tag_id = core_tag.id

        try:
            core_page = CorePage.objects.using("ak").filter(
                pagetags__tag=tag_id).get(pagetags__tag=settings.AKTIVATOR_TAG_PAGE_TAG_ID)
        except CorePage.DoesNotExist:
            page_id = self.create_tag_page(tag_id)
        else:
            page_id = core_page.id

        self.cleaned_data.update({'ak_tag_id': tag_id, 'ak_page_id': page_id})
        return AllowedTag.objects.create(**self.cleaned_data)
