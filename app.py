import streamlit as st
import sqlite3
import re
from datetime import datetime

# ----------------------------------------------------
# 1) DATABASE SETUP & FUNCTIONS
# ----------------------------------------------------
conn = sqlite3.connect('inventory.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    """
    Creates all necessary tables if they don't already exist.
    """
    # Orders (header)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_name TEXT,
            gadi_no TEXT,
            order_date TEXT
        )
    ''')
    # Order items (details)
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
    # Simplified "stock" table (lot_no is unique, quantity is the current balance)
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_no TEXT UNIQUE,
            product_description TEXT,
            quantity INTEGER
        )
    ''')
    # Optional: store each pasted stock row in a "stock_entries" table for historical reference
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inward_date TEXT,
            storage_area TEXT,
            lot_no TEXT,
            product_name TEXT,
            brand_name TEXT,
            in_quantity INTEGER,
            out_quantity INTEGER,
            balance_quantity INTEGER
        )
    ''')
    conn.commit()

init_db()

# ---------------- ORDERS ----------------
def add_order(party_name, gadi_no, order_date):
    c.execute("INSERT INTO orders (party_name, gadi_no, order_date) VALUES (?, ?, ?)",
              (party_name, gadi_no, order_date))
    conn.commit()
    return c.lastrowid

def add_order_item(order_id, lot_no, quantity, product_description):
    c.execute("INSERT INTO order_items (order_id, lot_no, quantity, product_description) VALUES (?, ?, ?, ?)",
              (order_id, lot_no, quantity, product_description))
    conn.commit()

def get_orders():
    c.execute("SELECT * FROM orders ORDER BY id DESC")
    return c.fetchall()

def get_order_items(order_id):
    c.execute("SELECT lot_no, quantity, product_description FROM order_items WHERE order_id = ?", (order_id,))
    return c.fetchall()

# ---------------- STOCK ----------------
def set_stock(lot_no, product_description, new_quantity):
    """
    Sets (or overwrites) the 'quantity' for a lot_no in the 'stock' table
    instead of incrementing. If lot_no doesn't exist, creates a new record.
    """
    try:
        # Attempt to insert
        c.execute("""
            INSERT INTO stock (lot_no, product_description, quantity) 
            VALUES (?, ?, ?)
        """, (lot_no, product_description, new_quantity))
    except sqlite3.IntegrityError:
        # Lot already exists => update
        c.execute("""
            UPDATE stock 
            SET quantity = ?, product_description = ? 
            WHERE lot_no = ?
        """, (new_quantity, product_description, lot_no))
    conn.commit()

def add_stock_increment(lot_no, product_description, quantity_to_add):
    """
    Increments the quantity by the specified amount (used by manual 'Stock Management').
    If lot_no doesn't exist, creates a new record with that quantity.
    """
    try:
        c.execute("""
            INSERT INTO stock (lot_no, product_description, quantity) 
            VALUES (?, ?, ?)
        """, (lot_no, product_description, quantity_to_add))
    except sqlite3.IntegrityError:
        # If the lot already exists, increment quantity
        c.execute("""
            UPDATE stock 
            SET quantity = quantity + ?, product_description = ? 
            WHERE lot_no = ?
        """, (quantity_to_add, product_description, lot_no))
    conn.commit()

def get_stock():
    c.execute("SELECT lot_no, product_description, quantity FROM stock ORDER BY lot_no")
    return c.fetchall()

# ---------------- STOCK ENTRIES (RAW LINES) ----------------
def add_stock_entry(
    inward_date, storage_area, lot_no, product_name,
    brand_name, in_qty, out_qty, bal_qty
):
    """
    Inserts a row into stock_entries for historical reference.
    """
    c.execute("""
        INSERT INTO stock_entries (
            inward_date, storage_area, lot_no, product_name, 
            brand_name, in_quantity, out_quantity, balance_quantity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (inward_date, storage_area, lot_no, product_name, brand_name, in_qty, out_qty, bal_qty))
    conn.commit()

def update_stock_from_entry(
    inward_date, storage_area, lot_no, product_name,
    brand_name, in_qty, out_qty, bal_qty
):
    """
    - Saves an entry in 'stock_entries'.
    - Updates the main 'stock' table to reflect the final balance quantity.
    - Merges 'product_name' + 'brand_name' into a single 'product_description' for the 'stock' table.
    """
    add_stock_entry(inward_date, storage_area, lot_no, product_name, brand_name, in_qty, out_qty, bal_qty)
    # We treat 'balance_quantity' as the final current quantity
    combined_description = f"{product_name} - {brand_name}"
    set_stock(lot_no, combined_description, bal_qty)

# ---------------- HELPER FUNCTIONS ----------------
def update_stock_after_order(lot_no, quantity):
    """
    For each item in an order, we subtract 'quantity' from the 'stock' table.
    Return (True, message) if success, (False, error) if not enough stock or lot not found.
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

# ----------------------------------------------------
# 2) PARSING FUNCTIONS
# ----------------------------------------------------
def parse_order_text(text):
    """
    Expects text in format like:
    
    Party Name : NS
    Gadi No : MH 05 EA 9834
    
    Order
    
    Lot no : 14016 (2 bxs SAFAWI A-1 QUALITY)
    Lot no : 14019 (2 bxs SAFAWI JUMBO)
    ...
    Total : 12 bxs
    """
    result = {}
    full_text = text.strip()

    # Party Name
    party_match = re.search(r"Party\s*Name\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["party_name"] = party_match.group(1).strip() if party_match else ""

    # Gadi No
    gadi_match = re.search(r"Gadi\s*No\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["gadi_no"] = gadi_match.group(1).strip() if gadi_match else ""

    # Order Items:  Lot no : 14016 (2 bxs SAFAWI A-1 QUALITY)
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

    # Total Boxes
    total_match = re.search(r"Total\s*:\s*(\d+)\s*bxs", full_text, re.IGNORECASE)
    result["total"] = int(total_match.group(1)) if total_match else None

    return result

def parse_stock_text(text):
    """
    Expects a tabular format (or possibly tab-separated) with a header row:
    InwardDate   StorageArea   LotNo   ProductName   BrandName   InQuantity   OutQuantity   BalanceQuantity

    For example:
    InwardDate   StorageArea   LotNo   ProductName             BrandName              InQuantity OutQuantity BalanceQuantity
    15/02/2025   CS-20        14393   WET DATES BOX 5 KG (imp) AJWA (PREMIUM)         494        282        212
    03/01/2025   CS-20        14016   WET DATES BOX 5 KG (imp) SAFAWI (A-1) QUALITY   1054       253        801
    ...
    """
    lines = text.strip().splitlines()
    entries = []

    # Attempt to detect and skip header row
    # We'll look for a line containing "InwardDate" or "StorageArea" etc.
    start_index = 0
    if lines:
        header_line = lines[0].lower()
        if ("inwarddate" in header_line) or ("storagearea" in header_line):
            start_index = 1  # skip header row

    for line in lines[start_index:]:
        line = line.strip()
        if not line:
            continue  # skip empty lines
        # Try splitting by tabs first
        parts = line.split("\t")
        # If we don't have 8 columns, try splitting by multiple spaces
        if len(parts) < 8:
            parts = re.split(r"\s{2,}", line)  # split on 2+ spaces
        if len(parts) < 8:
            # If still not 8 columns, skip or raise an error
            continue
        
        # Extract columns
        inward_date = parts[0].strip()
        storage_area = parts[1].strip()
        lot_no = parts[2].strip()
        product_name = parts[3].strip()
        brand_name = parts[4].strip()
        in_qty = int(parts[5].strip())
        out_qty = int(parts[6].strip())
        bal_qty = int(parts[7].strip())

        entries.append({
            "inward_date": inward_date,
            "storage_area": storage_area,
            "lot_no": lot_no,
            "product_name": product_name,
            "brand_name": brand_name,
            "in_quantity": in_qty,
            "out_quantity": out_qty,
            "balance_quantity": bal_qty
        })
    return entries

# ----------------------------------------------------
# 3) STREAMLIT APP
# ----------------------------------------------------
st.title("Inventory Management System")

# Sidebar Navigation
menu = st.sidebar.radio(
    "Navigation", 
    [
        "Paste Order", 
        "Paste Stock", 
        "Place Order", 
        "Stock Management", 
        "Stock Report", 
        "View Orders"
    ]
)

# -------------- (A) PASTE ORDER --------------
if menu == "Paste Order":
    st.header("Paste Order Text")
    st.markdown("Paste the entire order text (including Party Name, Gadi No, and items).")
    raw_text = st.text_area("Order Text", height=300)
    if st.button("Parse Order"):
        if raw_text.strip():
            order_data = parse_order_text(raw_text)
            st.subheader("Parsed Order Data")
            st.write("**Party Name:**", order_data.get("party_name", ""))
            st.write("**Gadi No:**", order_data.get("gadi_no", ""))
            st.write("**Order Items:**")
            for idx, item in enumerate(order_data.get("order_items", [])):
                st.write(
                    f"{idx+1}. **Lot:** {item['lot_no']} | "
                    f"**Qty:** {item['quantity']} | "
                    f"**Desc:** {item['product_description']}"
                )
            if order_data.get("total") is not None:
                st.write("**Total Boxes:**", order_data["total"])
            
            if st.button("Submit Parsed Order"):
                # Validate stock
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
                    # Add order header
                    order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    order_id = add_order(
                        order_data.get("party_name", ""), 
                        order_data.get("gadi_no", ""), 
                        order_date
                    )
                    # Add order items
                    for item in order_data.get("order_items", []):
                        add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                    st.success("Order submitted successfully!")
        else:
            st.error("Please paste the order text.")

# -------------- (B) PASTE STOCK --------------
elif menu == "Paste Stock":
    st.header("Paste Stock Data")
    st.markdown(
        "Paste rows (including the header if you have one) in the format:\n\n"
        "`InwardDate  StorageArea  LotNo  ProductName  BrandName  InQuantity  OutQuantity  BalanceQuantity`"
    )
    raw_stock_text = st.text_area("Stock Text", height=300)
    if st.button("Parse & Update Stock"):
        if raw_stock_text.strip():
            stock_entries = parse_stock_text(raw_stock_text)
            if not stock_entries:
                st.error("No valid stock lines found. Please check formatting.")
            else:
                st.subheader("Parsed Stock Entries")
                for e in stock_entries:
                    st.write(
                        f"**Date:** {e['inward_date']} | **Area:** {e['storage_area']} | "
                        f"**LotNo:** {e['lot_no']} | **In:** {e['in_quantity']} | **Out:** {e['out_quantity']} | "
                        f"**Bal:** {e['balance_quantity']} | **Product:** {e['product_name']} - {e['brand_name']}"
                    )
                if st.button("Submit Stock Entries"):
                    for e in stock_entries:
                        update_stock_from_entry(
                            e["inward_date"],
                            e["storage_area"],
                            e["lot_no"],
                            e["product_name"],
                            e["brand_name"],
                            e["in_quantity"],
                            e["out_quantity"],
                            e["balance_quantity"]
                        )
                    st.success("Stock data updated successfully!")
        else:
            st.error("Please paste the stock data.")

# -------------- (C) PLACE ORDER (Manual) --------------
elif menu == "Place Order":
    st.header("Place New Order (Manual)")
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
            st.write(
                f"{idx+1}. Lot No: {item['lot_no']} | "
                f"Quantity: {item['quantity']} | "
                f"Description: {item['product_description']}"
            )
        if st.button("Submit Order"):
            # Check stock for each item
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
                # Add order + items
                order_id = add_order(party_name, gadi_no, order_date)
                for item in st.session_state.order_items:
                    add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                st.success("Order submitted successfully!")
                st.session_state.order_items = []

# -------------- (D) STOCK MANAGEMENT (Manual) --------------
elif menu == "Stock Management":
    st.header("Stock Management (Manual)")
    st.subheader("Add / Update Stock (Incrementally)")
    with st.form("stock_form", clear_on_submit=True):
        lot_no_stock = st.text_input("Lot No", key="lot_no_stock")
        product_description_stock = st.text_input("Product Description", key="product_desc_stock")
        stock_quantity = st.number_input("Quantity to Add", min_value=1, step=1, key="stock_qty")
        submit_stock = st.form_submit_button("Add/Update Stock")
        if submit_stock:
            if lot_no_stock and product_description_stock and stock_quantity:
                add_stock_increment(lot_no_stock, product_description_stock, int(stock_quantity))
                st.success("Stock updated successfully!")
            else:
                st.error("Please fill in all stock fields.")

# -------------- (E) STOCK REPORT --------------
elif menu == "Stock Report":
    st.header("Stock Report")
    stock_data = get_stock()
    if stock_data:
        st.table(stock_data)
    else:
        st.write("No stock records found.")

# -------------- (F) VIEW ORDERS --------------
elif menu == "View Orders":
    st.header("View Orders")
    orders = get_orders()
    if orders:
        for order in orders:
            order_id, party_name, gadi_no, order_date = order
            st.write(
                f"**Order ID:** {order_id} | "
                f"**Party:** {party_name} | "
                f"**Vehicle:** {gadi_no} | "
                f"**Date:** {order_date}"
            )
            items = get_order_items(order_id)
            if items:
                for item in items:
                    lot_no, quantity, prod_desc = item
                    st.write(f"- Lot No: {lot_no} | Qty: {quantity} | Desc: {prod_desc}")
            st.write("---")
    else:
        st.write("No orders found.")
