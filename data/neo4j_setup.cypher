// Neo4j Graph Database Setup for E-Commerce

// Create Customers
CREATE (c:Customer {
    customer_id: 1,
    name: 'John Doe',
    email: 'john@example.com',
    country: 'USA',
    segment: 'Premium'
});

// Create Categories
CREATE (cat1:Category {category_id: 1, name: 'Electronics'})
CREATE (cat2:Category {category_id: 2, name: 'Laptops'})
CREATE (cat3:Category {category_id: 3, name: 'Smartphones'})
CREATE (cat4:Category {category_id: 4, name: 'Clothing'})
CREATE (cat5:Category {category_id: 5, name: 'Books'});

// Create hierarchy
MATCH (parent:Category {name: 'Electronics'}), (child:Category {name: 'Laptops'})
CREATE (child)-[:SUBCATEGORY_OF]->(parent);

MATCH (parent:Category {name: 'Electronics'}), (child:Category {name: 'Smartphones'})
CREATE (child)-[:SUBCATEGORY_OF]->(parent);

// Create Products
CREATE (p1:Product {
    product_id: 1,
    name: 'MacBook Pro',
    price: 1999.99,
    stock: 50,
    brand: 'Apple',
    rating: 4.8
})
CREATE (p2:Product {
    product_id: 2,
    name: 'iPhone 15',
    price: 999.99,
    stock: 100,
    brand: 'Apple',
    rating: 4.7
});

// Link Products to Categories
MATCH (p:Product {product_id: 1}), (c:Category {name: 'Laptops'})
CREATE (p)-[:BELONGS_TO]->(c);

MATCH (p:Product {product_id: 2}), (c:Category {name: 'Smartphones'})
CREATE (p)-[:BELONGS_TO]->(c);

// Create Orders
CREATE (o:Order {
    order_id: 1,
    order_date: datetime('2024-01-15T10:30:00'),
    status: 'Delivered',
    total_amount: 1999.99
});

// Customer places Order
MATCH (c:Customer {customer_id: 1}), (o:Order {order_id: 1})
CREATE (c)-[:PLACED]->(o);

// Order contains Product
MATCH (o:Order {order_id: 1}), (p:Product {product_id: 1})
CREATE (o)-[:CONTAINS {quantity: 1, unit_price: 1999.99}]->(p);

// Create Reviews
CREATE (r:Review {
    review_id: 1,
    rating: 5,
    review_text: 'Excellent product!',
    review_date: datetime('2024-01-20T14:00:00')
});

// Customer writes Review for Product
MATCH (c:Customer {customer_id: 1}), (r:Review {review_id: 1}), (p:Product {product_id: 1})
CREATE (c)-[:WROTE]->(r)
CREATE (r)-[:FOR_PRODUCT]->(p);

// Query to visualize relationships
MATCH (c:Customer)-[r1:PLACED]->(o:Order)-[r2:CONTAINS]->(p:Product)-[r3:BELONGS_TO]->(cat:Category)
RETURN c, r1, o, r2, p, r3, cat;