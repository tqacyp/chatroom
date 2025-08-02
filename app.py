# app.py - 服务端代码
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from datetime import datetime
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# 存储聊天记录
chat_history = []
# 线程锁确保线程安全
lock = threading.Lock()
# 在线用户计数
online_users = 0

@app.route('/')
def index():
    """渲染聊天室主页面"""
    return render_template('chat.html')

@socketio.on('connect')
def handle_connect():
    """处理新用户连接"""
    global online_users
    online_users += 1
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
    # 更新所有客户端的在线用户数
    emit('user_count', {'count': online_users}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    """处理新消息"""
    username = data.get('username', '匿名')
    message = data.get('message', '')
    
    if not message:
        return
    
    # 创建带时间戳的消息（使用月-日 时:分格式）
    timestamp = datetime.now().strftime("%m-%d %H:%M")
    new_message = {
        'username': username,
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