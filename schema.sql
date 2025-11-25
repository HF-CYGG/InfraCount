CREATE DATABASE IF NOT EXISTS infrared CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE infrared;
CREATE TABLE IF NOT EXISTS device_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    uuid VARCHAR(64),
    in_count INT,
    out_count INT,
    time DATETIME,
    battery_level INT,
    signal_status TINYINT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX IF NOT EXISTS idx_device_data_uuid_time ON device_data (uuid, time);
