import streamlit as st
from supabase import create_client, Client
from types import SimpleNamespace
import re
from datetime import datetime
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SCHEMA

# --------------------------------------------------
# Initialize Supabase Client
# Wrap options in SimpleNamespace to ensure a 'headers' attribute exists.
# --------------------------------------------------
options = SimpleNamespace(schema=SUPABASE_SCHEMA, headers={})
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)

st.title("Robust Inventory Management System with Supabase")

# --------------------------------------------------
# Database Helper Functions
# --------------------------------------------------
def add_order(party_name, gadi_no, order_date):
    try:
        new_order = {"party_name": party_name, "gadi_no": gadi_no, "order_date": order_date}
        response = supabase.table("orders").insert(new_order).execute()
        if response.get("data") and len(response["data"]) > 0:
            return response["data"][0]["id"]
        else:
            st.error("Failed to add order.")
            return None
    except Exception as e:
        st.error(f"Error adding order: {e}")
        return None

def add_order_item(order_id, lot_no, quantity, product_description):
    try:
        new_item = {
            "order_id": order_id,
            "lot_no": lot_no,
            "quantity": quantity,
            "product_description": product_description,
        }
        supabase.table("order_items").insert(new_item).execute()
    except Exception as e:
        st.error(f"Error adding order item: {e}")

