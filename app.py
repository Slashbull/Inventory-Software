import streamlit as st
from deta import Deta
import datetime
import uuid

# ---------------------------
# Deta Base Setup
# ---------------------------
# Set your Deta project key in Streamlit Cloud Secrets as DETA_PROJECT_KEY
deta = Deta(st.secrets["DETA_PROJECT_KEY"])

# Initialize the bases (collections)
orders_db = deta.Base("orders")
stock_db = deta.Base("stock")

# ---------------------------
# App Title & Sidebar Navigation
# ---------------------------
st.title("Inventory Management System")

menu = st.sidebar.radio("Menu", ["View Orders", "New Order", "Update Stock", "View Stock"])

# ---------------------------
# View Orders
# ---------------------------
if menu == "View Orders":
    st.header("Orders")
    orders = orders_db.fetch().items
    if orders:
        for order in orders:
            st.subheader(f"Order ID: {order.get('key')}")
            st.write("Party Name:", order.get("party_name"))
            st.write("Gadi No:", order.get("gadi_no"))
            st.write("Order Date:", order.get("order_date"))
            st.write("Items:")
            for item in order.get("items", []):
                st.write(f"- Lot: {item.get('lot_no')} | Quantity: {item.get('quantity')} | Description: {item.get('product_description')}")
            st.markdown("---")
    else:
        st.write("No orders found.")

# ---------------------------
# New Order
# ---------------------------
elif menu == "New Order":
    st.header("New Order")
    with st.form("order_form"):
        party_name = st.text_input("Party Name")
        gadi_no = st.text_input("Gadi No")
        order_date = st.text_input("Order Date (YYYY-MM-DD HH:MM)", 
                                   value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        st.markdown("### Order Item")
        lot_no = st.text_input("Lot No")
        quantity = st.number_input("Quantity", min_value=1, value=1)
        product_description = st.text_input("Product Description")
        submitted = st.form_submit_button("Create Order")
        if submitted:
            # Validate stock for the provided lot_no
            stock_item = stock_db.get(lot_no)
            if not stock_item:
                st.error(f"Stock for lot '{lot_no}' not found.")
            elif stock_item.get("quantity", 0) < quantity:
                st.error(f"Not enough stock for lot '{lot_no}'. Available: {stock_item.get('quantity')}")
            else:
                # Deduct stock
                new_stock_qty = stock_item["quantity"] - quantity
                stock_db.put({"key": lot_no, 
                              "product_description": stock_item["product_description"],
                              "quantity": new_stock_qty})
                # Create order
                order_data = {
                    "party_name": party_name,
                    "gadi_no": gadi_no,
                    "order_date": order_date,
                    "items": [{
                        "lot_no": lot_no,
                        "quantity": quantity,
                        "product_description": product_description
                    }]
                }
                order_id = str(uuid.uuid4())
                orders_db.put({"key": order_id, **order_data})
                st.success("Order created successfully.")

# ---------------------------
# Update Stock
# ---------------------------
elif menu == "Update Stock":
    st.header("Update Stock")
    with st.form("stock_form"):
        lot_no = st.text_input("Lot No")
        product_description = st.text_input("Product Description")
        quantity = st.number_input("Quantity to Add", min_value=1, value=1)
        submitted = st.form_submit_button("Update Stock")
        if submitted:
            # If stock exists, update it; otherwise, create new stock
            stock_item = stock_db.get(lot_no)
            if stock_item:
                new_qty = stock_item["quantity"] + quantity
                stock_db.put({"key": lot_no, "product_description": product_description, "quantity": new_qty})
            else:
                stock_db.put({"key": lot_no, "product_description": product_description, "quantity": quantity})
            st.success("Stock updated successfully.")

# ---------------------------
# View Stock
# ---------------------------
elif menu == "View Stock":
    st.header("Stock")
    stock_items = stock_db.fetch().items
    if stock_items:
        for item in stock_items:
            st.write(f"Lot: {item.get('key')}, Description: {item.get('product_description')}, Quantity: {item.get('quantity')}")
    else:
        st.write("No stock records found.")
