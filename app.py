import streamlit as st
import sqlite3
from datetime import datetime

# ---------------------------
# Database Setup & Functions
# ---------------------------

# Connect to SQLite database (creates file if not exists)
conn = sqlite3.connect('inventory.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    # Create orders table to store order header information
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT,
            gadi_no TEXT,
            order_date TEXT
        )
    ''')
    # Create order_items table to store each order's items
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            lot_no TEXT,
            quantity INTEGER,
            product_description TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    ''')
    # Create stock table to maintain current inventory
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_no TEXT UNIQUE,
            product_description TEXT,
            quantity INTEGER
        )
    ''')
    conn.commit()

init_db()

def add_order(party_name, gadi_no, order_date):
    c.execute("INSERT INTO orders (party_name, gadi_no, order_date) VALUES (?, ?, ?)", 
              (party_name, gadi_no, order_date))
    conn.commit()
    return c.lastrowid

def add_order_item(order_id, lot_no, quantity, product_description):
    c.execute("INSERT INTO order_items (order_id, lot_no, quantity, product_description) VALUES (?, ?, ?, ?)",
              (order_id, lot_no, quantity, product_description))
    conn.commit()

def update_stock_after_order(lot_no, quantity):
    """
    Checks if the lot exists and if sufficient stock is available.
    If yes, subtracts the quantity. Returns (True, message) if successful,
    otherwise (False, error message).
    """
    c.execute("SELECT quantity FROM stock WHERE lot_no = ?", (lot_no,))
    row = c.fetchone()
    if row is None:
        return False, f"Lot no {lot_no} does not exist in stock."
    current_qty = row[0]
    if current_qty < quantity:
        return False, f"Insufficient stock for Lot no {lot_no}. Available: {current_qty}, Required: {quantity}"
    new_qty = current_qty - quantity
    c.execute("UPDATE stock SET quantity = ? WHERE lot_no = ?", (new_qty, lot_no))
    conn.commit()
    return True, "Stock updated."

def add_stock(lot_no, product_description, quantity):
    try:
        c.execute("INSERT INTO stock (lot_no, product_description, quantity) VALUES (?, ?, ?)", 
              (lot_no, product_description, quantity))
    except sqlite3.IntegrityError:
        # If the lot already exists, update the quantity
        c.execute("UPDATE stock SET quantity = quantity + ? WHERE lot_no = ?", (quantity, lot_no))
    conn.commit()

def get_stock():
    c.execute("SELECT lot_no, product_description, quantity FROM stock")
    return c.fetchall()

def get_orders():
    c.execute("SELECT * FROM orders ORDER BY id DESC")
    return c.fetchall()

def get_order_items(order_id):
    c.execute("SELECT lot_no, quantity, product_description FROM order_items WHERE order_id = ?", (order_id,))
    return c.fetchall()

# ---------------------------
# Streamlit User Interface
# ---------------------------

st.title("Inventory Management System")

# Sidebar navigation
menu = st.sidebar.radio("Navigation", ["Place Order", "Stock Management", "Stock Report", "View Orders"])

# ---------------------------
# Place Order Section
# ---------------------------
if menu == "Place Order":
    st.header("Place New Order")
    
    # Initialize session state for order items if not already done
    if "order_items" not in st.session_state:
        st.session_state.order_items = []

    with st.form("order_form", clear_on_submit=False):
        party_name = st.text_input("Party Name")
        gadi_no = st.text_input("Vehicle/Gadi No")
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.write("Order Date:", order_date)
        
        st.subheader("Add Order Item")
        col1, col2, col3 = st.columns(3)
        lot_no = col1.text_input("Lot No", key="lot_no_input")
        quantity = col2.number_input("Quantity", min_value=1, step=1, key="quantity_input")
        product_description = col3.text_input("Product Description", key="prod_desc_input")
        
        add_item = st.form_submit_button("Add Item to Order")
        if add_item:
            if lot_no and product_description and quantity:
                # Append the order item to the session state list
                st.session_state.order_items.append({
                    "lot_no": lot_no,
                    "quantity": int(quantity),
                    "product_description": product_description
                })
                st.success(f"Added item: {lot_no} | {quantity} units | {product_description}")
            else:
                st.error("Please fill in all order item fields.")
    
    if st.session_state.order_items:
        st.subheader("Order Items Added:")
        for idx, item in enumerate(st.session_state.order_items):
            st.write(f"{idx+1}. Lot No: {item['lot_no']} | Quantity: {item['quantity']} | Description: {item['product_description']}")
        
        if st.button("Submit Order"):
            error_flag = False
            error_messages = []
            # Check stock for each order item before saving
            for item in st.session_state.order_items:
                valid, msg = update_stock_after_order(item['lot_no'], item['quantity'])
                if not valid:
                    error_flag = True
                    error_messages.append(msg)
            if error_flag:
                st.error("Order submission failed due to stock issues:")
                for err in error_messages:
                    st.error(err)
            else:
                # Save order header and items to the database
                order_id = add_order(party_name, gadi_no, order_date)
                for item in st.session_state.order_items:
                    add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                st.success("Order submitted successfully!")
                # Clear order items after submission
                st.session_state.order_items = []

# ---------------------------
# Stock Management Section
# ---------------------------
elif menu == "Stock Management":
    st.header("Stock Management")
    st.subheader("Add / Update Stock")
    with st.form("stock_form", clear_on_submit=True):
        lot_no_stock = st.text_input("Lot No", key="lot_no_stock")
        product_description_stock = st.text_input("Product Description", key="product_desc_stock")
        stock_quantity = st.number_input("Quantity to Add", min_value=1, step=1, key="stock_qty")
        submit_stock = st.form_submit_button("Add/Update Stock")
        if submit_stock:
            if lot_no_stock and product_description_stock and stock_quantity:
                add_stock(lot_no_stock, product_description_stock, int(stock_quantity))
                st.success("Stock updated successfully!")
            else:
                st.error("Please fill in all stock fields.")

# ---------------------------
# Stock Report Section
# ---------------------------
elif menu == "Stock Report":
    st.header("Stock Report")
    stock_data = get_stock()
    if stock_data:
        st.table(stock_data)
    else:
        st.write("No stock records found.")

# ---------------------------
# View Orders Section
# ---------------------------
elif menu == "View Orders":
    st.header("View Orders")
    orders = get_orders()
    if orders:
        for order in orders:
            order_id, party_name, gadi_no, order_date = order
            st.write(f"**Order ID:** {order_id} | **Party:** {party_name} | **Vehicle:** {gadi_no} | **Date:** {order_date}")
            items = get_order_items(order_id)
            if items:
                for item in items:
                    lot_no, quantity, prod_desc = item
                    st.write(f"- Lot No: {lot_no} | Quantity: {quantity} | Description: {prod_desc}")
            st.write("---")
    else:
        st.write("No orders found.")
