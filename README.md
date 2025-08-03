## 实时聊天室项目

### 项目简介
本项目是一个基于 Flask 和 Flask-SocketIO 实现的实时聊天室应用，支持用户注册、登录、消息实时收发、在线人数统计等功能。前端页面美观，支持移动端和桌面端自适应。

---

### 主要功能
- 用户注册与登录（密码加密存储）
- 实时消息收发（WebSocket）
- 在线用户统计与显示
- 聊天历史消息回显
- 用户显示名称自定义
- 美观的响应式前端界面

---

### 技术栈
- Python 3
- Flask
- Flask-SocketIO
- SQLite3
- HTML/CSS/JavaScript

---

### 安装与运行
1. **克隆项目**
   ```bash
   git clone <本项目地址>
   cd chatroom
   ```
2. **安装依赖**
   ```bash
   pip install flask flask-socketio werkzeug
   ```
3. **运行项目**
   ```bash
   python app.py
   ```
   默认监听 5000 端口，可通过浏览器访问 `http://localhost:5000`

---

### 目录结构
```
chatroom/
├── app.py                # 主程序入口
├── schema.sql            # 数据库表结构
├── data/
│   └── chat_users.db     # SQLite数据库文件
├── templates/
│   ├── chat.html         # 聊天室页面
│   ├── login.html        # 登录页面
│   └── register.html     # 注册页面
└── README.md             # 项目说明文档
```

---

### 数据库初始化
- 首次运行会自动创建 `data/chat_users.db` 数据库和 `users` 表。
- 如需手动初始化，可执行 `schema.sql` 脚本。

---

### 注意事项
- 请勿将 `SECRET_KEY` 设置为默认值，生产环境请更换为强随机密钥。
- 聊天历史为内存存储，重启服务会丢失。
- 仅供学习交流使用，未做大规模并发和安全加固。

---

### 交流与反馈
如有建议或问题，欢迎 issue 或 PR。
