from django.db import models

class AdjustmentRecord(models.Model):

    user = models.ForeignKey("auth.User")
    created_at = models.DateTimeField(auto_now_add=True)

    json = models.TextField(default="{}")

