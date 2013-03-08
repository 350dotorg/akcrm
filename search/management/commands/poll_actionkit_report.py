from django.core.management.base import BaseCommand
from akcrm.search.models import ActiveReport

class Command(BaseCommand):
    def handle(self, *args, **options):
        reports = ActiveReport.objects.filter(status__isnull=True)
        if not len(reports):
            return False
        report = reports[0]
        report.poll_results()
        print report.status
