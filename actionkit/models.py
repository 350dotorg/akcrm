from django.db import models


class CoreLanguage(models.Model):
    name = models.TextField()
    class Meta:
        db_table = u'core_language'
        managed = False


class CoreUser(models.Model):
    id = models.IntegerField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    email = models.CharField(max_length=255)
    prefix = models.CharField(max_length=765)
    first_name = models.CharField(max_length=765)
    middle_name = models.CharField(max_length=765)
    last_name = models.CharField(max_length=765)
    suffix = models.CharField(max_length=765)
    password = models.CharField(max_length=765)
    subscription_status = models.CharField(max_length=765)
    address1 = models.CharField(max_length=765)
    address2 = models.CharField(max_length=765)
    city = models.CharField(max_length=765)
    state = models.CharField(max_length=765)
    region = models.CharField(max_length=765)
    postal = models.CharField(max_length=765)
    zip = models.CharField(max_length=15)
    plus4 = models.CharField(max_length=12)
    country = models.CharField(max_length=765)
    source = models.CharField(max_length=765)
    lang = models.ForeignKey(CoreLanguage, null=True, blank=True, related_name="users")
    rand_id = models.IntegerField()
    class Meta:
        db_table = u'core_user'
        managed = False

    @models.permalink
    def get_absolute_url(self):
        return ("detail", [self.pk], {})

    def __unicode__(self):
        return u"%s %s" % (self.first_name, self.last_name)

    def formatted_address(self):
        fields = [
            self.address1,
            self.address2,
            self.city,
            self.state,
            self.region,
            self.zip,
            self.country
            ]
        return u", ".join(field for field in fields
                          if field and field.strip())

    def custom_fields(self):
        return {}
        fields = {}
        for field in self.fields.all():
            fields.setdefault(field.name, []).append(field.value)
        return fields

    def to_json(self):
        agent = self
        return dict(
            name=unicode(agent),
            email=agent.email,
            phone=agent.phone or '',
            zip=agent.zip,
            address=agent.formatted_address(),
            skills=agent.custom_fields().get('skills', []),
            campus=agent.custom_fields().get('campus', None),
            id=agent.id,
            )

