from django.db import models

class SearchField(models.Model):
    category = models.CharField(max_length=500)
    name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=500)
    
    def __unicode__(self):
        return "%s (%s: %s)" % (self.name, self.category, self.display_name)
