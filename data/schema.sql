-- E-Commerce Database Schema

-- Customers Table
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    country VARCHAR(100),
    city VARCHAR(100),
    registration_date DATE,
    customer_segment VARCHAR(50)
);

-- Categories Table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    parent_category_id INT REFERENCES categories(category_id),
    description TEXT
);

-- Products Table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category_id INT REFERENCES categories(category_id),
    price DECIMAL(10, 2) NOT NULL,
    cost DECIMAL(10, 2),
    stock_quantity INT DEFAULT 0,
    brand VARCHAR(100),
    rating DECIMAL(3, 2),
    created_date DATE
);

-- Orders Table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    order_date TIMESTAMP NOT NULL,
    status VARCHAR(50),
    total_amount DECIMAL(10, 2),
    shipping_address TEXT,
    payment_method VARCHAR(50)
);

-- Order Items Table
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    discount_percent DECIMAL(5, 2) DEFAULT 0,
    subtotal DECIMAL(10, 2)
);

-- Reviews Table
CREATE TABLE reviews (
    review_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    customer_id INT REFERENCES customers(customer_id),
    rating INT CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    review_date TIMESTAMP,
    helpful_count INT DEFAULT 0
);

-- Shipping Table
CREATE TABLE shipping (
    shipping_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    shipping_method VARCHAR(100),
    shipping_cost DECIMAL(10, 2),
    shipped_date TIMESTAMP,
    delivery_date TIMESTAMP,
    tracking_number VARCHAR(100)
);

-- Promotions Table
CREATE TABLE promotions (
    promotion_id SERIAL PRIMARY KEY,
    promotion_name VARCHAR(255),
    discount_type VARCHAR(50),
    discount_value DECIMAL(10, 2),
    start_date DATE,
    end_date DATE,
    category_id INT REFERENCES categories(category_id)
);

-- Create indexes for performance
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_reviews_product ON reviews(product_id);