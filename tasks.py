import os
import datetime
import subprocess
import logging

from django.conf import settings

from celery.schedules import crontab
from celery.task import task, periodic_task

from boto.s3.connection import S3Connection
from boto.s3.key import Key

logger = logging.getLogger()

@periodic_task(run_every=crontab(minute=0, hour=[0, 6, 12, 18]))
def dbbackup():
  try:
    tmp = '/tmp/sentry.sql'


    AWS_ACCESS_KEY_ID = getattr(settings, 'AWS_ACCESS_KEY_ID')
    if not AWS_ACCESS_KEY_ID:
      logger.error('Missing sentry_backup setting AWS_ACCESS_KEY_ID. Please add to your sentry.conf.py')

    AWS_SECRET_ACCESS_KEY = getattr(settings, 'AWS_SECRET_ACCESS_KEY')
    if not AWS_SECRET_ACCESS_KEY:
      logger.error('Missing sentry_backup setting AWS_SECRET_ACCESS_KEY. Please add to your sentry.conf.py')

    BACKUP_BUCKET_NAME = getattr(settings, 'BACKUP_BUCKET_NAME')
    if not BACKUP_BUCKET_NAME:
      logger.error('Missing sentry_backup setting BACKUP_BUCKET_NAME. Please add to your sentry.conf.py')

    user = settings.DATABASES['default']['USER']
    password = settings.DATABASES['default']['PASSWORD']
    host = settings.DATABASES['default']['HOST']
    dbname = settings.DATABASES['default']['NAME']

    if os.path.exists(tmp):
      os.remove(tmp)

    if os.path.exists(tmp + '.gz'):
      os.remove(tmp + '.gz')

    sts = subprocess.call("export PGPASSWORD=%s && pg_dump -U %s -h %s %s > %s && export PGPASSWORD=" % (password, user, host, dbname, tmp), shell=True)
    sts = subprocess.call("gzip -9 %s" % tmp, shell=True)

    conn = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    bucket = conn.get_bucket(BACKUP_BUCKET_NAME)
    now = datetime.datetime.now()
    k = Key(bucket)
    k.key = '%d-%d/%s_%d-%d-%d.sql.gz' % (now.year, now.month, dbname, now.day, now.hour, now.minute)
    k.set_contents_from_filename(tmp + '.gz')
    k.set_acl('private')
  except Exception, e:
    logger.exception(e)