class CoreLocation(models.Model):
    user = models.OneToOneField(CoreUser, related_name="location", primary_key=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    us_district = models.TextField(null=True, blank=True)

    class Meta:
        db_table = u'core_location'
        managed = False
    
class CorePhone(models.Model):
    id = models.IntegerField(primary_key=True)
    user = models.ForeignKey(CoreUser, related_name="phones")
    type = models.CharField(max_length=25)
    phone = models.CharField(max_length=25)
    normalized_phone = models.CharField(max_length=25)
    class Meta:
        db_table = u'core_phone'
        managed = False

    def __unicode__(self):
        if self.phone:
            return u"%s%s" % (self.phone, (
                    self.type and " (%s)" % self.type or ''))
        return u''

class CorePage(models.Model):
    id = models.IntegerField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    title = models.CharField(max_length=765)
    name = models.CharField(max_length=765)
    #hosted_with = models.ForeignKey(CoreHostingplatform)
    url = models.CharField(max_length=765)
    type = models.CharField(max_length=765)
    #lang = models.ForeignKey(CoreLanguage, null=True, blank=True)
    #english_version = models.ForeignKey('self', null=True, blank=True)
    goal = models.IntegerField(null=True, blank=True)
    goal_type = models.CharField(max_length=765)
    status = models.CharField(max_length=765)
    #list = models.ForeignKey(CoreList)
    hidden = models.IntegerField()
    class Meta:
        db_table = u'core_page'
        managed = False

    def __unicode__(self):
        return u"%s (%s, %s, %s)" % (self.title, self.name, self.id, self.type)

class CoreAction(models.Model):
    id = models.IntegerField(primary_key=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    user = models.ForeignKey(CoreUser,related_name="actions")
    #mailing = models.ForeignKey(CoreMailing, null=True, blank=True,related_name="related_mailer")
    page = models.ForeignKey(CorePage)
    link = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=765)
    opq_id = models.CharField(max_length=765)
    created_user = models.IntegerField()
    subscribed_user = models.IntegerField()
    #referring_user = models.ForeignKey(CoreUser, null=True, blank=True)
    #referring_mailing = models.ForeignKey(CoreMailing, null=True, blank=True)
    status = models.CharField(max_length=765)
    taf_emails_sent = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'core_action'
        managed = False

    def to_json(self):
        return dict(
            created_at=self.created_at,
            page_title=self.page.title,
            )
        
class CoreActionField(models.Model):
    parent = models.ForeignKey(CoreAction, related_name='fields')
    name = models.TextField()
    value = models.TextField()
    class Meta:
        db_table = 'core_actionfield'
        managed = False

class CoreUserField(models.Model):
    parent = models.ForeignKey(CoreUser, related_name='fields')
    name = models.TextField()
    value = models.TextField()
    class Meta:
        db_table = 'core_userfield'
        managed = False

class CoreTag(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    class Meta:
        db_table = u'core_tag'
        managed = False
    
class CorePageTag(models.Model):
    id = models.IntegerField(primary_key=True)
    page = models.ForeignKey(CorePage, related_name="pagetags")
    tag = models.ForeignKey(CoreTag, related_name="pagetags")
    class Meta:
        db_table = u'core_page_tags'
        managed = False

class CoreOrder(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    user = models.ForeignKey(CoreUser, related_name="orders")
    action = models.ForeignKey(CoreAction, related_name="orders")
    total = models.FloatField(max_length=255, unique=True)
    status = models.CharField(max_length=255)
    class Meta:
        db_table = u'core_order'
        managed = False

class CoreMailing(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    html = models.TextField()
    text = models.TextField()
    status = models.CharField(max_length=255)
    class Meta:
        db_table = u'core_mailing'
        managed = False

class CoreMailingSubject(models.Model):
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    text = models.CharField(max_length=255)
    mailing = models.ForeignKey(CoreMailing)
    class Meta:
        db_table = u'core_mailingsubject'
        managed = False

class CoreClickUrl(models.Model):
    id = models.IntegerField(primary_key=True)
    url = models.CharField(max_length=255)
    created_at = models.DateTimeField()
    page = models.ForeignKey(CorePage)
    class Meta:
        db_table = u'core_clickurl'
        managed = False

class CoreClick(models.Model):
    clickurl = models.ForeignKey(CoreClickUrl)
    user = models.ForeignKey(CoreUser)
    mailing = models.ForeignKey(CoreMailing)
    link_number = models.IntegerField(null=True)
    source = models.CharField(max_length=255)
    referring_user_id = models.IntegerField(null=True)
    created_at = models.DateTimeField(primary_key=True)
    class Meta:
        db_table = u'core_click'
        managed = False

class CoreOpen(models.Model):
    user = models.ForeignKey(CoreUser, related_name="email_opens")
    mailing = models.ForeignKey(CoreMailing)
    created_at = models.DateTimeField(primary_key=True)
    class Meta:
        db_table = u'core_open'
        managed = False

class CoreUserMailing(models.Model):
    mailing = models.ForeignKey(CoreMailing)
    user = models.ForeignKey(CoreUser)
    subject = models.ForeignKey(CoreMailingSubject)
    created_at = models.DateTimeField(primary_key=True)    
    class Meta:
        db_table = u'core_usermailing'
        managed = False

    def to_json(self):
        return dict(
            created_at=self.created_at,
            subject_text=self.subject.text,
            )

from django.db import connections

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def opens_by_user(user):
    cursor = connections['ak'].cursor()
    sql = """
SELECT open.mailing_id, open.created_at,
       subject.text AS subject_text,
       mailing.created_at AS mailed_at
FROM core_open open
LEFT JOIN core_mailing mailing
  ON mailing.id=open.mailing_id
LEFT JOIN core_usermailing usermailing
  ON open.mailing_id=usermailing.mailing_id 
  AND open.user_id=usermailing.user_id
LEFT JOIN core_mailingsubject subject 
  ON subject.id=usermailing.subject_id
WHERE open.user_id=%s
ORDER BY created_at DESC"""
    cursor.execute(sql, [user.id])
    return dictfetchall(cursor)

def clicks_by_user(user):
    cursor = connections['ak'].cursor()
    sql = """
SELECT click.mailing_id, click.created_at, 
       subject.text AS subject_text,
       mailing.created_at AS mailed_at
FROM core_click click
LEFT JOIN core_mailing mailing 
  ON mailing.id=click.mailing_id
LEFT JOIN core_usermailing usermailing
  ON click.mailing_id=usermailing.mailing_id 
  AND click.user_id=usermailing.user_id
LEFT JOIN core_mailingsubject subject 
  ON subject.id=usermailing.subject_id
WHERE click.user_id=%s
ORDER BY created_at DESC"""
    cursor.execute(sql, [user.id])
    return dictfetchall(cursor)

def mailings_by_user(user):
    cursor = connections['ak'].cursor()
    sql = """
SELECT usermailing.id as usermailing_id,
       mailing.id as id,
       mailing.created_at as mailed_at,
       click.created_at as clicked_at, 
       subject.text AS subject_text,
       open.created_at as opened_at
FROM core_usermailing usermailing
LEFT JOIN core_mailingsubject subject 
  ON subject.id=usermailing.subject_id
LEFT JOIN core_mailing mailing
  ON mailing.id=usermailing.mailing_id
LEFT JOIN core_click click
  ON click.mailing_id=usermailing.mailing_id
  AND click.user_id=usermailing.user_id
LEFT JOIN core_open open
  ON open.mailing_id=usermailing.mailing_id
  AND open.user_id=usermailing.user_id
WHERE usermailing.user_id=%s
ORDER BY usermailing.created_at DESC"""
    cursor.execute(sql, [user.id])
    return dictfetchall(cursor)

