-- MariaDB functions that apps use in raw SQL and Frappe does not translate
-- for Postgres. Applied on every start.

-- ERPNextSwiss uses IFNULL in about 40 queries.
CREATE OR REPLACE FUNCTION ifnull(anycompatible, anycompatible)
  RETURNS anycompatible
  LANGUAGE sql IMMUTABLE PARALLEL SAFE
  AS 'SELECT COALESCE($1, $2)';

-- ERPNext reports (Sales Order Analysis, Inactive Customers, Supplier
-- Scorecard, ...). MariaDB returns whole days between the two dates.
CREATE OR REPLACE FUNCTION datediff(timestamp, timestamp)
  RETURNS integer
  LANGUAGE sql IMMUTABLE PARALLEL SAFE
  AS 'SELECT $1::date - $2::date';

CREATE OR REPLACE FUNCTION curdate()
  RETURNS date
  LANGUAGE sql STABLE PARALLEL SAFE
  AS 'SELECT CURRENT_DATE';

-- ERPNext item search, Payment Entry, POS Register. MariaDB's IF takes a
-- boolean or a number as its condition.
CREATE OR REPLACE FUNCTION "if"(boolean, anycompatible, anycompatible)
  RETURNS anycompatible
  LANGUAGE sql IMMUTABLE PARALLEL SAFE
  AS 'SELECT CASE WHEN $1 THEN $2 ELSE $3 END';

CREATE OR REPLACE FUNCTION "if"(numeric, anycompatible, anycompatible)
  RETURNS anycompatible
  LANGUAGE sql IMMUTABLE PARALLEL SAFE
  AS 'SELECT CASE WHEN $1 <> 0 THEN $2 ELSE $3 END';
