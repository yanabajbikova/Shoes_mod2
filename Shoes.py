import sys
import os
import shutil
import random
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

    def get_columns(self, table_name):
        clean_name = table_name.replace('"', '')
        self.cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{clean_name}'")
        return [c['column_name'] for c in self.cursor.fetchall()]

    def get_all_orders(self):
        order_cols = self.get_columns('Order')
        point_cols = self.get_columns('pickuppoint')
        
        fk_order = "id_pickup_point" if "id_pickup_point" in order_cols else ("id_point" if "id_point" in order_cols else None)
        pk_point = "id_pickup_point" if "id_pickup_point" in point_cols else ("id_point" if "id_point" in point_cols else None)
        
        if fk_order and pk_point:
            query = f'SELECT o.*, p.address FROM "Order" o LEFT JOIN pickuppoint p ON o.{fk_order} = p.{pk_point}'
        else:
            query = 'SELECT * FROM "Order"'
        
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_all(self, table):
        self.cursor.execute(f"SELECT * FROM {table}")
        return self.cursor.fetchall()

    def delete_product(self, article):
        try:
            self.cursor.execute("SELECT 1 FROM orderproduct WHERE article = %s", (article,))
            if self.cursor.fetchone(): return False
            self.cursor.execute("DELETE FROM product WHERE article = %s", (article,))
            return True
        except: return False

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
    path = os.path.join(BASE_DIR, "import", "picture.png")
    if os.path.exists(path):
        pix = QtGui.QPixmap(path)
        if not pix.isNull(): return pix.scaled(w, h, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
    pix = QtGui.QPixmap(w, h); pix.fill(QtGui.QColor("lightgray"))
    return pix

class OrderEditDialog(QtWidgets.QDialog):
    def __init__(self, db, order=None):
        super().__init__()
        self.db, self.order = db, order
        self.setWindowTitle("Состав заказа" if order else "Новый заказ")
        self.setMinimumSize(650, 650)
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        
        self.id_field = QtWidgets.QLineEdit(str(order['id_order']) if order else "Авто")
        self.id_field.setReadOnly(True)
        
        self.status_cb = QtWidgets.QComboBox()
        self.status_cb.addItems(["Новый", "Завершен", "К получению"])
        if order: self.status_cb.setCurrentText(str(order['status']))

        self.order_date_edit = QtWidgets.QDateEdit(calendarPopup=True)
        o_date = self.order.get('order_date') if self.order else QtCore.QDate.currentDate()
        self.order_date_edit.setDate(o_date)

        self.delivery_date_edit = QtWidgets.QDateEdit(calendarPopup=True)
        d_date = self.order.get('delivery_date') if self.order else QtCore.QDate.currentDate().addDays(3)
        self.delivery_date_edit.setDate(d_date)

        self.point_cb = QtWidgets.QComboBox()
        points = self.db.get_all("pickuppoint")
        for p in points:
            addr = p.get('address') or p.get('pickup_point_address') or "Пункт выдачи"
            p_id = p.get('id_pickup_point') or p.get('id_point')
            self.point_cb.addItem(addr, p_id)
        
        if order:
            target_id = order.get('id_pickup_point') or order.get('id_point')
            idx = self.point_cb.findData(target_id)
            if idx >= 0: self.point_cb.setCurrentIndex(idx)

        form.addRow("ID Заказа:", self.id_field)
        form.addRow("Статус:", self.status_cb)
        form.addRow("Пункт выдачи:", self.point_cb)
        form.addRow("Дата заказа:", self.order_date_edit)
        form.addRow("Дата выдачи:", self.delivery_date_edit)
        layout.addLayout(form)

        layout.addWidget(QtWidgets.QLabel("<b>Товары в заказе:</b>"))
        self.prod_table = QtWidgets.QTableWidget(0, 3)
        self.prod_table.setHorizontalHeaderLabels(["Артикул товара", "Кол-во", "Действие"])
        self.prod_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.prod_table)

        add_p_btn = QtWidgets.QPushButton("+ Добавить товар")
        add_p_btn.clicked.connect(self.add_product_row)
        layout.addWidget(add_p_btn)

        self.all_products = self.db.get_all("product")
        if order: self.load_order_products()

        btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("СОХРАНИТЬ ВСЁ")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet("background-color: #7FFF00; font-weight: bold;")
        save_btn.clicked.connect(self.save_all)
        
        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn); btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def add_product_row(self, article="", qty=1):
        row_idx = self.prod_table.rowCount()
        self.prod_table.insertRow(row_idx)
        
        cb = QtWidgets.QComboBox()
        for p in self.all_products:
            cb.addItem(f"{p['article']} ({p['name']})", p['article'])
        if article:
            idx = cb.findData(article)
            if idx >= 0: cb.setCurrentIndex(idx)
        self.prod_table.setCellWidget(row_idx, 0, cb)
        
        sb = QtWidgets.QSpinBox(); sb.setRange(1, 100); sb.setValue(int(qty))
        self.prod_table.setCellWidget(row_idx, 1, sb)
        
        btn = QtWidgets.QPushButton("Удалить")
        btn.setStyleSheet("background-color: #FF4500; color: white;")
        btn.clicked.connect(lambda: self.prod_table.removeRow(self.prod_table.indexAt(btn.pos()).row()))
        self.prod_table.setCellWidget(row_idx, 2, btn)

    def load_order_products(self):
        query = "SELECT article, quantity FROM orderproduct WHERE id_order = %s"
        self.db.cursor.execute(query, (self.order['id_order'],))
        for item in self.db.cursor.fetchall():
            self.add_product_row(item['article'], item['quantity'])

    def save_all(self):
        try:
            import datetime, random
            
            date_o = self.order_date_edit.date().toPyDate()
            date_d = self.delivery_date_edit.date().toPyDate()
            status = self.status_cb.currentText()
            p_id = self.point_cb.currentData()
            
            cols = self.db.get_columns('Order')
            fk_point = 'id_pickup_point' if 'id_pickup_point' in cols else 'id_point'

            if self.order:
                oid = self.order['id_order']
                query = f"""
                    UPDATE "Order" SET order_date=%s, delivery_date=%s, 
                    status=%s, {fk_point}=%s WHERE id_order=%s
                """
                self.db.cursor.execute(query, (date_o, date_d, status, p_id, oid))
                self.db.cursor.execute("DELETE FROM orderproduct WHERE id_order = %s", (oid,))
            else:
                self.db.cursor.execute('SELECT COALESCE(MAX(id_order), 0) + 1 as next_id FROM "Order"')
                oid = self.db.cursor.fetchone()['next_id']
                r_code = random.randint(100, 999)
                
                query = f"""
                    INSERT INTO "Order" (id_order, order_date, delivery_date, {fk_point}, receipt_code, status) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                self.db.cursor.execute(query, (oid, date_o, date_d, p_id, r_code, status))

            for i in range(self.prod_table.rowCount()):
                art = self.prod_table.cellWidget(i, 0).currentData()
                qty = self.prod_table.cellWidget(i, 1).value()
                if art:
                    self.db.cursor.execute("INSERT INTO orderproduct (id_order, article, quantity) VALUES (%s, %s, %s)", (oid, art, qty))
            
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

class ProductEditDialog(QtWidgets.QDialog):
    def __init__(self, db, product=None):
        super().__init__()
        self.db, self.product = db, product
        self.setWindowTitle("Редактирование" if product else "Добавление товара")
        self.setFixedSize(550, 650)
        self.photo_path = product['photo'] if product else ""
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.art = QtWidgets.QLineEdit(product['article'] if product else ""); 
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

        self.img_lbl = QtWidgets.QLabel(); self.img_lbl.setFixedSize(300, 180); self.update_preview()
        btn_img = QtWidgets.QPushButton("Загрузить фото"); btn_img.clicked.connect(self.change_photo)

        form.addRow("Артикул:", self.art); form.addRow("Наименование:", self.name)
        form.addRow("Категория:", self.cat_cb); form.addRow("Производитель:", self.man_cb)
        form.addRow("Поставщик:", self.supp_cb); form.addRow("Цена:", self.price)
        form.addRow("Кол-во:", self.qty); form.addRow("Скидка (%):", self.disc); form.addRow("Описание:", self.desc)
        layout.addLayout(form); layout.addWidget(self.img_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn_img)
        btn_save = QtWidgets.QPushButton("СОХРАНИТЬ"); btn_save.clicked.connect(self.save); layout.addWidget(btn_save)

    def update_preview(self):
        full_path = os.path.join(BASE_DIR, "import", self.photo_path) if self.photo_path else ""
        pix = QtGui.QPixmap(full_path).scaled(300, 180) if os.path.exists(full_path) else get_placeholder_pixmap(300, 180)
        self.img_lbl.setPixmap(pix)

    def change_photo(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Выбор фото", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            name = os.path.basename(path)
            shutil.copy(path, os.path.join(BASE_DIR, "import", name))
            self.photo_path = name; self.update_preview()

    def save(self):
        d = (
            self.art.text(), 
            self.name.text(), 
            self.desc.toPlainText(), 
            self.photo_path, 
            self.cat_cb.currentData(), 
            self.man_cb.currentData(), 
            self.supp_cb.currentData(), 
            self.price.value(), 
            self.qty.value(), 
            self.disc.value(),
            'шт.' 
        )
        
        try:
            if self.product:
                self.db.cursor.execute("""
                    UPDATE product SET 
                    name=%s, description=%s, photo=%s, id_category=%s, 
                    id_manufacturer=%s, id_supplier=%s, price=%s, 
                    stock_quantity=%s, discount=%s, unit=%s 
                    WHERE article=%s
                """, d[1:10] + ('шт.', d[0]))
            else:
                self.db.cursor.execute("""
                    INSERT INTO product 
                    (article, name, description, photo, id_category, 
                    id_manufacturer, id_supplier, price, stock_quantity, discount, unit) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, d)
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка БД", f"Не удалось сохранить товар: {e}")

