-- ATG ORDER SYSTEM - MYSQL LAN DATABASE
-- Database dùng chung cho nhiều máy trong mạng LAN nội bộ
-- MySQL 8.x / MariaDB 10.x

CREATE DATABASE IF NOT EXISTS atg_order_system
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE atg_order_system;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_code VARCHAR(100) NOT NULL UNIQUE,
    order_type VARCHAR(30) NOT NULL DEFAULT 'ECOM',
    platform VARCHAR(100),
    shop_name VARCHAR(255),
    customer_name VARCHAR(255),
    customer_phone VARCHAR(50),
    customer_address TEXT,
    total_amount DECIMAL(15,2) DEFAULT 0,
    total_boxes INT DEFAULT 1,
    order_status VARCHAR(50) DEFAULT 'NEW',
    packing_status VARCHAR(50) DEFAULT 'WAITING',
    conveyor_status VARCHAR(50) DEFAULT 'WAITING',
    shipping_status VARCHAR(50) DEFAULT 'WAITING',
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_orders_order_code (order_code),
    INDEX idx_orders_type (order_type),
    INDEX idx_orders_status (order_status),
    INDEX idx_orders_packing_status (packing_status),
    INDEX idx_orders_conveyor_status (conveyor_status),
    INDEX idx_orders_shipping_status (shipping_status),
    INDEX idx_orders_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    order_code VARCHAR(100) NOT NULL,
    sku VARCHAR(100),
    product_name VARCHAR(255),
    quantity INT DEFAULT 1,
    unit VARCHAR(50),
    unit_price DECIMAL(15,2) DEFAULT 0,
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    INDEX idx_order_items_order_id (order_id),
    INDEX idx_order_items_order_code (order_code),
    INDEX idx_order_items_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS employees (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    employee_code VARCHAR(100) NOT NULL UNIQUE,
    employee_name VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    phone VARCHAR(50),
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_employees_code (employee_code),
    INDEX idx_employees_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'STAFF',
    is_active TINYINT DEFAULT 1,
    last_login_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_username (username),
    INDEX idx_users_employee_code (employee_code),
    INDEX idx_users_role (role),
    INDEX idx_users_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS packing_sessions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    order_code VARCHAR(100) NOT NULL,
    legacy_session_id BIGINT,
    session_code VARCHAR(100),
    packing_type VARCHAR(30) DEFAULT 'ECOM',
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    scanner_id VARCHAR(100),
    station_id VARCHAR(100),
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    status VARCHAR(50) DEFAULT 'PACKING',
    total_boxes INT DEFAULT 1,
    total_items INT DEFAULT 0,
    note TEXT,
    CONSTRAINT fk_packing_sessions_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    UNIQUE KEY uk_packing_legacy_session (legacy_session_id),
    INDEX idx_packing_sessions_order_id (order_id),
    INDEX idx_packing_sessions_order_code (order_code),
    INDEX idx_packing_sessions_scanner (scanner_id),
    INDEX idx_packing_sessions_status (status),
    INDEX idx_packing_sessions_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS packing_boxes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    order_code VARCHAR(100) NOT NULL,
    packing_session_id BIGINT,
    box_code VARCHAR(150) NOT NULL UNIQUE,
    box_index INT DEFAULT 1,
    total_boxes INT DEFAULT 1,
    weight DECIMAL(10,2),
    length DECIMAL(10,2),
    width DECIMAL(10,2),
    height DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'PACKED',
    conveyor_checked_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_packing_boxes_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_packing_boxes_session FOREIGN KEY (packing_session_id) REFERENCES packing_sessions(id) ON DELETE SET NULL,
    INDEX idx_packing_boxes_order_id (order_id),
    INDEX idx_packing_boxes_order_code (order_code),
    INDEX idx_packing_boxes_box_code (box_code),
    INDEX idx_packing_boxes_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS packing_videos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT,
    order_code VARCHAR(100) NOT NULL,
    packing_session_id BIGINT,
    box_code VARCHAR(150),
    session_type VARCHAR(50),
    video_type VARCHAR(30) DEFAULT 'ECOM',
    item_report_enabled TINYINT DEFAULT 0,
    item_count INT DEFAULT 0,
    scanner_id VARCHAR(100),
    camera_id VARCHAR(100),
    camera_name VARCHAR(255),
    storage_code VARCHAR(100),
    file_path TEXT NOT NULL,
    relative_path TEXT,
    file_name VARCHAR(255),
    file_size BIGINT DEFAULT 0,
    duration_seconds DECIMAL(10,2) DEFAULT 0,
    start_time DATETIME,
    end_time DATETIME,
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    result VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_packing_videos_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_packing_videos_session FOREIGN KEY (packing_session_id) REFERENCES packing_sessions(id) ON DELETE SET NULL,
    INDEX idx_packing_videos_order_id (order_id),
    INDEX idx_packing_videos_order_code (order_code),
    INDEX idx_packing_videos_video_type (video_type),
    INDEX idx_packing_videos_item_report (item_report_enabled),
    INDEX idx_packing_videos_box_code (box_code),
    INDEX idx_packing_videos_scanner_id (scanner_id),
    INDEX idx_packing_videos_camera_id (camera_id),
    INDEX idx_packing_videos_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE packing_videos
    ADD COLUMN IF NOT EXISTS video_type VARCHAR(30) DEFAULT 'ECOM' AFTER session_type,
    ADD COLUMN IF NOT EXISTS item_report_enabled TINYINT DEFAULT 0 AFTER video_type,
    ADD COLUMN IF NOT EXISTS item_count INT DEFAULT 0 AFTER item_report_enabled;

CREATE INDEX IF NOT EXISTS idx_packing_videos_video_type ON packing_videos (video_type);
CREATE INDEX IF NOT EXISTS idx_packing_videos_item_report ON packing_videos (item_report_enabled);

CREATE OR REPLACE VIEW ecom_packing_videos AS
SELECT *
FROM packing_videos
WHERE video_type = 'ECOM';

CREATE OR REPLACE VIEW wholesale_packing_videos AS
SELECT *
FROM packing_videos
WHERE video_type = 'WHOLESALE';

CREATE TABLE IF NOT EXISTS conveyor_checks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT,
    order_code VARCHAR(100) NOT NULL,
    box_code VARCHAR(150),
    conveyor_id VARCHAR(100),
    station_id VARCHAR(100),
    scan_code VARCHAR(150) NOT NULL,
    scan_type VARCHAR(50) DEFAULT 'BARCODE',
    result VARCHAR(50) DEFAULT 'OK',
    message TEXT,
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    image_path TEXT,
    video_path TEXT,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_conveyor_checks_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    INDEX idx_conveyor_checks_order_id (order_id),
    INDEX idx_conveyor_checks_order_code (order_code),
    INDEX idx_conveyor_checks_box_code (box_code),
    INDEX idx_conveyor_checks_scan_code (scan_code),
    INDEX idx_conveyor_checks_result (result),
    INDEX idx_conveyor_checks_checked_at (checked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wholesale_box_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    master_order_id BIGINT,
    master_order_code VARCHAR(100) NOT NULL,
    child_order_id BIGINT,
    child_order_code VARCHAR(100) NOT NULL,
    packing_session_id BIGINT,
    box_code VARCHAR(150),
    scan_index INT DEFAULT 1,
    scan_status VARCHAR(50) DEFAULT 'PACKED',
    is_deleted TINYINT DEFAULT 0,
    deleted_at DATETIME,
    deleted_reason TEXT,
    scanner_id VARCHAR(100),
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_wholesale_box_items_master_order FOREIGN KEY (master_order_id) REFERENCES orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_wholesale_box_items_child_order FOREIGN KEY (child_order_id) REFERENCES orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_wholesale_box_items_session FOREIGN KEY (packing_session_id) REFERENCES packing_sessions(id) ON DELETE SET NULL,
    INDEX idx_wholesale_box_items_master (master_order_code),
    INDEX idx_wholesale_box_items_child (child_order_code),
    INDEX idx_wholesale_box_items_box_code (box_code),
    INDEX idx_wholesale_box_items_session (packing_session_id),
    INDEX idx_wholesale_box_items_status (scan_status),
    INDEX idx_wholesale_box_items_scanned_at (scanned_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS packing_small_packages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT,
    order_code VARCHAR(100) NOT NULL,
    packing_session_id BIGINT,
    legacy_item_id BIGINT,
    small_package_code VARCHAR(150) NOT NULL,
    scan_index INT DEFAULT 1,
    scan_status VARCHAR(50) DEFAULT 'PACKED',
    is_deleted TINYINT DEFAULT 0,
    deleted_at DATETIME,
    deleted_reason TEXT,
    scanner_id VARCHAR(100),
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_packing_small_packages_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_packing_small_packages_session FOREIGN KEY (packing_session_id) REFERENCES packing_sessions(id) ON DELETE SET NULL,
    INDEX idx_packing_small_packages_order_code (order_code),
    INDEX idx_packing_small_packages_code (small_package_code),
    INDEX idx_packing_small_packages_session (packing_session_id),
    INDEX idx_packing_small_packages_deleted (is_deleted),
    INDEX idx_packing_small_packages_scanned_at (scanned_at),
    INDEX idx_packing_small_packages_legacy (legacy_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wholesale_handover_checks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    master_order_id BIGINT,
    master_order_code VARCHAR(100) NOT NULL,
    scanned_code VARCHAR(150) NOT NULL,
    matched_child_order_code VARCHAR(100),
    packing_session_id BIGINT,
    delivery_scanner_id VARCHAR(100),
    employee_code VARCHAR(100),
    employee_name VARCHAR(255),
    result VARCHAR(50) NOT NULL,
    message TEXT,
    video_path TEXT,
    image_path TEXT,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wholesale_handover_master_order FOREIGN KEY (master_order_id) REFERENCES orders(id) ON DELETE SET NULL,
    CONSTRAINT fk_wholesale_handover_session FOREIGN KEY (packing_session_id) REFERENCES packing_sessions(id) ON DELETE SET NULL,
    INDEX idx_wholesale_handover_master (master_order_code),
    INDEX idx_wholesale_handover_scanned_code (scanned_code),
    INDEX idx_wholesale_handover_result (result),
    INDEX idx_wholesale_handover_checked_at (checked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS carriers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    carrier_code VARCHAR(100) NOT NULL UNIQUE,
    carrier_name VARCHAR(255) NOT NULL,
    api_base_url TEXT,
    api_type VARCHAR(100),
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_carriers_code (carrier_code),
    INDEX idx_carriers_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS shipments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    order_code VARCHAR(100) NOT NULL,
    carrier_code VARCHAR(100),
    carrier_name VARCHAR(255),
    tracking_code VARCHAR(150) NOT NULL UNIQUE,
    shipping_status VARCHAR(50) DEFAULT 'CREATED',
    pickup_time DATETIME,
    delivered_time DATETIME,
    receiver_name VARCHAR(255),
    receiver_phone VARCHAR(50),
    last_api_sync DATETIME,
    raw_last_status VARCHAR(255),
    sync_enabled TINYINT DEFAULT 1,
    sync_error_count INT DEFAULT 0,
    last_sync_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_shipments_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    INDEX idx_shipments_order_id (order_id),
    INDEX idx_shipments_order_code (order_code),
    INDEX idx_shipments_tracking_code (tracking_code),
    INDEX idx_shipments_status (shipping_status),
    INDEX idx_shipments_sync (sync_enabled, shipping_status, last_api_sync)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS shipment_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    shipment_id BIGINT NOT NULL,
    order_code VARCHAR(100) NOT NULL,
    tracking_code VARCHAR(150) NOT NULL,
    carrier_code VARCHAR(100),
    event_time DATETIME,
    event_status VARCHAR(100),
    event_location VARCHAR(255),
    event_description TEXT,
    raw_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_shipment_events_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
    INDEX idx_shipment_events_shipment_id (shipment_id),
    INDEX idx_shipment_events_order_code (order_code),
    INDEX idx_shipment_events_tracking_code (tracking_code),
    INDEX idx_shipment_events_event_time (event_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS delivery_assignments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    shipment_id BIGINT,
    order_id BIGINT,
    order_code VARCHAR(100) NOT NULL,
    tracking_code VARCHAR(150),
    assigned_to_code VARCHAR(100),
    assigned_to_name VARCHAR(255),
    assigned_by_code VARCHAR(100),
    assigned_by_name VARCHAR(255),
    assignment_status VARCHAR(50) DEFAULT 'ASSIGNED',
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    accepted_at DATETIME,
    completed_at DATETIME,
    note TEXT,
    CONSTRAINT fk_delivery_assignments_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE SET NULL,
    CONSTRAINT fk_delivery_assignments_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    INDEX idx_delivery_assignments_order_code (order_code),
    INDEX idx_delivery_assignments_tracking_code (tracking_code),
    INDEX idx_delivery_assignments_assigned_to (assigned_to_code),
    INDEX idx_delivery_assignments_status (assignment_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS delivery_confirmations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    shipment_id BIGINT,
    order_id BIGINT,
    order_code VARCHAR(100) NOT NULL,
    tracking_code VARCHAR(150),
    receiver_name VARCHAR(255),
    receiver_phone VARCHAR(50),
    receiver_position VARCHAR(100),
    delivered_by_code VARCHAR(100),
    delivered_by_name VARCHAR(255),
    delivery_result VARCHAR(50) DEFAULT 'DELIVERED',
    proof_image_path TEXT,
    signature_image_path TEXT,
    gps_lat DECIMAL(10,7),
    gps_lng DECIMAL(10,7),
    note TEXT,
    confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_delivery_confirmations_shipment FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE SET NULL,
    CONSTRAINT fk_delivery_confirmations_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    INDEX idx_delivery_confirmations_order_code (order_code),
    INDEX idx_delivery_confirmations_tracking_code (tracking_code),
    INDEX idx_delivery_confirmations_delivered_by (delivered_by_code),
    INDEX idx_delivery_confirmations_confirmed_at (confirmed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS api_sync_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    provider VARCHAR(100),
    api_name VARCHAR(100),
    order_code VARCHAR(100),
    tracking_code VARCHAR(150),
    request_url TEXT,
    request_body JSON,
    response_body JSON,
    status_code INT,
    is_success TINYINT DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_api_sync_logs_provider (provider),
    INDEX idx_api_sync_logs_order_code (order_code),
    INDEX idx_api_sync_logs_tracking_code (tracking_code),
    INDEX idx_api_sync_logs_success (is_success),
    INDEX idx_api_sync_logs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS api_outbox (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    order_code VARCHAR(100),
    tracking_code VARCHAR(150),
    payload JSON,
    status VARCHAR(50) DEFAULT 'PENDING',
    retry_count INT DEFAULT 0,
    last_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_api_outbox_status (status),
    INDEX idx_api_outbox_task_type (task_type),
    INDEX idx_api_outbox_order_code (order_code),
    INDEX idx_api_outbox_tracking_code (tracking_code),
    INDEX idx_api_outbox_retry (status, retry_count, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mobile_sync_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    employee_code VARCHAR(100),
    device_id VARCHAR(255),
    app_version VARCHAR(50),
    client_request_id VARCHAR(100),
    action_type VARCHAR(100),
    order_code VARCHAR(100),
    tracking_code VARCHAR(150),
    request_data JSON,
    response_data JSON,
    ip_address VARCHAR(100),
    is_success TINYINT DEFAULT 1,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_mobile_client_request_id (client_request_id),
    INDEX idx_mobile_sync_logs_user_id (user_id),
    INDEX idx_mobile_sync_logs_employee_code (employee_code),
    INDEX idx_mobile_sync_logs_action_type (action_type),
    INDEX idx_mobile_sync_logs_order_code (order_code),
    INDEX idx_mobile_sync_logs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS web_index_orders (
    order_code VARCHAR(100) PRIMARY KEY,
    order_id BIGINT,
    order_type VARCHAR(30),
    platform VARCHAR(100),
    shop_name VARCHAR(255),
    customer_name VARCHAR(255),
    customer_phone VARCHAR(50),
    total_boxes INT DEFAULT 1,
    total_items INT DEFAULT 0,
    packed_boxes INT DEFAULT 0,
    packed_children INT DEFAULT 0,
    video_count INT DEFAULT 0,
    last_video_path TEXT,
    order_status VARCHAR(50),
    packing_status VARCHAR(50),
    conveyor_status VARCHAR(50),
    shipping_status VARCHAR(50),
    carrier_code VARCHAR(100),
    carrier_name VARCHAR(255),
    tracking_code VARCHAR(150),
    raw_last_status VARCHAR(255),
    last_packed_at DATETIME,
    last_conveyor_check_at DATETIME,
    last_shipping_event_at DATETIME,
    last_handover_at DATETIME,
    last_sync_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_web_index_order_id (order_id),
    INDEX idx_web_index_type (order_type),
    INDEX idx_web_index_packing_status (packing_status),
    INDEX idx_web_index_conveyor_status (conveyor_status),
    INDEX idx_web_index_shipping_status (shipping_status),
    INDEX idx_web_index_tracking_code (tracking_code),
    INDEX idx_web_index_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS web_index_queue (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_code VARCHAR(100) NOT NULL,
    action_type VARCHAR(100) DEFAULT 'REFRESH_ORDER',
    payload JSON,
    status VARCHAR(50) DEFAULT 'PENDING',
    retry_count INT DEFAULT 0,
    last_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_web_index_queue_status (status, retry_count, created_at),
    INDEX idx_web_index_queue_order_code (order_code),
    INDEX idx_web_index_queue_action (action_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    app_name VARCHAR(100),
    event_type VARCHAR(100),
    level VARCHAR(30) DEFAULT 'INFO',
    order_code VARCHAR(100),
    message TEXT,
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_app_events_app_name (app_name),
    INDEX idx_app_events_level (level),
    INDEX idx_app_events_order_code (order_code),
    INDEX idx_app_events_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS system_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value TEXT,
    note TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_instances (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    app_name VARCHAR(100) NOT NULL,
    instance_id VARCHAR(100) NOT NULL UNIQUE,
    machine_name VARCHAR(255),
    ip_address VARCHAR(100),
    status VARCHAR(50) DEFAULT 'ONLINE',
    last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_app_instances_app_name (app_name),
    INDEX idx_app_instances_status (status),
    INDEX idx_app_instances_heartbeat (last_heartbeat)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS storage_locations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    storage_code VARCHAR(100) NOT NULL UNIQUE,
    storage_name VARCHAR(255),
    storage_type VARCHAR(50) DEFAULT 'NETWORK',
    base_path TEXT NOT NULL,
    machine_name VARCHAR(255),
    ip_address VARCHAR(100),
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_storage_locations_code (storage_code),
    INDEX idx_storage_locations_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO carriers (carrier_code, carrier_name, api_type, is_active) VALUES
('INTERNAL', 'Giao hàng nội bộ', 'MANUAL', 1),
('GHN', 'Giao Hàng Nhanh', 'API', 1),
('GHTK', 'Giao Hàng Tiết Kiệm', 'API', 1),
('VIETTELPOST', 'Viettel Post', 'API', 1),
('JT', 'J&T Express', 'API', 1),
('SPX', 'Shopee Express', 'API', 1);

INSERT IGNORE INTO system_settings (setting_key, setting_value, note) VALUES
('database_version', '1.1.0', 'ATG Order System MySQL LAN schema'),
('company_name', 'ATG SOLUTION', 'Tên công ty'),
('default_order_type', 'ECOM', 'Loại đơn mặc định');

UPDATE system_settings
SET setting_value='1.1.0',
    note='ATG Order System MySQL LAN schema'
WHERE setting_key='database_version';

SET FOREIGN_KEY_CHECKS = 1;
