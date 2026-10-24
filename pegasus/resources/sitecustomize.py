# Loaded by Python at startup in every bench process.
#
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
