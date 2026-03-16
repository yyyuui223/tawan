from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'mato_exe_secret_key_12345'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SLIP_FOLDER'] = 'static/slips'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

for folder in [app.config['UPLOAD_FOLDER'], app.config['SLIP_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('mato_exe.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        balance REAL DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock1 INTEGER DEFAULT 0,
        stock2 INTEGER DEFAULT 0,
        product_type INTEGER DEFAULT 1,
        download_link TEXT,
        image_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        total_price REAL NOT NULL,
        status TEXT DEFAULT 'completed',
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS topups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        slip_image TEXT,
        status TEXT DEFAULT 'pending',
        approved_by INTEGER,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (approved_by) REFERENCES users (id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    try:
        admin_hash = generate_password_hash('72732owoowx')
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                  ('Huax', admin_hash, 1))
    except:
        pass
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('mato_exe.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_balance(user_id):
    conn = get_db_connection()
    result = conn.execute('SELECT balance FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return result['balance'] if result else 0

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        conn = get_db_connection()
        try:
            hashed_password = generate_password_hash(password)
            conn.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                        (username, hashed_password, email))
            conn.commit()
            flash('ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ชื่อผู้ใช้นี้มีอยู่แล้ว', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user:
            if user['is_banned']:
                flash('บัญชีของคุณถูกระงับการใช้งาน', 'error')
            elif check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                flash('เข้าสู่ระบบสำเร็จ!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('รหัสผ่านไม่ถูกต้อง', 'error')
        else:
            flash('ไม่พบชื่อผู้ใช้', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบสำเร็จ', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    recent_orders = conn.execute('''
        SELECT o.*, p.name as product_name 
        FROM orders o 
        JOIN products p ON o.product_id = p.id 
        WHERE o.user_id = ? 
        ORDER BY o.order_date DESC 
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    recent_topups = conn.execute('''
        SELECT * FROM topups 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 3
    ''', (session['user_id'],)).fetchall()
    
    featured_products = conn.execute('''
        SELECT * FROM products 
        WHERE stock2 > 0 
        ORDER BY RANDOM() 
        LIMIT 3
    ''').fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                          user=user, 
                          orders=recent_orders,
                          topups=recent_topups,
                          featured_products=featured_products,
                          get_user_balance=get_user_balance)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    order_stats = conn.execute('''
        SELECT COUNT(*) as total_orders, 
               SUM(total_price) as total_spent 
        FROM orders 
        WHERE user_id = ? AND status = 'completed'
    ''', (session['user_id'],)).fetchone()
    
    topups = conn.execute('''
        SELECT * FROM topups 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('profile.html', user=user, order_stats=order_stats, topups=topups, get_user_balance=get_user_balance)

@app.route('/products/fake')
def products_fake():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products WHERE product_type = 1 AND stock1 > 0').fetchall()
    user_balance = get_user_balance(session['user_id'])
    conn.close()
    
    return render_template('products.html', products=products, product_type='fake', user_balance=user_balance, get_user_balance=get_user_balance)

@app.route('/products/real')
def products_real():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products WHERE product_type = 2 AND stock2 > 0').fetchall()
    user_balance = get_user_balance(session['user_id'])
    conn.close()
    
    return render_template('products.html', products=products, product_type='real', user_balance=user_balance, get_user_balance=get_user_balance)

@app.route('/buy/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'กรุณาเข้าสู่ระบบ'})
    
    conn = get_db_connection()
    
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if not product:
        return jsonify({'success': False, 'message': 'ไม่พบสินค้า'})
    
    user_balance = get_user_balance(session['user_id'])
    if user_balance < product['price']:
        return jsonify({
            'success': False, 
            'message': 'ยอดเงินไม่พอ กรุณาเติมเงิน',
            'need_topup': True,
            'balance': user_balance,
            'price': product['price']
        })
    
    stock_field = 'stock1' if product['product_type'] == 1 else 'stock2'
    current_stock = product[stock_field]
    
    if current_stock <= 0:
        return jsonify({'success': False, 'message': 'สินค้าหมด'})
    
    new_stock = current_stock - 1
    conn.execute(f'UPDATE products SET {stock_field} = ? WHERE id = ?', 
                (new_stock, product_id))
    
    new_balance = user_balance - product['price']
    conn.execute('UPDATE users SET balance = ? WHERE id = ?', 
                (new_balance, session['user_id']))
    
    conn.execute('''
        INSERT INTO orders (user_id, product_id, total_price, status) 
        VALUES (?, ?, ?, 'completed')
    ''', (session['user_id'], product_id, product['price']))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'download_link': product['download_link'],
        'message': 'ซื้อสินค้าสำเร็จ!',
        'new_balance': new_balance
    })

@app.route('/my-orders')
def my_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    orders_list = conn.execute('''
        SELECT o.*, p.name as product_name, p.download_link
        FROM orders o 
        JOIN products p ON o.product_id = p.id 
        WHERE o.user_id = ? 
        ORDER BY o.order_date DESC
    ''', (session['user_id'],)).fetchall()
    
    total = conn.execute('''
        SELECT SUM(total_price) as total 
        FROM orders 
        WHERE user_id = ? AND status = 'completed'
    ''', (session['user_id'],)).fetchone()
    
    conn.close()
    
    return render_template('orders.html', orders=orders_list, total=total['total'] or 0, get_user_balance=get_user_balance)

@app.route('/topup', methods=['GET', 'POST'])
def topup():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        amount = request.form.get('amount', type=float)
        
        if not amount or amount <= 0:
            flash('กรุณากรอกจำนวนเงินที่ถูกต้อง', 'error')
            return redirect(url_for('topup'))
        
        slip_image = None
        if 'slip' in request.files:
            file = request.files['slip']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                new_filename = f"slip_{session['user_id']}_{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['SLIP_FOLDER'], new_filename))
                slip_image = new_filename
        
        if not slip_image:
            flash('กรุณาแนบสลิปการโอนเงิน', 'error')
            return redirect(url_for('topup'))
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO topups (user_id, amount, slip_image, status)
            VALUES (?, ?, ?, 'pending')
        ''', (session['user_id'], amount, slip_image))
        conn.commit()
        conn.close()
        
        flash('ส่งคำขอเติมเงินเรียบร้อย รอแอดมินอนุมัติ', 'success')
        return redirect(url_for('profile'))
    
    return render_template('topup.html', get_user_balance=get_user_balance)

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        message = request.form['message']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO reports (user_id, title, message) 
            VALUES (?, ?, ?)
        ''', (session['user_id'], title, message))
        conn.commit()
        conn.close()
        
        flash('ส่งรายงานปัญหาเรียบร้อยแล้ว', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('report.html', get_user_balance=get_user_balance)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    product_count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    order_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    report_count = conn.execute('SELECT COUNT(*) FROM reports WHERE status = "pending"').fetchone()[0]
    topup_pending = conn.execute('SELECT COUNT(*) FROM topups WHERE status = "pending"').fetchone()[0]
    
    recent_users = conn.execute('''
        SELECT username, email, created_at 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                          user_count=user_count,
                          product_count=product_count,
                          order_count=order_count,
                          report_count=report_count,
                          topup_pending=topup_pending,
                          recent_users=recent_users,
                          get_user_balance=get_user_balance)

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin/users.html', users=users, get_user_balance=get_user_balance)

@app.route('/admin/toggle_ban/<int:user_id>')
def toggle_ban(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if user:
        new_status = 0 if user['is_banned'] else 1
        conn.execute('UPDATE users SET is_banned = ? WHERE id = ?', (new_status, user_id))
        conn.commit()
        
        action = 'แบน' if new_status == 1 else 'ปลดแบน'
        conn.close()
        return jsonify({'success': True, 'message': f'{action} ผู้ใช้เรียบร้อย'})
    
    conn.close()
    return jsonify({'success': False, 'message': 'ไม่พบผู้ใช้'})

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin/products.html', products=products, get_user_balance=get_user_balance)

@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            description = request.form.get('description', '')
            price = float(request.form['price']) if request.form['price'] else 0
            
            stock1_str = request.form.get('stock1', '0')
            stock1 = int(stock1_str) if stock1_str and stock1_str.strip() else 0
            
            stock2_str = request.form.get('stock2', '0')
            stock2 = int(stock2_str) if stock2_str and stock2_str.strip() else 0
            
            product_type = int(request.form['product_type'])
            download_link = request.form.get('download_link', '')
            
            image_file = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    new_filename = f"{uuid.uuid4().hex}.{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                    image_file = new_filename
            
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO products (name, description, price, stock1, stock2, product_type, download_link, image_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, price, stock1, stock2, product_type, download_link, image_file))
            conn.commit()
            conn.close()
            
            flash('เพิ่มสินค้าสำเร็จ!', 'success')
            return redirect(url_for('admin_products'))
            
        except Exception as e:
            flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
            return redirect(url_for('add_product'))
    
    return render_template('admin/add_product.html', get_user_balance=get_user_balance)

@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            description = request.form.get('description', '')
            price = float(request.form['price']) if request.form['price'] else 0
            
            stock1_str = request.form.get('stock1', '0')
            stock1 = int(stock1_str) if stock1_str and stock1_str.strip() else 0
            
            stock2_str = request.form.get('stock2', '0')
            stock2 = int(stock2_str) if stock2_str and stock2_str.strip() else 0
            
            product_type = int(request.form['product_type'])
            download_link = request.form.get('download_link', '')
            
            product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            image_file = product['image_file']
            
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    if image_file:
                        old_file = os.path.join(app.config['UPLOAD_FOLDER'], image_file)
                        if os.path.exists(old_file):
                            os.remove(old_file)
                    
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower()
                    new_filename = f"{uuid.uuid4().hex}.{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                    image_file = new_filename
            
            conn.execute('''
                UPDATE products 
                SET name=?, description=?, price=?, stock1=?, stock2=?, 
                    product_type=?, download_link=?, image_file=?
                WHERE id=?
            ''', (name, description, price, stock1, stock2, product_type, download_link, image_file, product_id))
            conn.commit()
            
            flash('แก้ไขสินค้าสำเร็จ!', 'success')
            return redirect(url_for('admin_products'))
            
        except Exception as e:
            flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
            return redirect(url_for('edit_product', product_id=product_id))
    
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    
    if not product:
        flash('ไม่พบสินค้า', 'error')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/edit_product.html', product=product, get_user_balance=get_user_balance)

@app.route('/admin/delete_product/<int:product_id>')
def delete_product(product_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    conn = get_db_connection()
    product = conn.execute('SELECT image_file FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if product and product['image_file']:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], product['image_file'])
        if os.path.exists(file_path):
            os.remove(file_path)
    
    conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'ลบสินค้าสำเร็จ'})

@app.route('/admin/topups')
def admin_topups():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    topups = conn.execute('''
        SELECT t.*, u.username 
        FROM topups t 
        JOIN users u ON t.user_id = u.id 
        ORDER BY 
            CASE t.status 
                WHEN 'pending' THEN 1 
                WHEN 'approved' THEN 2 
                ELSE 3 
            END,
            t.created_at DESC
    ''').fetchall()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN status = 'approved' THEN amount ELSE 0 END) as total_amount
        FROM topups
    ''').fetchone()
    
    conn.close()
    
    return render_template('admin/topups.html', topups=topups, stats=stats, get_user_balance=get_user_balance)

@app.route('/admin/approve_topup/<int:topup_id>/<action>')
def approve_topup(topup_id, action):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    conn = get_db_connection()
    topup = conn.execute('SELECT * FROM topups WHERE id = ?', (topup_id,)).fetchone()
    
    if not topup:
        conn.close()
        return jsonify({'success': False, 'message': 'ไม่พบคำขอ'})
    
    if action == 'approve':
        conn.execute('UPDATE users SET balance = balance + ? WHERE id = ?', 
                    (topup['amount'], topup['user_id']))
        conn.execute('''
            UPDATE topups 
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (session['user_id'], topup_id))
        message = 'อนุมัติการเติมเงินสำเร็จ'
    elif action == 'reject':
        conn.execute('''
            UPDATE topups 
            SET status = 'rejected', approved_by = ?, approved_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (session['user_id'], topup_id))
        message = 'ปฏิเสธการเติมเงินสำเร็จ'
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Action not valid'})
    
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': message})

@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    reports = conn.execute('''
        SELECT r.*, u.username 
        FROM reports r 
        JOIN users u ON r.user_id = u.id 
        ORDER BY r.created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('admin/reports.html', reports=reports, get_user_balance=get_user_balance)

@app.route('/admin/update_report/<int:report_id>/<status>')
def update_report(report_id, status):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    conn = get_db_connection()
    conn.execute('UPDATE reports SET status = ? WHERE id = ?', (status, report_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'อัปเดตสถานะเรียบร้อย'})

@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    orders = conn.execute('''
        SELECT o.*, u.username, p.name as product_name
        FROM orders o 
        JOIN users u ON o.user_id = u.id 
        JOIN products p ON o.product_id = p.id 
        ORDER BY o.order_date DESC
    ''').fetchall()
    
    order_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
            SUM(total_price) as total_revenue
        FROM orders
    ''').fetchone()
    
    conn.close()
    
    return render_template('admin/orders.html', orders=orders, order_stats=order_stats, get_user_balance=get_user_balance)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=1111)
