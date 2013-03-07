from akcrm.actionkit.models import CoreUser
from collections import namedtuple
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

def make_temporary_model(table_name):
    class MyClassMetaclass(models.base.ModelBase):
        def __new__(cls, name, bases, attrs):
            name += str(table_name)
            return models.base.ModelBase.__new__(cls, name, bases, attrs)

    class SearchResult(models.Model):

        __metaclass__ = MyClassMetaclass

        id = models.IntegerField(primary_key=True)
        created_at = models.DateTimeField()
        updated_at = models.DateTimeField()
        email = models.CharField(max_length=255)
        prefix = models.CharField(max_length=765)
        first_name = models.CharField(max_length=765)
        middle_name = models.CharField(max_length=765)
        last_name = models.CharField(max_length=765)

        name = models.CharField(max_length=765)

        suffix = models.CharField(max_length=765)
        password = models.CharField(max_length=765)
        subscription_status = models.CharField(max_length=765)
        address1 = models.CharField(max_length=765)
        address2 = models.CharField(max_length=765)
        city = models.CharField(max_length=765)
        state = models.CharField(max_length=765)
        region = models.CharField(max_length=765)
        postal = models.CharField(max_length=765)
        zip = models.CharField(max_length=25)
        plus4 = models.CharField(max_length=25)
        country = models.CharField(max_length=765)
        source = models.CharField(max_length=765)
        rand_id = models.IntegerField()
        lang_id = models.IntegerField(null=True, blank=True)

        phone = models.CharField(max_length=255, null=True, blank=True)
        campus = models.CharField(max_length=255, null=True, blank=True)

        class Meta:
            db_table = "search_result_" + table_name[:30]
            managed = True

        @models.permalink
        def get_absolute_url(self):
            return ("detail", [self.id], {})

        def get_actionkit_url(self):
            return settings.ACTIONKIT_URL.rstrip("/") + "/admin/core/user/%s/" % self.id

    return SearchResult

class SearchField(models.Model):
    category = models.CharField(max_length=500)
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=500)
    
    def __unicode__(self):
        return "%s (%s: %s)" % (self.name, self.category, self.display_name)


_AgentTag = namedtuple("AgentTag", "name ak_tag_id editable allowed_tag_id")


class AgentTag(_AgentTag):
    def __repr__(self):
        return self.name


class SearchQuery(models.Model):
    """User saved / favorite query"""

    slug = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=128)
    description = models.TextField()
    querystring = models.TextField()

    def __unicode__(self):
        return self.title


class UserSearchQuery(models.Model):
    """Join Users and Search Queries"""

    user = models.ForeignKey(User)
    query = models.ForeignKey(SearchQuery)

from django.template.defaultfilters import slugify
import hashlib

class ActiveReport(models.Model):
    
    query_string = models.CharField(max_length=255, unique=True)
    akid = models.IntegerField(unique=True)
    slug = models.SlugField(max_length=64, unique=True)

    @classmethod
    def slugify(cls, sql):
        hash = hashlib.sha1(sql).hexdigest()
        slug = slugify(hash)
        return slug
