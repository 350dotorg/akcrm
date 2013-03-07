from akcrm.actionkit.models import CoreUser
from collections import namedtuple
from django.db import models
from django.contrib.auth.models import User


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
from base64 import b64encode 

class ActiveReport(models.Model):
    
    query_string = models.CharField(max_length=255, unique=True)
    akid = models.IntegerField(unique=True)
    slug = models.SlugField(max_length=64, unique=True)

    @classmethod
    def slugify(cls, sql):
        return slugify(b64encode(sql))[:63]
