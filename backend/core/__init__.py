# Makes Django's MySQL backend (django.db.backends.mysql) use PyMySQL instead
# of mysqlclient — PyMySQL is pure-Python, so it doesn't need a C compiler or
# system MySQL client headers, which shared/cPanel hosting often can't provide.
# Only exercised when DB_ENGINE=mysql (see settings.py); harmless no-op otherwise.
import pymysql
pymysql.install_as_MySQLdb()