def get_orders():
    try:
        response = supabase.table("orders").select("*").order("id", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        return []

def get_order_items(order_id):
    try:
        response = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching order items: {e}")
        return []

def get_stock():
    try:
        response = supabase.table("stock").select("*").order("lot_no").execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching stock: {e}")
        return []

def update_stock_after_order(lot_no, quantity):
    try:
        res = supabase.table("stock").select("quantity").eq("lot_no", lot_no).execute()
        data = res.data
        if not data or len(data) == 0:
            return False, f"Lot no {lot_no} does not exist in stock."
        current_qty = data[0]["quantity"]
        if current_qty < quantity:
            return False, f"Insufficient stock for Lot no {lot_no}. Available: {current_qty}, Required: {quantity}"
        new_qty = current_qty - quantity
        supabase.table("stock").update({"quantity": new_qty}).eq("lot_no", lot_no).execute()
        return True, "Stock updated."
    except Exception as e:
        return False, f"Error updating stock: {e}"

def add_stock_increment(lot_no, product_description, quantity_to_add):
    try:
        res = supabase.table("stock").select("*").eq("lot_no", lot_no).execute()
        data = res.data
        if data and len(data) > 0:
            current_qty = data[0]["quantity"]
            new_qty = current_qty + quantity_to_add
            supabase.table("stock").update({"quantity": new_qty, "product_description": product_description}).eq("lot_no", lot_no).execute()
        else:
            supabase.table("stock").insert({"lot_no": lot_no, "product_description": product_description, "quantity": quantity_to_add}).execute()
    except Exception as e:
        st.error(f"Error updating stock increment: {e}")

def add_stock_entry(entry):
    try:
        supabase.table("stock_entries").insert(entry).execute()
    except Exception as e:
        st.error(f"Error adding stock entry: {e}")

def update_stock_from_entry(entry):
    add_stock_entry(entry)
    combined_description = f"{entry['product_name']} - {entry['brand_name']}"
    try:
        supabase.table("stock").upsert({
            "lot_no": entry["lot_no"],
            "product_description": combined_description,
            "quantity": entry["balance_quantity"]
        }).execute()
    except Exception as e:
        st.error(f"Error upserting stock from entry: {e}")

# --------------------------------------------------
# Parsing Functions
# --------------------------------------------------
def parse_order_text(text):
    result = {}
    full_text = text.strip()
    party_match = re.search(r"Party\s*Name\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["party_name"] = party_match.group(1).strip() if party_match else ""
    gadi_match = re.search(r"Gadi\s*No\s*:\s*(.*)", full_text, re.IGNORECASE)
    result["gadi_no"] = gadi_match.group(1).strip() if gadi_match else ""
    item_pattern = re.compile(r"Lot\s*no\s*:\s*(\S+)\s*\(\s*(\d+)\s*bxs\s*(.*?)\)", re.IGNORECASE | re.DOTALL)
    items = item_pattern.findall(full_text)
    order_items = []
    for match in items:
        lot_no = match[0].strip()
        quantity = int(match[1])
        description = match[2].replace("\n", " ").strip()
        order_items.append({"lot_no": lot_no, "quantity": quantity, "product_description": description})
    result["order_items"] = order_items
    total_match = re.search(r"Total\s*:\s*(\d+)\s*bxs", full_text, re.IGNORECASE)
    result["total"] = int(total_match.group(1)) if total_match else None
    return result

def parse_stock_text(text):
    lines = text.strip().splitlines()
    entries = []
    start_index = 0
    if lines:
        header_line = lines[0].lower()
        if "inwarddate" in header_line or "storagearea" in header_line:
            start_index = 1
    for line in lines[start_index:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            parts = re.split(r"\s{2,}", line)
        if len(parts) < 8:
            continue
        inward_date = parts[0].strip()
        storage_area = parts[1].strip()
        lot_no = parts[2].strip()
        product_name = parts[3].strip()
        brand_name = parts[4].strip()
        try:
            in_qty = int(parts[5].strip())
            out_qty = int(parts[6].strip())
            bal_qty = int(parts[7].strip())
        except:
            continue
        entry = {
            "inward_date": inward_date,
            "storage_area": storage_area,
            "lot_no": lot_no,
            "product_name": product_name,
            "brand_name": brand_name,
            "in_quantity": in_qty,
            "out_quantity": out_qty,
            "balance_quantity": bal_qty
        }
        entries.append(entry)
    return entries

# --------------------------------------------------
# Streamlit UI
# --------------------------------------------------
menu = st.sidebar.radio("Navigation", [
    "Paste Order",
    "Paste Stock",
    "Place Order (Manual)",
    "Stock Management (Manual)",
    "Stock Report",
    "View Orders"
])

# ----- Paste Order Tab -----
if menu == "Paste Order":
    st.header("Paste Order Text")
    st.markdown("Paste the complete order text including Party Name, Gadi No, and order items.")
    raw_text = st.text_area("Order Text", height=300)
    if st.button("Parse Order"):
        if raw_text.strip():
            order_data = parse_order_text(raw_text)
            st.subheader("Parsed Order Data")
            st.write("**Party Name:**", order_data.get("party_name", ""))
            st.write("**Gadi No:**", order_data.get("gadi_no", ""))
            st.write("**Order Items:**")
            for idx, item in enumerate(order_data.get("order_items", [])):
                st.write(f"{idx+1}. Lot: {item['lot_no']} | Qty: {item['quantity']} | Desc: {item['product_description']}")
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
                    if order_id:
                        for item in order_data.get("order_items", []):
                            add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                        st.success("Order submitted successfully!")
                    else:
                        st.error("Failed to create order.")
        else:
            st.error("Please paste the order text.")

# ----- Paste Stock Tab -----
elif menu == "Paste Stock":
    st.header("Paste Stock Data")
    st.markdown("Paste stock data in this format (header optional):\n`InwardDate  StorageArea  LotNo  ProductName  BrandName  InQuantity  OutQuantity  BalanceQuantity`")
    raw_stock_text = st.text_area("Stock Data", height=300)
    if st.button("Parse & Update Stock"):
        if raw_stock_text.strip():
            stock_entries = parse_stock_text(raw_stock_text)
            if not stock_entries:
                st.error("No valid stock entries found. Please check formatting.")
            else:
                st.subheader("Parsed Stock Entries")
                for e in stock_entries:
                    st.write(f"Date: {e['inward_date']} | Area: {e['storage_area']} | Lot: {e['lot_no']} | Product: {e['product_name']} - {e['brand_name']} | Bal: {e['balance_quantity']}")
                if st.button("Submit Stock Entries"):
                    for e in stock_entries:
                        update_stock_from_entry(e)
                    st.success("Stock entries updated successfully!")
        else:
            st.error("Please paste the stock data.")

# ----- Place Order (Manual) Tab -----
elif menu == "Place Order (Manual)":
    st.header("Place New Order (Manual Entry)")
    if "manual_order_items" not in st.session_state:
        st.session_state.manual_order_items = []
    with st.form("manual_order_form", clear_on_submit=False):
        party_name = st.text_input("Party Name")
        gadi_no = st.text_input("Vehicle/Gadi No")
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.write("Order Date:", order_date)
        st.subheader("Add Order Item")
        col1, col2, col3 = st.columns(3)
        lot_no = col1.text_input("Lot No", key="manual_lot_no")
        quantity = col2.number_input("Quantity", min_value=1, step=1, key="manual_quantity")
        product_description = col3.text_input("Product Description", key="manual_prod_desc")
        add_item = st.form_submit_button("Add Item")
        if add_item:
            if lot_no and product_description and quantity:
                st.session_state.manual_order_items.append({"lot_no": lot_no, "quantity": int(quantity), "product_description": product_description})
                st.success(f"Added item: {lot_no} | {quantity} units | {product_description}")
            else:
                st.error("Please fill in all fields.")
    if st.session_state.manual_order_items:
        st.subheader("Order Items Added:")
        for idx, item in enumerate(st.session_state.manual_order_items):
            st.write(f"{idx+1}. Lot: {item['lot_no']} | Qty: {item['quantity']} | Desc: {item['product_description']}")
        if st.button("Submit Order"):
            error_flag = False
            error_messages = []
            for item in st.session_state.manual_order_items:
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
                if order_id:
                    for item in st.session_state.manual_order_items:
                        add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
                    st.success("Order submitted successfully!")
                    st.session_state.manual_order_items = []
                else:
                    st.error("Failed to create order.")

# ----- Stock Management (Manual) Tab -----
elif menu == "Stock Management (Manual)":
    st.header("Stock Management (Manual)")
    st.subheader("Add / Update Stock (Increment)")
    with st.form("manual_stock_form", clear_on_submit=True):
        lot_no_stock = st.text_input("Lot No", key="stock_lot_no")
        product_description_stock = st.text_input("Product Description", key="stock_prod_desc")
        stock_quantity = st.number_input("Quantity to Add", min_value=1, step=1, key="stock_qty")
        submit_stock = st.form_submit_button("Update Stock")
        if submit_stock:
            if lot_no_stock and product_description_stock and stock_quantity:
                add_stock_increment(lot_no_stock, product_description_stock, int(stock_quantity))
                st.success("Stock updated successfully!")
            else:
                st.error("Please fill in all fields.")

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
            order_id = order.get("id")
            party_name = order.get("party_name")
            gadi_no = order.get("gadi_no")
            order_date = order.get("order_date")
            st.write(f"Order ID: {order_id} | Party: {party_name} | Vehicle: {gadi_no} | Date: {order_date}")
            items = get_order_items(order_id)
            if items:
                for item in items:
                    st.write(f"- Lot: {item.get('lot_no')} | Qty: {item.get('quantity')} | Desc: {item.get('product_description')}")
            st.write("---")
    else:
        st.write("No orders found.")
