# Loaded by Python at startup in every bench process. Makes Postgres behave
# like MariaDB where Frappe and its apps assume MariaDB.

# psycopg2 decodes json and jsonb columns into Python objects, while MariaDB
# returns them as strings. Frappe and its apps are written for strings and
# call json.loads on them, which fails on Postgres (for example for
# DocField.link_filters). Return the raw text, as MariaDB does.
try:
	import psycopg2.extras
except ImportError:
	pass
else:
	psycopg2.extras.register_default_json(globally=True, loads=lambda value: value)
	psycopg2.extras.register_default_jsonb(globally=True, loads=lambda value: value)

# FORCE INDEX and USE INDEX are MySQL-only, and pypika renders them for every
# dialect. ERPNext 16 uses FORCE INDEX in its financial statements (fixed on
# develop, not backported). Postgres has no index hints and its planner picks
# the index anyway, so drop them.
try:
	from pypika.dialects import PostgreSQLQueryBuilder
except ImportError:
	pass
else:
	PostgreSQLQueryBuilder._force_index_sql = lambda self, **kwargs: ""
	PostgreSQLQueryBuilder._use_index_sql = lambda self, **kwargs: ""
