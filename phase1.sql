Table Customer {
  customer_id int [pk]
  name varchar
  email varchar [unique]
  password varchar
}

Table Category {
  category_id int [pk]
  name varchar
}

Table Product {
  product_id int [pk]
  name varchar
  price decimal
  stock_quantity int
  category_id int
}

Table Orders {
  order_id int [pk]
  customer_id int
  order_date date
  total_amount decimal
}

Table Order_Item {
  order_item_id int [pk]
  order_id int
  product_id int
  quantity int
}

Table Payment {
  payment_id int [pk]
  order_id int [unique]
  payment_status varchar
}

Ref: Product.category_id > Category.category_id
Ref: Orders.customer_id > Customer.customer_id
Ref: Order_Item.order_id > Orders.order_id
Ref: Order_Item.product_id > Product.product_id
Ref: Payment.order_id > Orders.order_id