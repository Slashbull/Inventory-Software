import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QTabWidget, QSpinBox, QListWidget,
    QListWidgetItem, QMessageBox, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt

# ---------------------------
# Database Setup & Functions
# ---------------------------
conn = sqlite3.connect('inventory.db')
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
# PyQt5 Application Classes
# ---------------------------

class PlaceOrderTab(QWidget):
    def __init__(self):
        super().__init__()
        self.order_items = []  # list to hold order items
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()

        # Order header form
        form_layout = QFormLayout()
        self.party_name_input = QLineEdit()
        self.gadi_no_input = QLineEdit()
        self.order_date_label = QLabel(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        form_layout.addRow("Party Name:", self.party_name_input)
        form_layout.addRow("Vehicle/Gadi No:", self.gadi_no_input)
        form_layout.addRow("Order Date:", self.order_date_label)
        layout.addLayout(form_layout)

        # Order item form
        layout.addWidget(QLabel("Add Order Item:"))
        item_form_layout = QHBoxLayout()
        self.lot_no_input = QLineEdit()
        self.lot_no_input.setPlaceholderText("Lot No")
        self.quantity_input = QSpinBox()
        self.quantity_input.setMinimum(1)
        self.prod_desc_input = QLineEdit()
        self.prod_desc_input.setPlaceholderText("Product Description")
        self.add_item_btn = QPushButton("Add Item")
        self.add_item_btn.clicked.connect(self.add_order_item)
        item_form_layout.addWidget(self.lot_no_input)
        item_form_layout.addWidget(self.quantity_input)
        item_form_layout.addWidget(self.prod_desc_input)
        item_form_layout.addWidget(self.add_item_btn)
        layout.addLayout(item_form_layout)

        # List widget to show added items
        self.items_list = QListWidget()
        layout.addWidget(QLabel("Order Items Added:"))
        layout.addWidget(self.items_list)

        # Submit Order button
        self.submit_order_btn = QPushButton("Submit Order")
        self.submit_order_btn.clicked.connect(self.submit_order)
        layout.addWidget(self.submit_order_btn)

        self.setLayout(layout)

    def add_order_item(self):
        lot_no = self.lot_no_input.text().strip()
        quantity = self.quantity_input.value()
        prod_desc = self.prod_desc_input.text().strip()
        if lot_no and prod_desc:
            item_text = f"Lot: {lot_no} | Qty: {quantity} | Desc: {prod_desc}"
            self.order_items.append({
                "lot_no": lot_no,
                "quantity": quantity,
                "product_description": prod_desc
            })
            self.items_list.addItem(QListWidgetItem(item_text))
            # Clear input fields after adding
            self.lot_no_input.clear()
            self.quantity_input.setValue(1)
            self.prod_desc_input.clear()
        else:
            QMessageBox.warning(self, "Input Error", "Please fill in Lot No and Product Description.")

    def submit_order(self):
        party_name = self.party_name_input.text().strip()
        gadi_no = self.gadi_no_input.text().strip()
        order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not party_name or not gadi_no:
            QMessageBox.warning(self, "Input Error", "Please fill in Party Name and Vehicle No.")
            return
        if not self.order_items:
            QMessageBox.warning(self, "Input Error", "Please add at least one order item.")
            return

        # Validate stock for each order item
        error_msgs = []
        for item in self.order_items:
            valid, msg = update_stock_after_order(item['lot_no'], item['quantity'])
            if not valid:
                error_msgs.append(msg)
        if error_msgs:
            err_text = "\n".join(error_msgs)
            QMessageBox.critical(self, "Stock Error", f"Order submission failed:\n{err_text}")
            return

        # Add order header and items if all validations pass
        order_id = add_order(party_name, gadi_no, order_date)
        for item in self.order_items:
            add_order_item(order_id, item['lot_no'], item['quantity'], item['product_description'])
        QMessageBox.information(self, "Success", "Order submitted successfully!")
        # Clear fields and list after submission
        self.party_name_input.clear()
        self.gadi_no_input.clear()
        self.order_items = []
        self.items_list.clear()
        self.order_date_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

class StockManagementTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.lot_no_input = QLineEdit()
        self.prod_desc_input = QLineEdit()
        self.stock_qty_input = QSpinBox()
        self.stock_qty_input.setMinimum(1)
        form_layout.addRow("Lot No:", self.lot_no_input)
        form_layout.addRow("Product Description:", self.prod_desc_input)
        form_layout.addRow("Quantity to Add:", self.stock_qty_input)
        layout.addLayout(form_layout)
        self.add_stock_btn = QPushButton("Add/Update Stock")
        self.add_stock_btn.clicked.connect(self.add_stock)
        layout.addWidget(self.add_stock_btn)
        self.setLayout(layout)
        
    def add_stock(self):
        lot_no = self.lot_no_input.text().strip()
        prod_desc = self.prod_desc_input.text().strip()
        qty = self.stock_qty_input.value()
        if lot_no and prod_desc:
            add_stock(lot_no, prod_desc, qty)
            QMessageBox.information(self, "Success", "Stock updated successfully!")
            self.lot_no_input.clear()
            self.prod_desc_input.clear()
            self.stock_qty_input.setValue(1)
        else:
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")

class StockReportTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.refresh_btn = QPushButton("Refresh Stock Report")
        self.refresh_btn.clicked.connect(self.load_stock)
        layout.addWidget(self.refresh_btn)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Lot No", "Product Description", "Quantity"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.load_stock()
        
    def load_stock(self):
        data = get_stock()
        self.table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

class ViewOrdersTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.refresh_btn = QPushButton("Refresh Orders")
        self.refresh_btn.clicked.connect(self.load_orders)
        layout.addWidget(self.refresh_btn)
        self.orders_list = QListWidget()
        self.orders_list.itemClicked.connect(self.show_order_details)
        layout.addWidget(self.orders_list)
        self.order_details = QTextEdit()
        self.order_details.setReadOnly(True)
        layout.addWidget(QLabel("Order Details:"))
        layout.addWidget(self.order_details)
        self.setLayout(layout)
        self.load_orders()
        
    def load_orders(self):
        self.orders_list.clear()
        self.order_details.clear()
        orders = get_orders()
        for order in orders:
            order_id, party_name, gadi_no, order_date = order
            item_text = f"ID: {order_id} | Party: {party_name} | Vehicle: {gadi_no} | Date: {order_date}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, order_id)
            self.orders_list.addItem(list_item)
            
    def show_order_details(self, item):
        order_id = item.data(Qt.UserRole)
        items = get_order_items(order_id)
        details = ""
        for order_item in items:
            lot_no, quantity, prod_desc = order_item
            details += f"Lot No: {lot_no} | Quantity: {quantity} | Description: {prod_desc}\n"
        self.order_details.setPlainText(details)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventory Management System")
        self.resize(800, 600)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.place_order_tab = PlaceOrderTab()
        self.stock_mgmt_tab = StockManagementTab()
        self.stock_report_tab = StockReportTab()
        self.view_orders_tab = ViewOrdersTab()
        
        self.tabs.addTab(self.place_order_tab, "Place Order")
        self.tabs.addTab(self.stock_mgmt_tab, "Stock Management")
        self.tabs.addTab(self.stock_report_tab, "Stock Report")
        self.tabs.addTab(self.view_orders_tab, "View Orders")

# ---------------------------
# Main Application Entry
# ---------------------------
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
