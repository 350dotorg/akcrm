from django.db import models
from akcrm.cms.models import AdjustmentRecord

class ContactRecord(models.Model):

    CONTACT_TYPE_CHOICES = (
        ("phone", "Phone call"),
        ("email", "Email"),
        ("sms", "Text message"),
        )
    contact_type = models.CharField(max_length=100, choices=CONTACT_TYPE_CHOICES)

    def contact_type_str(self):
        return dict(self.CONTACT_TYPE_CHOICES)[self.contact_type]

    akid = models.IntegerField(db_index=True)
    user = models.ForeignKey("auth.User", verbose_name="Contacted by")
    
    completed_at = models.DateTimeField(auto_now_add=True)

    RESULT_CHOICES = (
        ("contact",
         "Reached the desired person directly"),
        ("nothome",
         "Not home (but reached another human)"),
        ("voicemail",
         "Reached an answering machine"),
        ("busy",
         "Busy signal"),
        ("outofservice",
         "Number out of service"),
        ("invalid",
         "Wrong number / email bounced"),
        ("noanswer",
         "No answer (e.g. phone kept ringing, or voicemail full)"),
        ("callback",
         "Call back"),
        )
    result = models.CharField(max_length=100, choices=RESULT_CHOICES)

    def result_str(self):
        return dict(self.RESULT_CHOICES)[self.result]

    adjustments = models.ForeignKey(AdjustmentRecord, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return u" ".join((self.user.username, str(self.akid), self.contact_type))

    def to_json(self):
        return dict(
            user=unicode(self.user),
            type=self.contact_type_str(),
            result=self.result_str(),
            akid=self.akid,
            completed_at=self.completed_at,
            notes=self.notes,
            )
