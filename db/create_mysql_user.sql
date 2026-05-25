-- Chạy bằng tài khoản root/admin trên MySQL server
CREATE USER IF NOT EXISTS 'atg_app'@'192.168.%' IDENTIFIED BY 'atg_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'192.168.%';
FLUSH PRIVILEGES;