class OrdersWindow(QtWidgets.QDialog):
    def __init__(self, db, user_role):
        super().__init__()
        self.db, self.user_role = db, user_role
        self.setWindowTitle("Управление заказами"); self.resize(900, 500)
        layout = QtWidgets.QVBoxLayout(self)
        if user_role == 'Администратор':
            btn = QtWidgets.QPushButton("+ НОВЫЙ ЗАКАЗ"); btn.clicked.connect(self.add_order); layout.addWidget(btn)
        self.table = QtWidgets.QTableWidget(); layout.addWidget(self.table)
        self.load_data()
    
    def load_data(self):
        orders = self.db.get_all_orders()
        self.table.setRowCount(len(orders))
        cols = ["ID", "Статус", "Адрес выдачи", "Дата заказа", "Дата выдачи"]
        if self.user_role == 'Администратор': 
            cols += ["Действия"]
        
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        for i, row in enumerate(orders): 
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(row['id_order'])))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(row['status'])))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(row.get('address') or 'Не указан')))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(row['order_date'])))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(row['delivery_date'])))
            
            if self.user_role == 'Администратор':
                w = QtWidgets.QWidget()
                l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(5, 2, 5, 2); l.setSpacing(10)                
                
                edit_btn = QtWidgets.QPushButton("✎"); edit_btn.setToolTip("Редактировать заказ"); edit_btn.setFixedSize(30, 30) 
                edit_btn.setStyleSheet("QPushButton { background-color: #00FF7F; color: black; border: 1px solid #7FFF00; font-size: 14px; border-radius: 5px; }")
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_order(r))
                
                del_btn = QtWidgets.QPushButton("🗑"); del_btn.setToolTip("Удалить заказ"); del_btn.setFixedSize(30, 30) 
                del_btn.setStyleSheet("QPushButton { background-color: #FF4500; color: white; border: 1px solid #7FFF00; font-size: 14px; border-radius: 5px; }")
                del_btn.clicked.connect(lambda checked, oid=row['id_order']: self.delete_order(oid))
                
                l.addWidget(edit_btn); l.addWidget(del_btn);
                self.table.setCellWidget(i, 5, w)
        self.table.resizeColumnsToContents()

    def add_order(self):
        if OrderEditDialog(self.db).exec(): self.load_data()

    def edit_order(self, order):
        if OrderEditDialog(self.db, order).exec(): self.load_data()

    def delete_order(self, id):
        if QtWidgets.QMessageBox.question(self, "Удаление", "Удалить заказ?") == QtWidgets.QMessageBox.StandardButton.Yes:
            self.db.cursor.execute('DELETE FROM orderproduct WHERE id_order=%s', (id,))
            self.db.cursor.execute('DELETE FROM "Order" WHERE id_order=%s', (id,))
            self.load_data()

