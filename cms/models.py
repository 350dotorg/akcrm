from django.db import models

class AdjustmentRecord(models.Model):

    user = models.ForeignKey("auth.User")
    created_at = models.DateTimeField(auto_now_add=True)

    json = models.TextField(default="{}")

class AllowedTag(models.Model):
    
    ak_tag_id = models.IntegerField(unique=True)
    ak_page_id = models.IntegerField(unique=True)
    tag_name = models.CharField(max_length=300, unique=True)
