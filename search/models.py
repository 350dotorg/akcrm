from akcrm.actionkit.models import CoreUser
from collections import namedtuple
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

def make_temporary_model(table_name, extra_fields=None):
    class MyClassMetaclass(models.base.ModelBase):
        def __new__(cls, name, bases, attrs):
            name += str(table_name)
            return models.base.ModelBase.__new__(cls, name, bases, attrs)

    class SearchResult(models.Model):

        __metaclass__ = MyClassMetaclass

        _aktivator_uid = models.AutoField(primary_key=True)

        class Meta:
            db_table = table_name[:60]
            managed = True

        @models.permalink
        def get_absolute_url(self):
            return ("detail", [self.id], {})

        def get_actionkit_url(self):
            return settings.ACTIONKIT_URL.rstrip("/") + "/admin/core/user/%s/" % self.id

    if extra_fields:
        for field in extra_fields:
            SearchResult.add_to_class(
                field, models.CharField(max_length=765, null=True, blank=True))
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
from akcrm.actionkit import rest
from itertools import imap
from akcrm.search.utils import grouper

class ActiveReport(models.Model):
    
    query_string = models.TextField(unique=True)
    akid = models.IntegerField(unique=True)
    slug = models.SlugField(max_length=64, unique=True)

    status = models.CharField(max_length=20, null=True, blank=True)
    message = models.TextField(null=True, blank=True)

    local_table = models.CharField(max_length=100, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def results_model(self, extra_fields=None):
        assert self.local_table is not None
        return make_temporary_model(self.local_table, extra_fields=extra_fields)

    @classmethod
    def slugify(cls, sql):
        hash = hashlib.sha1(sql).hexdigest()
        slug = slugify(hash)
        return slug
    
    # @@TODO this should commit transactions during each save()
    def poll_results(self):
        if self.status == "ready":
            return True
        if self.status is not None:
            return False
        self.status = "polling"
        try:
            columns, results = rest.poll_report(self.akid)
        except rest.ReportFailed, e:
            self.status = "failed"
            self.message = str(e.data)
            self.save()
            return False
        except rest.ReportIncomplete, e:
            self.status = None
            self.save()
            return False
        self.status = "loading"
        self.save()
        
        from akcrm.search import sql
        try:
            SearchResult = self.results_model(columns)
            sql.create_model(SearchResult)

            results = imap(
                lambda result: sql.result_to_model(result, SearchResult, columns), 
                results)
            results = (result for result in results if result is not None)
            chunked_models = grouper(results, 1000)

            for chunk in chunked_models:
                SearchResult.objects.using("dummy").bulk_create(
                    (obj for obj in chunk if obj is not None))
        except Exception, e:
            self.status = "exception"
            self.message = str(e)
            self.save()
            raise e

        self.status = "ready" 
        self.save()
        return True