class ProductItem(QtWidgets.QFrame):
    def __init__(self, p, parent_win):
        super().__init__()
        self.p, self.parent_win = p, parent_win
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        qty, disc = p.get('stock_quantity', 0), (p.get('discount', 0) or 0)
        if disc > 15: self.setStyleSheet("background-color: #2E8B57; color: white;")
        
        lay = QtWidgets.QHBoxLayout(self)
        img_name = p.get('photo')
        full_path = os.path.join(BASE_DIR, "import", img_name) if img_name else ""
        pix = QtGui.QPixmap(full_path).scaled(130, 130) if os.path.exists(full_path) else get_placeholder_pixmap(130, 130)
        lbl_img = QtWidgets.QLabel(); lbl_img.setFixedSize(130, 130); lbl_img.setPixmap(pix); lay.addWidget(lbl_img)

        info = QtWidgets.QVBoxLayout()
        info.addWidget(QtWidgets.QLabel(f"<b>{p['name']}</b> | Арт: {p['article']}"))
        info.addWidget(QtWidgets.QLabel(f"Категория: {p['category_name']}"))
        desc = QtWidgets.QLabel(f"<i>{p['description']}</i>"); desc.setWordWrap(True); info.addWidget(desc)
        info.addWidget(QtWidgets.QLabel(f"Производитель: {p['manufacturer_name']}\nПоставщик: {p['supplier_name']}"))
        q_lbl = QtWidgets.QLabel("<b>Нет на складе</b>" if qty == 0 else f"На складе: {qty} шт.")
        if qty == 0: q_lbl.setStyleSheet("color: #00BFFF;")
        info.addWidget(q_lbl); lay.addLayout(info, 2)

        price_lay = QtWidgets.QVBoxLayout(); price_lay.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        base = float(p['price'])
        if disc > 0:
            old = QtWidgets.QLabel(f"{base} р."); old.setStyleSheet("color: red; text-decoration: line-through;")
            new = QtWidgets.QLabel(f"{base * (1 - disc/100):.2f} р."); new.setStyleSheet("font-size: 18px; font-weight: bold;")
            price_lay.addWidget(old); price_lay.addWidget(new)
        else:
            reg = QtWidgets.QLabel(f"{base} р."); reg.setStyleSheet("font-size: 18px; font-weight: bold;"); price_lay.addWidget(reg)
        price_lay.addWidget(QtWidgets.QLabel(f"Скидка: {disc}%")); lay.addLayout(price_lay, 1)

        if parent_win.user and parent_win.user.get('role_name') == 'Администратор':
            bl = QtWidgets.QVBoxLayout()
            e = QtWidgets.QPushButton("РЕДАКТИРОВАТЬ"); e.clicked.connect(lambda: parent_win.open_edit(self.p))
            d = QtWidgets.QPushButton("УДАЛИТЬ"); d.setStyleSheet("background-color: #FF4500;"); d.clicked.connect(self.del_me)
            bl.addWidget(e); bl.addWidget(d); lay.addLayout(bl)

    def del_me(self):
        if self.parent_win.db.delete_product(self.p['article']): self.parent_win.update_list()
        else: QtWidgets.QMessageBox.warning(self, "Ошибка", "Товар в заказе!")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, db, user, login_win):
        super().__init__()
        self.db, self.user, self.login_win = db, user, login_win
        self.setWindowTitle("ООО Обувь - Каталог"); self.resize(1100, 850)
        central = QtWidgets.QWidget(); self.setCentralWidget(central); layout = QtWidgets.QVBoxLayout(central)
        
        header = QtWidgets.QHBoxLayout(); logo = QtWidgets.QLabel(); logo.setFixedSize(60, 60); logo.setStyleSheet("background-color: #7FFF00; border-radius: 30px;")
        logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pix = get_logo_pixmap(40); 
        if pix: logo.setPixmap(pix)
        header.addWidget(logo); header.addWidget(QtWidgets.QLabel("<h1>КАТАЛОГ</h1>")); header.addStretch()
        header.addWidget(QtWidgets.QLabel(f"<b>{user['fio'] if user else 'Гость'}</b>"))
        exit_b = QtWidgets.QPushButton("ВЫХОД"); exit_b.clicked.connect(self.logout); header.addWidget(exit_b)
        layout.addLayout(header)

        role = user.get('role_name') if user else "Гость"
        if role in ["Администратор", "Менеджер"]:
            self.search = QtWidgets.QLineEdit(placeholderText="Поиск..."); self.search.textChanged.connect(self.update_list)
            self.sort_cb = QtWidgets.QComboBox(); self.sort_cb.addItems(["Кол-во", "По возр.", "По убыв."]); self.sort_cb.currentIndexChanged.connect(self.update_list)
            self.supp_cb = QtWidgets.QComboBox(); self.supp_cb.addItem("Все поставщики", None)
            for s in db.get_all("supplier"): self.supp_cb.addItem(s['supplier_name'], s['id_supplier'])
            self.supp_cb.currentIndexChanged.connect(self.update_list)
            f = QtWidgets.QHBoxLayout(); f.addWidget(self.search); f.addWidget(self.sort_cb); f.addWidget(self.supp_cb); layout.addLayout(f)
            ord_b = QtWidgets.QPushButton("ЗАКАЗЫ"); ord_b.clicked.connect(lambda: OrdersWindow(self.db, role).exec()); header.insertWidget(2, ord_b)
        else:
            self.search = QtWidgets.QLineEdit(); self.sort_cb = QtWidgets.QComboBox(); self.supp_cb = QtWidgets.QComboBox()

        self.scroll = QtWidgets.QScrollArea(); self.content = QtWidgets.QWidget(); self.list_lay = QtWidgets.QVBoxLayout(self.content)
        self.scroll.setWidgetResizable(True); self.scroll.setWidget(self.content); layout.addWidget(self.scroll)
        if role == "Администратор":
            ab = QtWidgets.QPushButton("+ ДОБАВИТЬ ТОВАР"); ab.clicked.connect(lambda: self.open_edit(None)); layout.addWidget(ab)
        self.update_list()

    def update_list(self):
        while self.list_lay.count():
            w = self.list_lay.takeAt(0).widget()
            if w: w.deleteLater()
        prods = self.db.get_products(self.search.text(), self.supp_cb.currentData(), {1: "ASC", 2: "DESC"}.get(self.sort_cb.currentIndex()))
        for p in prods: self.list_lay.addWidget(ProductItem(p, self))
        self.list_lay.addStretch()

    def open_edit(self, p):
        if ProductEditDialog(self.db, p).exec(): self.update_list()

    def logout(self): self.login_win.show(); self.close()

