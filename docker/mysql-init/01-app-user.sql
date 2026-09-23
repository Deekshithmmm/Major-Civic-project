-- Creates the application's database user with no privileges at all.
--
-- Privileges are granted per table by `python -m app.db.harden`, which runs after the migration
-- because a table-level GRANT cannot name a table that does not exist yet. That script is what
-- makes the audit log append-only on MySQL: unlike PostgreSQL, a MySQL trigger does not fire on
-- TRUNCATE, so the only way to stop one is to withhold the privilege it needs.
--
-- The schema owner (civic_migrate) is created by the image from MYSQL_USER and holds the DDL
-- rights Alembic needs. The application never connects as that user.

CREATE USER IF NOT EXISTS 'civic'@'%' IDENTIFIED BY 'civic_dev_password';

-- Deliberately no GRANT here. Until `app.db.harden` runs, this account can connect and do
-- nothing, which is the correct failure mode: a half-set-up database should refuse work rather
-- than run with the audit log writable.

-- MySQL refuses CREATE TRIGGER from a non-SUPER account while binary logging is on, because a
-- trigger carries a DEFINER and that has replication consequences. SET_USER_ID is the narrow
-- MySQL 8 replacement for SUPER that covers exactly this, and it goes to the schema owner only.
--
-- Binary logging is deliberately left on: for a system whose whole claim is that the record
-- cannot be quietly altered, the binlog is a second, independent trace of every write.
GRANT SET_USER_ID ON *.* TO 'civic_migrate'@'%';
