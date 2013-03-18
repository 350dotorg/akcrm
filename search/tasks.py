from celery.decorators import task, periodic_task
from akcrm.search.models import ActiveReport

@task
def poll_report(report):
    report.poll_results()