class LoginWin(QtWidgets.QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db; self.setWindowTitle("Авторизация"); self.setFixedSize(350, 400)
        lay = QtWidgets.QVBoxLayout(self); logo = QtWidgets.QLabel(); logo.setFixedSize(120, 120); logo.setStyleSheet("background-color: #7FFF00; border-radius: 60px;")
        logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pix = get_logo_pixmap(80); 
        if pix: logo.setPixmap(pix)
        lay.addWidget(logo, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.login = QtWidgets.QLineEdit(placeholderText="Логин"); self.pw = QtWidgets.QLineEdit(placeholderText="Пароль", echoMode=QtWidgets.QLineEdit.EchoMode.Password)
        lay.addWidget(self.login); lay.addWidget(self.pw)
        bi = QtWidgets.QPushButton("ВОЙТИ"); bi.clicked.connect(self.auth); bg = QtWidgets.QPushButton("ВОЙТИ КАК ГОСТЬ"); bg.clicked.connect(lambda: self.start_main(None))
        lay.addWidget(bi); lay.addWidget(bg)

    def auth(self):
        u = self.db.get_user(self.login.text(), self.pw.text())
        if u: self.start_main(u)
        else: QtWidgets.QMessageBox.warning(self, "Ошибка", "Неверные данные")

    def start_main(self, user):
        self.main = MainWindow(self.db, user, self); self.main.show(); self.hide()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv); app.setStyleSheet(STYLE_SHEET)
    db = DatabaseManager(); LoginWin(db).show(); sys.exit(app.exec())