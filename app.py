import os
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import threading
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# 确保data文件夹存在
if not os.path.exists('data'):
    os.makedirs('data')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['DATABASE'] = 'data/chat_users.db'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# 初始化数据库
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

# 创建数据库表
def create_tables():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.commit()

# 在应用启动时创建数据库表
create_tables()

# 存储聊天记录
chat_history = []
# 线程锁确保线程安全
lock = threading.Lock()
# 在线用户计数
online_users = 0
# 在线用户列表
online_users_list = {}

def get_client_ip():
    """获取客户端真实IP地址"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    
    if ip.startswith('::ffff:'):
        ip = ip[7:]
    
    return ip

@app.route('/')
def index():
    """首页，根据登录状态重定向"""
    if 'user_id' in session:
        # 获取客户端真实IP地址
        client_ip = get_client_ip()
        return render_template('chat.html', client_ip=client_ip, username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('register.html')
        
        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            db.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名已存在', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """注销登录"""
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('connect')
def handle_connect():
    """处理新用户连接"""
    global online_users
    online_users += 1
    
    if 'user_id' in session:
        user_id = session['user_id']
        username = session['username']
        online_users_list[request.sid] = {
            'user_id': user_id,
            'username': username,
            'ip': get_client_ip()
        }
    
    # 更新所有客户端的在线用户数
    emit('user_count', {'count': online_users}, broadcast=True)
    
    # 发送历史消息给新连接的用户
    with lock:
        for msg in chat_history:
            emit('new_message', msg)

@socketio.on('disconnect')
def handle_disconnect():
    """处理用户断开连接"""
    global online_users
    online_users -= 1
    
    if request.sid in online_users_list:
        del online_users_list[request.sid]
    
    # 更新所有客户端的在线用户数
    emit('user_count', {'count': online_users}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    """处理新消息"""
    if 'user_id' not in session:
        return
    
    message = data.get('message', '')
    display_name = data.get('display_name', '')
    
    if not message:
        return
    
    # 获取用户信息
    user_id = session['user_id']
    username = session['username']
    
    # 创建带时间戳的消息（使用月-日 时:分格式）
    timestamp = datetime.now().strftime("%m-%d %H:%M")
    new_message = {
        'user_id': user_id,
        'username': username,
        'display_name': display_name if display_name else username,
        'message': message,
        'timestamp': timestamp
    }
    
    # 保存消息
    with lock:
        chat_history.append(new_message)
    
    # 广播新消息给所有客户端
    emit('new_message', new_message, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)