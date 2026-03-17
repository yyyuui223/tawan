from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'my_diary_secret_key_12345'

# ข้อมูลผู้เขียนไดอารี่ (เฉพาะผม)
AUTHOR_USERNAME = "ตูน ตะวัน"
AUTHOR_AGE = "19"
AUTHOR_INSTAGRAM = "Tttwsiiiwxkakkkac"
AUTHOR_INSTAGRAM_SHOW = "ttttt___998on"  # ไอจีที่ให้คนอื่นติดต่อ

def init_db():
    conn = sqlite3.connect('diary_v2.db')
    c = conn.cursor()
    
    # ตารางผู้ใช้
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age TEXT NOT NULL,
        instagram TEXT,
        is_author INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # ตารางไดอารี่
    c.execute('''CREATE TABLE IF NOT EXISTS diaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        mood TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # ตารางคอมเม้นต์
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        diary_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL,
        content TEXT NOT NULL,
        reply TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (diary_id) REFERENCES diaries (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # ตารางอยากรู้จัก
    c.execute('''CREATE TABLE IF NOT EXISTS interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL,
        user_age TEXT NOT NULL,
        user_instagram TEXT,
        message TEXT,
        replied INTEGER DEFAULT 0,
        reply_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('diary_v2.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name')
    age = request.form.get('age')
    instagram = request.form.get('instagram')
    
    if not name or not age:
        flash('กรุณากรอกชื่อและอายุ', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # ตรวจสอบว่าเป็นผู้เขียนหรือไม่
    is_author = (name == AUTHOR_USERNAME and 
                 age == AUTHOR_AGE and 
                 instagram == AUTHOR_INSTAGRAM)
    
    # บันทึกหรืออัปเดตผู้ใช้
    user = conn.execute('SELECT * FROM users WHERE name = ? AND age = ? AND instagram = ?', 
                       (name, age, instagram)).fetchone()
    
    if not user:
        conn.execute('INSERT INTO users (name, age, instagram, is_author) VALUES (?, ?, ?, ?)',
                    (name, age, instagram, 1 if is_author else 0))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE name = ? AND age = ? AND instagram = ?', 
                          (name, age, instagram)).fetchone()
    
    conn.close()
    
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_age'] = user['age']
    session['is_author'] = user['is_author']
    
    if is_author:
        return redirect(url_for('author_dashboard'))
    else:
        return redirect(url_for('reader_dashboard'))

@app.route('/author')
def author_dashboard():
    if 'user_id' not in session or not session.get('is_author'):
        flash('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    diaries = conn.execute('SELECT * FROM diaries ORDER BY created_at DESC').fetchall()
    
    # ดึงคอมเม้นต์ล่าสุด
    comments = conn.execute('''
        SELECT c.*, d.title as diary_title 
        FROM comments c 
        JOIN diaries d ON c.diary_id = d.id 
        ORDER BY c.created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    # ดึงรายการอยากรู้จัก
    interests = conn.execute('''
        SELECT * FROM interests 
        ORDER BY created_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('author_dashboard.html', 
                         diaries=diaries, 
                         comments=comments, 
                         interests=interests)

@app.route('/reader')
def reader_dashboard():
    if 'user_id' not in session or session.get('is_author'):
        return redirect(url_for('author_dashboard'))
    
    conn = get_db_connection()
    diaries = conn.execute('SELECT * FROM diaries ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('reader_dashboard.html', 
                         diaries=diaries,
                         user_name=session.get('user_name'))

@app.route('/diary/<int:diary_id>')
def view_diary(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    diary = conn.execute('SELECT * FROM diaries WHERE id = ?', (diary_id,)).fetchone()
    comments = conn.execute('''
        SELECT * FROM comments 
        WHERE diary_id = ? 
        ORDER BY created_at DESC
    ''', (diary_id,)).fetchall()
    conn.close()
    
    if not diary:
        flash('ไม่พบไดอารี่', 'error')
        return redirect(url_for('reader_dashboard'))
    
    return render_template('view_diary.html', 
                         diary=diary, 
                         comments=comments,
                         is_author=session.get('is_author', False),
                         user_id=session.get('user_id'),
                         user_name=session.get('user_name'))

@app.route('/add_diary', methods=['POST'])
def add_diary():
    if 'user_id' not in session or not session.get('is_author'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    title = request.form.get('title')
    content = request.form.get('content')
    mood = request.form.get('mood')
    
    if not title or not content:
        return jsonify({'success': False, 'message': 'กรุณากรอกข้อมูลให้ครบ'})
    
    conn = get_db_connection()
    conn.execute('INSERT INTO diaries (title, content, mood) VALUES (?, ?, ?)',
                (title, content, mood))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'เพิ่มไดอารี่สำเร็จ'})

@app.route('/delete_diary/<int:diary_id>', methods=['POST'])
def delete_diary(diary_id):
    if 'user_id' not in session or not session.get('is_author'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    conn = get_db_connection()
    
    # ลบคอมเม้นต์ที่เกี่ยวข้องก่อน (ON DELETE CASCADE จะจัดการให้ แต่เผื่อไว้)
    conn.execute('DELETE FROM comments WHERE diary_id = ?', (diary_id,))
    # ลบไดอารี่
    conn.execute('DELETE FROM diaries WHERE id = ?', (diary_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'ลบไดอารี่สำเร็จ'})

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'กรุณาเข้าสู่ระบบ'})
    
    data = request.json
    diary_id = data.get('diary_id')
    content = data.get('content')
    
    if not content:
        return jsonify({'success': False, 'message': 'กรุณากรอกคอมเม้นต์'})
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO comments (diary_id, user_id, user_name, content) 
        VALUES (?, ?, ?, ?)
    ''', (diary_id, session['user_id'], session['user_name'], content))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'คอมเม้นต์สำเร็จ'})

@app.route('/reply_comment', methods=['POST'])
def reply_comment():
    if 'user_id' not in session or not session.get('is_author'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.json
    comment_id = data.get('comment_id')
    reply = data.get('reply')
    
    conn = get_db_connection()
    conn.execute('UPDATE comments SET reply = ? WHERE id = ?', (reply, comment_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'ตอบกลับสำเร็จ'})

@app.route('/add_interest', methods=['POST'])
def add_interest():
    if 'user_id' not in session or session.get('is_author'):
        return jsonify({'success': False, 'message': 'ไม่สามารถดำเนินการได้'})
    
    data = request.json
    message = data.get('message', '')
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO interests (user_id, user_name, user_age, user_instagram, message) 
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], session['user_name'], session['user_age'], 
          session.get('user_instagram', ''), message))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'ส่งความสนใจเรียบร้อย'})

@app.route('/reply_interest', methods=['POST'])
def reply_interest():
    if 'user_id' not in session or not session.get('is_author'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.json
    interest_id = data.get('interest_id')
    reply = data.get('reply')
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE interests 
        SET replied = 1, reply_message = ? 
        WHERE id = ?
    ''', (reply, interest_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'ตอบกลับสำเร็จ'})

@app.route('/logout')
def logout():
    session.clear()
    flash('ออกจากระบบสำเร็จ', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=1137)
