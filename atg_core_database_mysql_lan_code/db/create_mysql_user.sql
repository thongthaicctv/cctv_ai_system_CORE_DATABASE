-- Chạy bằng tài khoản root/admin MySQL.
-- Đổi mật khẩu trước khi triển khai thực tế.

CREATE USER IF NOT EXISTS 'atg_app'@'192.168.%' IDENTIFIED BY 'atg_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'192.168.%';

CREATE USER IF NOT EXISTS 'atg_app'@'localhost' IDENTIFIED BY 'atg_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON atg_order_system.* TO 'atg_app'@'localhost';

FLUSH PRIVILEGES;
