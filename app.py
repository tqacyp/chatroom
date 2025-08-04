import os
import uuid
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# 确保data文件夹存在
if not os.path.exists('data'):
    os.makedirs('data')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['USER_DATABASE'] = 'data/chat_users.db'
app.config['MESSAGE_DATABASE'] = 'data/chat_messages.db'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# 初始化数据库
def get_user_db():
    db = sqlite3.connect(app.config['USER_DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def get_message_db():
    db = sqlite3.connect(app.config['MESSAGE_DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def create_tables():
    # 创建用户表
    user_db = get_user_db()
    user_db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    user_db.commit()
    user_db.close()

    # 创建消息表
    msg_db = get_message_db()
    msg_db.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            display_name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ip TEXT NOT NULL,
            is_guest BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    msg_db.commit()
    msg_db.close()

# 在应用启动时创建数据库表
create_tables()

# 存储聊天记录
chat_history = []
# 记录最后保存的消息索引
last_saved_index = 0
# 线程锁确保线程安全
lock = threading.Lock()
# 在线用户计数
online_users = 0
# 在线用户列表
online_users_list = {}

# 象棋部分
chess_games = {}

def init_board():
    """初始化棋盘状态 (FEN格式)"""
    return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

def parse_fen(fen):
    """解析FEN字符串为二维数组"""
    board = [['' for _ in range(8)] for _ in range(8)]
    rows = fen.split('/')
    
    for row_idx, row in enumerate(rows):
        col_idx = 0
        for char in row:
            if char.isdigit():
                # 空位置
                col_idx += int(char)
            else:
                board[row_idx][col_idx] = char
                col_idx += 1
    return board

def fen_from_board(board):
    """从棋盘数组生成FEN字符串"""
    fen_rows = []
    for row in board:
        fen_row = ''
        empty_count = 0
        
        for cell in row:
            if cell == '':
                empty_count += 1
            else:
                if empty_count > 0:
                    fen_row += str(empty_count)
                    empty_count = 0
                fen_row += cell
        
        if empty_count > 0:
            fen_row += str(empty_count)
        
        fen_rows.append(fen_row)
    
    return '/'.join(fen_rows)

# 国际象棋API路由
@app.route('/chess/new_game', methods=['POST'])
def new_chess_game():
    """创建新棋局"""
    game_id = str(uuid.uuid4())[:8]
    chess_games[game_id] = {
        'state': init_board(),
        'history': [],
        'players': {}
    }
    return jsonify({'game_id': game_id})

@app.route('/chess/<game_id>/state', methods=['GET'])
def get_chess_state(game_id):
    """获取当前棋局状态"""
    if game_id not in chess_games:
        return jsonify({'error': 'Game not found'}), 404
    
    # 将FEN转换为前端需要的格式
    fen = chess_games[game_id]['state']
    board = parse_fen(fen)
    
    # 转换为二维数组表示
    return jsonify({
        'board': board,
        'current_player': 'white' if len(chess_games[game_id]['history']) % 2 == 0 else 'black',
        'history': chess_games[game_id]['history']
    })
    
@app.route('/chess/<game_id>/move', methods=['POST'])
def make_move(game_id):
    """执行移动操作"""
    if game_id not in chess_games:
        return jsonify({'error': 'Game not found'}), 404
    
    data = request.get_json()
    from_pos = data.get('from')
    to_pos = data.get('to')
    
    if not from_pos or not to_pos:
        return jsonify({'error': 'Missing from or to position'}), 400
    
    try:
        # 解析位置 (例如: "e2" -> [6, 4])
        file_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5, 'g': 6, 'h': 7}
        from_row = 8 - int(from_pos[1])
        from_col = file_map[from_pos[0]]
        to_row = 8 - int(to_pos[1])
        to_col = file_map[to_pos[0]]
        
        game = chess_games[game_id]
        board = parse_fen(game['state'])
        
        # 简单验证：起始位置必须有棋子
        if not board[from_row][from_col]:
            return jsonify({'error': 'No piece at starting position'}), 400
        
        # 执行移动
        piece = board[from_row][from_col]
        board[from_row][from_col] = ''
        board[to_row][to_col] = piece
        
        # 更新游戏状态
        game['state'] = fen_from_board(board)
        game['history'].append({
            'from': from_pos,
            'to': to_pos,
            'piece': piece,
            'player': game['current_player']
        })
        
        # 切换玩家
        game['current_player'] = 'black' if game['current_player'] == 'white' else 'white'
        
        return jsonify({
            'success': True,
            'message': f'Moved {piece} from {from_pos} to {to_pos}',
            'new_state': game['state']
        })
        
    except Exception as e:
        return jsonify({'error': f'Invalid move: {str(e)}'}), 400
    
# 聊天室部分

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

def save_message_to_db(message):
    """将消息保存到数据库"""
    try:
        db = get_message_db()
        db.execute('''
            INSERT INTO messages 
            (user_id, username, display_name, message, timestamp, ip, is_guest)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            message['user_id'],
            message['username'],
            message['display_name'],
            message['message'],
            message['timestamp'],
            message['ip'],
            message['is_guest']
        ))
        db.commit()
        return True
    except Exception as e:
        print(f"保存消息到数据库失败: {str(e)}")
        return False

def load_chat_history():
    """从数据库加载聊天记录"""
    global chat_history
    try:
        db = get_message_db()
        messages = db.execute('''
            SELECT * FROM messages 
            ORDER BY created_at ASC
            LIMIT 1000
        ''').fetchall()
        
        chat_history = []
        for msg in messages:
            chat_history.append({
                'user_id': msg['user_id'],
                'username': msg['username'],
                'display_name': msg['display_name'],
                'message': msg['message'],
                'timestamp': msg['timestamp'],
                'ip': msg['ip'],
                'is_guest': bool(msg['is_guest'])
            })
        
        print(f"已从数据库加载 {len(chat_history)} 条历史消息")
    except Exception as e:
        print(f"加载聊天记录失败: {str(e)}")

# 启动时加载历史记录
load_chat_history()

@app.route('/')
def index():
    """首页，根据登录状态重定向"""
    client_ip = get_client_ip()
    
    # 游客模式处理
    if 'user_id' not in session:
        session['is_guest'] = True
        session['guest_ip'] = client_ip
        session['username'] = f"游客-{client_ip[:]}"
        return render_template('chat.html', client_ip=client_ip, username=session['username'], is_guest=True)
    
    # 登录用户处理
    return render_template('chat.html', client_ip=client_ip, username=session['username'], is_guest=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_user_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.pop('is_guest', None)
            session.pop('guest_ip', None)
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
        
        db = get_user_db()
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
    session.pop('is_guest', None)
    session.pop('guest_ip', None)
    return redirect(url_for('index'))

@socketio.on('connect')
def handle_connect():
    """处理新用户连接"""
    global online_users
    online_users += 1
    
    client_ip = get_client_ip()
    
    # 游客模式处理
    if session.get('is_guest'):
        user_id = f"guest-{client_ip}"
        username = session.get('username', f"游客-{client_ip[:]}")
        online_users_list[request.sid] = {
            'user_id': user_id,
            'username': username,
            'ip': client_ip,
            'is_guest': True
        }
    # 登录用户处理
    elif 'user_id' in session:
        user_id = session['user_id']
        username = session['username']
        online_users_list[request.sid] = {
            'user_id': user_id,
            'username': username,
            'ip': client_ip,
            'is_guest': False
        }
    
    # 更新所有客户端的在线用户数
    emit('user_count', {'count': online_users}, broadcast=True)

@socketio.on('request_history')
def handle_history_request():
    """处理历史记录请求"""
    with lock:
        emit('chat_history', chat_history)

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
    client_ip = get_client_ip()
    display_name = data.get('display_name', '')
    message = data.get('message', '')
    
    if not message:
        return
    
    # 获取用户信息
    if session.get('is_guest'):
        user_id = f"guest-{client_ip}"
        username = session.get('username', f"游客-{client_ip[:]}")
    elif 'user_id' in session:
        user_id = session['user_id']
        username = session['username']
    else:
        # 未登录且不是游客（理论上不会发生）
        user_id = f"guest-{client_ip}"
        username = f"游客-{client_ip[:]}"
    
    # 使用显示名称或用户名
    final_display_name = display_name if display_name else username
    
    # 创建带时间戳的消息（使用月-日 时:分格式）
    timestamp = datetime.now().strftime("%m-%d %H:%M")
    new_message = {
        'user_id': user_id,
        'username': username,
        'display_name': final_display_name,
        'message': message,
        'timestamp': timestamp,
        'ip': client_ip,
        'is_guest': session.get('is_guest', True)
    }
    
    # 保存消息到数据库
    if save_message_to_db(new_message):
        with lock:
            chat_history.append(new_message)
        
        # 广播新消息给所有客户端
        emit('new_message', new_message, broadcast=True)
        # 广播保存成功通知
        # emit('save_notification', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='192.168.31.10', port=88, debug=False)