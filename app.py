import streamlit as st
import sqlite3
import re
from datetime import datetime

# ---------------------------
# Database Setup & Functions
# ---------------------------

# Connect to SQLite database (creates file if not exists)
conn = sqlite3.connect('inventory.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT,
            gadi_no TEXT,
            order_date TEXT
        )
    ''')
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
        # Lot already exists—update the quantity.
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
# Order Text Parsing Function
# ---------------------------
def parse_order_text(text):
    """
    Expects text in the format:
    
    Party Name : NS
    Gadi No : MH 05 EA 9834
    
    Order 
    
    Lot no : 14016 (2 bxs SAFAWI A-1 QUALITY)
    Lot no : 14019 (2 bxs SAFAWI JUMBO)
    Lot no : 14390 (2 bxs SAFAWI PREMIUM)
    Lot no : 14391 (2 bxs
    SAFAWI SUPER QUALITY)
    Lot no : 14392 (2 bxs SAFAWI QUALITY)
    Lot no : 14393 (2 bxs AJWA PREMIUM)
    
     Total : 12  bxs
    """
    result = {}
    full_text = text.strip()
    
    # Extract Party Name
    party_match = re.search(r"Party\s*Name\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["party_name"] = party_match.group(1).strip() if party_match else ""
    
    # Extract Gadi No
    gadi_match = re.search(r"Gadi\s*No\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["gadi_no"] = gadi_match.group(1).strip() if gadi_match else ""
    
    # Extract Order Items using regex with DOTALL to handle multiline descriptions.
    item_pattern = re.compile(r"Lot\s*no\s*:\s*(\S+)\s*\(\s*(\d+)\s*bxs\s*(.*?)\)", re.IGNORECASE | re.DOTALL)
    items = item_pattern.findall(full_text)
    order_items = []
    for match in items:
        lot_no = match[0].strip()
        quantity = int(match[1])
        description = match[2].replace("\n", " ").strip()
        order_items.append({
            "lot_no": lot_no,
            "quantity": quantity,
            "product_description": description
        })
    result["order_items"] = order_items
    
    # Extract Total if present
    total_match = re.search(r"Total\s*:\s*(\d+)\s*bxs", full_text, re.IGNORECASE)
    result["total"] = int(total_match.group(1)) if total_match else None
    
    return result

# ---------------------------
# Streamlit User Interface
# ---------------------------

st.title("Inventory Management System")

# Sidebar Navigation (includes new "Paste Order" tab)
menu = st.sidebar.radio("Navigation", 
    ["Paste Order", "Place Order", "Stock Management", "Stock Report", "View Orders"])

# ----- Paste Order Tab -----
if menu == "Paste Order":
    st.header("Paste Order Text")
    st.markdown(
        "Paste your entire order text (including party name, vehicle number, order items, and total) in the box below."
    )
    raw_text = st.text_area("Order Text", height=300)
    if st.button("Parse Order"):
        if raw_text.strip():
            order_data = parse_order_text(raw_text)
            st.subheader("Parsed Order Data:")
            st.write("**Party Name:**", order_data.get("party_name", ""))
            st.write("**Gadi No:**", order_data.get("gadi_no", ""))
            st.write("**Order Items:**")
            for idx, item in enumerate(order_data.get("order_items", [])):
                st.write(f"{idx+1}. **Lot:** {item['lot_no']}, **Quantity:** {item['quantity']}, **Description:** {item['product_description']}")
            if order_data.get("total") is not None:
                st.write("**Total Boxes:**", order_data["total"])
            
            if st.button("Submit Parsed Order"):
                error_flag = False
                error_messages = []
                for item in order_data.get("order_items", []):
                    valid, msg = update_stock_after_order(item['lot_no'], item['quantity'])
                    if not valid:
                        error_flag = True
                        error_messages.append(msg)
                if error_flag:
                    st.error("Order submission failed due to stock issues:")
                    for err in error_messages:
                        st.error(err)
                else:
                    order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    order_id = add_order(order_data.get("party_name", ""), order_data.get("gadi_no", ""), order_date)
                    for item in order_data.get("order_items", []):
                        add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                    st.success("Order submitted successfully!")
        else:
            st.error("Please paste the order text.")

# ----- Place Order Tab (Manual Entry) -----
elif menu == "Place Order":
    st.header("Place New Order")
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
                order_id = add_order(party_name, gadi_no, order_date)
                for item in st.session_state.order_items:
                    add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                st.success("Order submitted successfully!")
                st.session_state.order_items = []

# ----- Stock Management Tab -----
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

# ----- Stock Report Tab -----
elif menu == "Stock Report":
    st.header("Stock Report")
    stock_data = get_stock()
    if stock_data:
        st.table(stock_data)
    else:
        st.write("No stock records found.")

# ----- View Orders Tab -----
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
