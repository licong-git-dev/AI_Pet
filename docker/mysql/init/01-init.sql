-- PetPal MySQL 初始化脚本
-- 此脚本在 MySQL 容器首次启动时自动执行

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS petpal
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE petpal;

-- 输出初始化完成信息
SELECT 'PetPal database initialized successfully!' AS message;
