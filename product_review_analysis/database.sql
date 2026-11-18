
CREATE DATABASE IF NOT EXISTS product_quality_db;

USE product_quality_db;

CREATE TABLE IF NOT EXISTS product_analyses (

    id INT AUTO_INCREMENT PRIMARY KEY,

    product_url VARCHAR(1000) NOT NULL,

    platform VARCHAR(100) NOT NULL,

    average_rating DECIMAL(2,1) NOT NULL,

    rating_count INT NOT NULL,

    classification VARCHAR(20) NOT NULL,

    evidence_level VARCHAR(50) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);
