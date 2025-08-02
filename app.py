from flask import Flask, request, jsonify, render_template
from datetime import datetime
import threading

app = Flask(__name__)

# 存储聊天记录
chat_history = []
# 线程锁，确保多线程安全
lock = threading.Lock()

@app.route('/')
def index():
    """渲染聊天室主页面"""
    return render_template('chat.html')

@app.route('/send', methods=['POST'])
def send_message():
    """接收并存储新消息"""
    data = request.json
    username = data.get('username', '匿名')
    message = data.get('message', '')
    
    if not message:
        return jsonify({'status': 'error', 'message': '消息不能为空'}), 400
    
    # 创建带时间戳的消息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_message = {
        'username': username,
        'message': message,
        'timestamp': timestamp
    }
    
    # 使用锁确保线程安全
    with lock:
        chat_history.append(new_message)
    
    return jsonify({'status': 'success', 'message': '消息已发送'})

@app.route('/messages')
def get_messages():
    """获取所有聊天记录"""
    # 使用锁确保线程安全
    with lock:
        return jsonify(chat_history)

if __name__ == '__main__':
    app.run(host='192.168.31.10', port=5000, debug=True)