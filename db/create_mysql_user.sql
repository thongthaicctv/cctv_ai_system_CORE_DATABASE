-- Run with root/admin on the MariaDB server.
-- Reset atg_app accounts to mysql_native_password. This avoids MariaDB
-- selecting auth_gssapi_client/unix_socket accounts when PyMySQL connects.

DROP USER IF EXISTS 'atg_app'@'localhost';
DROP USER IF EXISTS 'atg_app'@'127.0.0.1';
DROP USER IF EXISTS 'atg_app'@'192.168.%';
DROP USER IF EXISTS 'atg_app'@'%';

CREATE USER 'atg_app'@'localhost'
    IDENTIFIED VIA mysql_native_password USING PASSWORD('atg_password');
CREATE USER 'atg_app'@'127.0.0.1'
    IDENTIFIED VIA mysql_native_password USING PASSWORD('atg_password');
CREATE USER 'atg_app'@'192.168.%'
    IDENTIFIED VIA mysql_native_password USING PASSWORD('atg_password');
CREATE USER 'atg_app'@'%'
    IDENTIFIED VIA mysql_native_password USING PASSWORD('atg_password');

GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'192.168.%';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'%';
FLUSH PRIVILEGES;
