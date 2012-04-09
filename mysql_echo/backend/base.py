from django.db.backends.mysql.base import *
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper
from django.db.backends.mysql.base import DatabaseOperations as MySQLDatabaseOperations

class DatabaseOperations(MySQLDatabaseOperations):
    def last_executed_query(self, cursor, sql, params):
        # With MySQLdb, cursor objects have an (undocumented) "_last_executed" 
        # attribute where the exact query sent to the database is saved. 
        # See MySQLdb/cursors.py in the source distribution. 
        return cursor._last_executed

class DatabaseWrapper(MySQLDatabaseWrapper):

    def __init__(self, *args, **kwargs):
        super(DatabaseWrapper, self).__init__(*args, **kwargs)
        self.ops = DatabaseOperations()

