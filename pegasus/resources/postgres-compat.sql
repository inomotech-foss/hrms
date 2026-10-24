-- MariaDB functions that apps use in raw SQL and Frappe does not translate
-- for Postgres. ERPNextSwiss uses IFNULL in about 40 queries.
CREATE OR REPLACE FUNCTION ifnull(anycompatible, anycompatible)
  RETURNS anycompatible
  LANGUAGE sql IMMUTABLE PARALLEL SAFE
  AS 'SELECT COALESCE($1, $2)';
