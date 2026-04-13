import sys
import os
import shutil
from PyQt6 import QtWidgets, QtCore, QtGui
import psycopg2
from psycopg2 import extras

DB_CONFIG = {
    "dbname": "ShoesStore",
    "user": "mae",       
    "password": "",      
    "host": "localhost",
    "port": "5432"
}

STYLE_SHEET = """
    QWidget { background-color: #FFFFFF; font-family: "Times New Roman"; font-size: 14px; color: #000000; }
    QPushButton { background-color: #00FA9A; border: 1px solid #7FFF00; padding: 8px; border-radius: 5px; font-weight: bold; }
    QPushButton:hover { background-color: #7FFF00; }
    QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox { border: 2px solid #7FFF00; padding: 5px; background-color: #FFFFFF; }
    QScrollArea { border: 1px solid #7FFF00; }
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class DatabaseManager:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(cursor_factory=extras.RealDictCursor)
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Ошибка БД", f"Не удалось подключиться к базе: {e}")
            sys.exit()

    def get_user(self, login, password):
        self.cursor.execute('SELECT u.*, r.role_name FROM "User" u JOIN role r ON u.id_role = r.id_role WHERE login=%s AND password=%s', (login, password))
        return self.cursor.fetchone()

    def get_products(self, search="", supplier_id=None, sort_mode=None):
        query = """
            SELECT p.*, c.category_name, m.manufacturer_name, s.supplier_name 
            FROM product p
            LEFT JOIN category c ON p.id_category = c.id_category
            LEFT JOIN manufacturer m ON p.id_manufacturer = m.id_manufacturer
            LEFT JOIN supplier s ON p.id_supplier = s.id_supplier
            WHERE (p.name ILIKE %s OR p.description ILIKE %s OR p.article ILIKE %s)
        """
        params = [f'%{search}%', f'%{search}%', f'%{search}%']
        if supplier_id:
            query += " AND p.id_supplier = %s"
            params.append(supplier_id)
        if sort_mode == "ASC": query += " ORDER BY p.stock_quantity ASC"
        elif sort_mode == "DESC": query += " ORDER BY p.stock_quantity DESC"
        self.cursor.execute(query, tuple(params))
        return self.cursor.fetchall()

    def delete_product(self, article):
        try:
            self.cursor.execute("SELECT 1 FROM orderproduct WHERE article = %s", (article,))
            if self.cursor.fetchone(): return False
            self.cursor.execute("DELETE FROM product WHERE article = %s", (article,))
            return True
        except: return False

    def get_all(self, table):
        self.cursor.execute(f"SELECT * FROM {table}")
        return self.cursor.fetchall()

def get_logo_pixmap(size):
    search_dirs = [os.path.join(BASE_DIR, "import"), BASE_DIR]
    names = ["Icon.png", "Icon.JPG", "Icon.ico", "icon.png", "logo.png"]
    for d in search_dirs:
        for name in names:
            full_path = os.path.join(d, name)
            if os.path.exists(full_path):
                pix = QtGui.QPixmap(full_path)
                if not pix.isNull():
                    return pix.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
    return None

def get_placeholder_pixmap(w, h):
    search_paths = [
        os.path.join(BASE_DIR, "import", "picture.png"),
        os.path.join(BASE_DIR, "picture.png")
    ]
    for path in search_paths:
        if os.path.exists(path):
            pix = QtGui.QPixmap(path)
            if not pix.isNull():
                return pix.scaled(w, h, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
    
    pix = QtGui.QPixmap(w, h)
    pix.fill(QtGui.QColor("lightgray"))
    return pix

class OrdersWindow(QtWidgets.QDialog):
    def __init__(self, db):
        super().__init__()
        self.setWindowTitle("Просмотр заказов — ООО Обувь") 
        self.resize(900, 500)
        layout = QtWidgets.QVBoxLayout(self)

        btn_back = QtWidgets.QPushButton("← НАЗАД В КАТАЛОГ")
        btn_back.clicked.connect(self.close)
        layout.addWidget(btn_back, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        self.table = QtWidgets.QTableWidget()
        try:
            orders = db.get_all('"Order"') 
            if not orders:
                QtWidgets.QMessageBox.information(self, "Информация", "Список заказов пуст.")
            
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Дата заказа", "Доставка", "Статус", "Код"])
            self.table.setRowCount(len(orders))
            
            for i, row in enumerate(orders):
                self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(row.get('id_order', ''))))
                self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(row.get('order_date', ''))))
                self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(row.get('delivery_date', ''))))
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(row.get('status', ''))))
                self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(row.get('receipt_code', ''))))
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка данных", f"Не удалось загрузить список заказов: {e}")
        
        layout.addWidget(self.table)

class ProductEditDialog(QtWidgets.QDialog):
    def __init__(self, db, product=None):
        super().__init__()
        self.db, self.product = db, product
        self.setWindowTitle("Редактирование" if product else "Добавление товара")
        self.setFixedSize(550, 650)
        self.photo_path = product['photo'] if product else ""
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.art = QtWidgets.QLineEdit(product['article'] if product else "")
        if product: self.art.setReadOnly(True)
        
        self.name = QtWidgets.QLineEdit(product['name'] if product else "")
        self.desc = QtWidgets.QTextEdit(product['description'] if product else "")
        self.price = QtWidgets.QDoubleSpinBox(); self.price.setRange(0, 1000000); self.price.setValue(float(product['price']) if product else 0)
        self.qty = QtWidgets.QSpinBox(); self.qty.setRange(0, 10000); self.qty.setValue(product['stock_quantity'] if product else 0)
        self.disc = QtWidgets.QSpinBox(); self.disc.setRange(0, 100); self.disc.setValue(product['discount'] if product else 0)

        self.cat_cb = QtWidgets.QComboBox()
        for c in db.get_all("category"): self.cat_cb.addItem(c['category_name'], c['id_category'])
        self.man_cb = QtWidgets.QComboBox()
        for m in db.get_all("manufacturer"): self.man_cb.addItem(m['manufacturer_name'], m['id_manufacturer'])
        self.supp_cb = QtWidgets.QComboBox()
        for s in db.get_all("supplier"): self.supp_cb.addItem(s['supplier_name'], s['id_supplier'])

        self.img_lbl = QtWidgets.QLabel(); self.img_lbl.setFixedSize(300, 180)
        self.update_preview()

        btn_img = QtWidgets.QPushButton("Загрузить фото")
        btn_img.clicked.connect(self.change_photo)

        form.addRow("Артикул:", self.art); form.addRow("Наименование:", self.name)
        form.addRow("Категория:", self.cat_cb); form.addRow("Производитель:", self.man_cb)
        form.addRow("Поставщик:", self.supp_cb); form.addRow("Цена:", self.price)
        form.addRow("Кол-во:", self.qty); form.addRow("Скидка (%):", self.disc)
        form.addRow("Описание:", self.desc)
        layout.addLayout(form)
        layout.addWidget(self.img_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn_img)

        btn_save = QtWidgets.QPushButton("СОХРАНИТЬ")
        btn_save.clicked.connect(self.save)
        layout.addWidget(btn_save)

    def update_preview(self):
        full_path = os.path.join(BASE_DIR, "import", self.photo_path) if self.photo_path else ""
        if self.photo_path and os.path.exists(full_path):
            pix = QtGui.QPixmap(full_path).scaled(300, 180, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        else:
            pix = get_placeholder_pixmap(300, 180)
        self.img_lbl.setPixmap(pix)

    def change_photo(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Выбор изображения", "", "Images (*.jpg *.png)")
        if file:
            new_name = os.path.basename(file)
            import_dir = os.path.join(BASE_DIR, "import")
            if not os.path.exists(import_dir): os.makedirs(import_dir)
            shutil.copy(file, os.path.join(import_dir, new_name))
            self.photo_path = new_name
            self.update_preview()
    
    def save(self):
        try:
            data = (self.name.text(), "шт.", self.price.value(), self.disc.value(), 
                    self.man_cb.currentData(), self.supp_cb.currentData(), self.cat_cb.currentData(), 
                    self.qty.value(), self.desc.toPlainText(), self.photo_path)
            if self.product:
                query = "UPDATE product SET name=%s, unit=%s, price=%s, discount=%s, id_manufacturer=%s, id_supplier=%s, id_category=%s, stock_quantity=%s, description=%s, photo=%s WHERE article=%s"
                self.db.cursor.execute(query, data + (self.art.text(),))
            else:
                query = "INSERT INTO product (name, unit, price, discount, id_manufacturer, id_supplier, id_category, stock_quantity, description, photo, article) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                self.db.cursor.execute(query, data + (self.art.text(),))
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

class ProductItem(QtWidgets.QFrame):
    def __init__(self, p, parent_win):
        super().__init__()
        self.p, self.parent_win = p, parent_win
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        qty = p.get('stock_quantity', 0)
        disc = p.get('discount', 0) or 0
        if disc > 15: self.setStyleSheet("background-color: #2E8B57; color: white;")
        
        lay = QtWidgets.QHBoxLayout(self)
        img_name = p.get('photo')
        
        full_path = os.path.join(BASE_DIR, "import", img_name) if img_name else ""
        if img_name and os.path.exists(full_path):
            pix = QtGui.QPixmap(full_path).scaled(130, 130, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        else:
            pix = get_placeholder_pixmap(130, 130)
        
        lbl_img = QtWidgets.QLabel(); lbl_img.setFixedSize(130, 130)
        lbl_img.setPixmap(pix)
        lay.addWidget(lbl_img)

        info = QtWidgets.QVBoxLayout()
        info.addWidget(QtWidgets.QLabel(f"<b>{p['name']}</b> | {p['category_name']}"))
        desc = QtWidgets.QLabel(f"<i>{p['description']}</i>"); desc.setWordWrap(True); info.addWidget(desc)
        info.addWidget(QtWidgets.QLabel(f"Производитель: {p['manufacturer_name']}"))
        info.addWidget(QtWidgets.QLabel(f"Поставщик: {p['supplier_name']}"))
        qty_lbl = QtWidgets.QLabel()
        if qty == 0:
            qty_lbl.setText("<b>Нет на складе</b>")
            qty_lbl.setStyleSheet("color: #00BFFF;")
        else:
            qty_lbl.setText(f"На складе: {qty} шт.")
        info.addWidget(qty_lbl)
        lay.addLayout(info, 2)

        price_lay = QtWidgets.QVBoxLayout(); price_lay.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        base_price = float(p['price'])
        if disc > 0:
            old_p = QtWidgets.QLabel(f"{base_price} р."); old_p.setStyleSheet("color: red; text-decoration: line-through;")
            new_p = QtWidgets.QLabel(f"{base_price * (1 - disc/100):.2f} р."); new_p.setStyleSheet("font-size: 18px; font-weight: bold;")
            price_lay.addWidget(old_p); price_lay.addWidget(new_p)
        else:
            reg_p = QtWidgets.QLabel(f"{base_price} р."); reg_p.setStyleSheet("font-size: 18px; font-weight: bold;")
            price_lay.addWidget(reg_p)
        
        price_lay.addWidget(QtWidgets.QLabel(f"Скидка: {disc}%"))
        lay.addLayout(price_lay, 1)

        if parent_win.user and parent_win.user.get('role_name') == 'Администратор':
            btns_lay = QtWidgets.QVBoxLayout()
            btn_edit = QtWidgets.QPushButton("РЕДАКТИРОВАТЬ")
            btn_edit.clicked.connect(lambda: parent_win.open_edit(self.p))
            btn_del = QtWidgets.QPushButton("УДАЛИТЬ")
            btn_del.setStyleSheet("background-color: #FF4500; color: white;")
            btn_del.clicked.connect(self.delete_me)
            btns_lay.addWidget(btn_edit); btns_lay.addWidget(btn_del)
            lay.addLayout(btns_lay)

    def delete_me(self):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Подтверждение удаления")
        msg.setText(f"Вы уверены, что хотите удалить товар: {self.p['name']}?")
        msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
        
        yes_button = msg.addButton("Да", QtWidgets.QMessageBox.ButtonRole.YesRole)
        no_button = msg.addButton("Нет", QtWidgets.QMessageBox.ButtonRole.NoRole)
        
        msg.exec()
        
        if msg.clickedButton() == yes_button:
            if self.parent_win.db.delete_product(self.p['article']):
                self.parent_win.update_list()
        else:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Невозможно удалить товар, так как он присутствует в заказах!")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, db, user, login_win):
        super().__init__()
        self.db, self.user, self.login_win = db, user, login_win
        self.edit_active = False
        self.setWindowTitle("ООО Обувь - Каталог"); self.resize(1100, 850)

        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        header = QtWidgets.QHBoxLayout()
        logo_label = QtWidgets.QLabel(); logo_label.setFixedSize(60, 60)
        logo_label.setStyleSheet("background-color: #7FFF00; border-radius: 30px;")
        logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pix = get_logo_pixmap(40)
        if pix: logo_label.setPixmap(pix)
        header.addWidget(logo_label)
        
        header.addWidget(QtWidgets.QLabel("<h1>КАТАЛОГ</h1>"))
        header.addStretch()
        header.addWidget(QtWidgets.QLabel(f"<b>{user['fio'] if user else 'Гость'}</b>"))
        btn_exit = QtWidgets.QPushButton("ВЫХОД"); btn_exit.clicked.connect(self.logout); header.addWidget(btn_exit)
        layout.addLayout(header)

        role = user.get('role_name') if user else "Гость"
        if role in ["Администратор", "Менеджер"]:
            self.search = QtWidgets.QLineEdit(placeholderText="Поиск...")
            self.search.textChanged.connect(self.update_list)
            self.sort_cb = QtWidgets.QComboBox(); self.sort_cb.addItems(["Кол-во", "По возр.", "По убыв."])
            self.sort_cb.currentIndexChanged.connect(self.update_list)
            self.supp_cb = QtWidgets.QComboBox(); self.supp_cb.addItem("Все поставщики", None)
            for s in db.get_all("supplier"): self.supp_cb.addItem(s['supplier_name'], s['id_supplier'])
            self.supp_cb.currentIndexChanged.connect(self.update_list)
            
            flay = QtWidgets.QHBoxLayout()
            flay.addWidget(self.search); flay.addWidget(self.sort_cb); flay.addWidget(self.supp_cb)
            layout.addLayout(flay)
            
            btn_orders = QtWidgets.QPushButton("ЗАКАЗЫ"); btn_orders.clicked.connect(lambda: OrdersWindow(self.db).exec())
            header.insertWidget(2, btn_orders)
        else:
            self.search = QtWidgets.QLineEdit(); self.sort_cb = QtWidgets.QComboBox(); self.supp_cb = QtWidgets.QComboBox()

        self.scroll = QtWidgets.QScrollArea(); self.content = QtWidgets.QWidget()
        self.list_lay = QtWidgets.QVBoxLayout(self.content); self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.content); layout.addWidget(self.scroll)

        if role == "Администратор":
            btn_add = QtWidgets.QPushButton("+ ДОБАВИТЬ ТОВАР"); btn_add.clicked.connect(lambda: self.open_edit(None)); layout.addWidget(btn_add)
        self.update_list()

    def update_list(self):
        while self.list_lay.count():
            child = self.list_lay.takeAt(0); w = child.widget()
            if w: w.deleteLater()
        s_mode = {1: "ASC", 2: "DESC"}.get(self.sort_cb.currentIndex())
        prods = self.db.get_products(self.search.text(), self.supp_cb.currentData(), s_mode)
        for p in prods: self.list_lay.addWidget(ProductItem(p, self))
        self.list_lay.addStretch()

    def open_edit(self, p):
        if self.edit_active: return
        self.edit_active = True
        if ProductEditDialog(self.db, p).exec(): self.update_list()
        self.edit_active = False

    def logout(self): self.login_win.show(); self.close()

class LoginWin(QtWidgets.QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Авторизация"); self.setFixedSize(350, 400)
        lay = QtWidgets.QVBoxLayout(self)
        
        logo = QtWidgets.QLabel(); logo.setFixedSize(120, 120); logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background-color: #7FFF00; border-radius: 60px;")
        pix = get_logo_pixmap(80)
        if pix: logo.setPixmap(pix)
        lay.addWidget(logo, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.login = QtWidgets.QLineEdit(placeholderText="Логин")
        self.pw = QtWidgets.QLineEdit(placeholderText="Пароль", echoMode=QtWidgets.QLineEdit.EchoMode.Password)
        btn_in = QtWidgets.QPushButton("ВОЙТИ"); btn_in.clicked.connect(self.auth)
        btn_guest = QtWidgets.QPushButton("ВОЙТИ КАК ГОСТЬ"); btn_guest.clicked.connect(lambda: self.start_main(None))
        lay.addWidget(self.login); lay.addWidget(self.pw); lay.addWidget(btn_in); lay.addWidget(btn_guest)

    def auth(self):
        u = self.db.get_user(self.login.text(), self.pw.text())
        if u: self.start_main(u)
        else: QtWidgets.QMessageBox.warning(self, "Ошибка", "Неверные данные")

    def start_main(self, user):
        self.main = MainWindow(self.db, user, self); self.main.show(); self.hide()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv); app.setStyleSheet(STYLE_SHEET)
    db = DatabaseManager()
    LoginWin(db).show()
    sys.exit(app.exec())