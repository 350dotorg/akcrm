from collections import namedtuple
from django.db import models

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
