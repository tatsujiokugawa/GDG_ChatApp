import os
import sys
from datetime import datetime
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# -------------------------------------------------------------------------
# 環境変数・初期設定
# -------------------------------------------------------------------------
os.environ["PSYCOPG_IMPL"] = "python"

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meet_backchat_secret_key')

# Render環境やローカルスレッド環境で安定して動作するよう threading を指定
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode="threading"
)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
MAX_HISTORY = 100

# -------------------------------------------------------------------------
# 【本番・Render環境最適化】 psycopg v3 互換レイヤー
# -------------------------------------------------------------------------
import psycopg

class DictCursorAdapter:
    """psycopg2 の DictCursor の挙動を psycopg v3 で再現するアダプター"""
    def __init__(self, cursor):
        self.cursor = cursor
    def execute(self, query, params=None):
        self.cursor.execute(query, params)
    def fetchall(self):
        keys = [desc[0] for desc in self.cursor.description]
        return [dict(zip(keys, row)) for row in self.cursor.fetchall()]
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()

class PostgresConnectionAdapter:
    """psycopg2 の connection の挙動を再現するアダプター"""
    def __init__(self, conn):
        self.conn = conn
    def cursor(self, cursor_factory=None):
        cur = self.conn.cursor()
        if cursor_factory is not None:
            return DictCursorAdapter(cur)
        return cur
    def commit(self):
        self.conn.conn.commit() if hasattr(self.conn, 'conn') else self.conn.commit()
    def close(self):
        self.conn.close()

class psycopg2_mock:
    """psycopg2 モジュールのダミーオブジェクト"""
    @staticmethod
    def connect(url):
        if "?" in url:
            url = url.split("?")[0]
        conn = psycopg.connect(url)
        return PostgresConnectionAdapter(conn)

psycopg2 = psycopg2_mock
DictCursor = "DictCursor"

# -------------------------------------------------------------------------
# データベース操作関数
# -------------------------------------------------------------------------
def get_db_connection():
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    if not SUPABASE_URL:
        print("Warning: SUPABASE_URL is not set. Skipping database initialization.")
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    msg TEXT,
                    time_str TEXT,
                    sender_id TEXT
                )
            ''')
            conn.commit()
    finally:
        conn.close()

def save_message(user, msg, time, sender_id):
    if not SUPABASE_URL:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO chat_messages (username, msg, time_str, sender_id) VALUES (%s, %s, %s, %s)',
                (user, msg, time, sender_id)
            )
            cursor.execute('''
                DELETE FROM chat_messages 
                WHERE id NOT IN (
                    SELECT id FROM chat_messages ORDER BY id DESC LIMIT %s
                )
            ''', (MAX_HISTORY,))
            conn.commit()
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def get_history():
    if not SUPABASE_URL:
        return []
    conn = get_db_connection()
    history = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('SELECT username, msg, time_str, sender_id FROM chat_messages ORDER BY id DESC LIMIT %s', (MAX_HISTORY,))
            rows = cursor.fetchall()
            for row in reversed(rows):
                history.append({
                    'name': row['username'],   # クライアント側の期待するキー 'name' に統一
                    'msg': row['msg'],
                    'timestamp': row['time_str'], # クライアント側の期待するキー 'timestamp' に統一
                    'sender_id': row['sender_id']
                })
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
    return history

# データベースの初期化
init_db()

# -------------------------------------------------------------------------
# Completely English & Accessibility-friendly HTML Template (V4)
# - 名前・タイムスタンプを青色にスタイル適用
# - 送信された名前(Name)がAnonymousにならず適切に表示されるロジック
# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global Discussion Group ChatRoom</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 0 10px; position: relative; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        
        #chat-area { display: block; }
        #chat-log { border: 2px solid #ccc; height: 400px; overflow-y: scroll; padding: 15px; margin-bottom: 15px; background: #f9f9f9; border-radius: 4px; }
        
        .message { margin-bottom: 10px; padding: 8px; border-bottom: 1px solid #eee; display: flex; flex-direction: column; }
        
        /* 名前とタイムスタンプのエリアを青色（#0056b3）に指定して本文と区別 */
        .msg-meta { font-size: 0.85em; color: #0056b3; margin-bottom: 4px; display: flex; gap: 8px; }
        .msg-user { font-weight: bold; color: #0056b3; }
        .timestamp { font-weight: normal; color: #0056b3; }
        
        .input-group { margin-bottom: 15px; }
        .checkbox-group { margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
        .checkbox-group label { margin-bottom: 0; font-weight: bold; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        button:hover { background: #0056b3; }
        
        .welcome-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
        .welcome-text { font-size: 1.1em; font-weight: bold; margin: 0; }
        
        .settings-btn { background: none; border: none; padding: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: transform 0.2s; }
        .settings-btn:hover { transform: rotate(45deg); }
        .settings-btn svg { width: 28px; height: 28px; fill: #333; }
        
        #history-status { color: #888; font-style: italic; margin: 5px 0 15px 0; }

        /* 設定モーダル */
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px; border: 1px solid #888; width: 85%; max-width: 400px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .modal-header h2 { margin: 0; font-size: 1.3em; }
        .close-btn { font-size: 28px; font-weight: bold; cursor: pointer; background: none; border: none; color: #aaa; padding: 0; line-height: 1; }
        .close-btn:hover { color: #000; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    </style>
</head>
<body>
    <header>
        <h1>Global Discussion Group ChatRoom</h1>
    </header>

    <main>
        <div class="welcome-container">
            <p class="welcome-text">Welcome to the real-time chatroom for all GDG members..</p>
            <button id="settings-icon" class="settings-btn" title="Settings" aria-label="Open Settings">
                <svg viewBox="0 0 24 24">
                    <path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73(1.69-.98l.38-2.65c.03-.24.24-.42.49-.42h4c.25 0 .46.18.49.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"/>
                </svg>
            </button>
        </div>

        <p id="history-status">System: History being loaded.</p>

        <div id="chat-area">
            <div id="chat-log" role="log" aria-live="polite"></div>
            <div class="input-group">
                <input type="text" id="message-input" placeholder="Type a message...">
            </div>
            <button id="send-btn">Send</button>
        </div>
    </main>

    <div id="settings-modal" class="modal" role="dialog" aria-labelledby="modal-title" aria-hidden="true">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">Settings</h2>
                <button class="close-btn" id="close-modal-btn" aria-label="Close Settings">&times;</button>
            </div>
            <div class="input-group">
                <label for="settings-password">Password</label>
                <input type="password" id="settings-password" placeholder="Room password">
            </div>
            <div class="input-group">
                <label for="settings-name">Name</label>
                <input type="text" id="settings-name" placeholder="Your name">
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="settings-timestamp">
                <label for="settings-timestamp">Timestamp</label>
            </div>
            <div class="modal-actions">
                <button id="save-settings-btn">Save</button>
            </div>
        </div>
    </div>

    <script>
        const MAX_HISTORY = 100;
        const socket = io({ transports: ['polling'] });

        window.addEventListener('DOMContentLoaded', () => {
            const savedPassword = localStorage.getItem('chat_password') || '';
            const savedName = localStorage.getItem('chat_name') || '';
            const savedTimestamp = localStorage.getItem('chat_timestamp') === 'true';

            document.getElementById('settings-password').value = savedPassword;
            document.getElementById('settings-name').value = savedName;
            document.getElementById('settings-timestamp').checked = savedTimestamp;

            renderLocalHistory();

            setTimeout(() => {
                const statusMessage = document.getElementById('history-status');
                if (statusMessage) statusMessage.remove();
            }, 1500);
        });

        document.getElementById('send-btn').addEventListener('click', () => {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            const name = localStorage.getItem('chat_name') || 'Anonymous';
            const password = localStorage.getItem('chat_password') || '';
            
            if (message !== "") {
                socket.emit('send_message', { 
                    msg: message, 
                    name: name,
                    user: name,
                    username: name,
                    password: password 
                });
                input.value = ''; 
            }
        });

        socket.on('load_history', function(history) {
            const statusMessage = document.getElementById('history-status');
            if (statusMessage) statusMessage.remove();
            
            if (Array.isArray(history) && history.length > 0) {
                const standardHistory = history.slice(-MAX_HISTORY).map(item => ({
                    name: item.name || item.user || item.username || 'Anonymous',
                    msg: item.msg || item.message || '',
                    timestamp: item.timestamp || item.time || new Date().toISOString()
                }));
                localStorage.setItem('chat_history_data', JSON.stringify(standardHistory));
                renderLocalHistory();
            }
        });

        function formatTimestamp(dateStr) {
            const date = dateStr ? new Date(dateStr) : new Date();
            if (isNaN(date.getTime())) return dateStr;
            
            const yyyy = date.getFullYear();
            const mm = String(date.getMonth() + 1).padStart(2, '0');
            const dd = String(date.getDate()).padStart(2, '0');
            const hh = String(date.getHours()).padStart(2, '0');
            const min = String(date.getMinutes()).padStart(2, '0');
            
            return `${yyyy}/${mm}/${dd} ${hh}:${min}`;
        }

        function createMessageElement(data) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message');
            
            const metaElement = document.createElement('div');
            metaElement.classList.add('msg-meta');
            
            const nameSpan = document.createElement('span');
            nameSpan.classList.add('msg-user');
            nameSpan.textContent = data.name || 'Anonymous';
            metaElement.appendChild(nameSpan);

            const showTimestamp = localStorage.getItem('chat_timestamp') === 'true';
            if (showTimestamp) {
                const timeSpan = document.createElement('span');
                timeSpan.classList.add('timestamp');
                timeSpan.textContent = formatTimestamp(data.timestamp);
                metaElement.appendChild(timeSpan);
            }
            
            messageElement.appendChild(metaElement);

            const textElement = document.createElement('span');
            textElement.style.color = '#333';
            textElement.textContent = data.msg;
            messageElement.appendChild(textElement);
            
            return messageElement;
        }

        function renderLocalHistory() {
            const chatLog = document.getElementById('chat-log');
            chatLog.innerHTML = '';
            
            const historyLog = JSON.parse(localStorage.getItem('chat_history_data')) || [];
            historyLog.forEach(data => {
                const elem = createMessageElement(data);
                chatLog.appendChild(elem);
            });
            chatLog.scrollTop = chatLog.scrollHeight;
        }

        socket.on('receive_message', function(data) {
            const chatLog = document.getElementById('chat-log');
            const incomingName = data.name || data.user || data.username || 'Anonymous';
            
            const messageData = {
                name: incomingName,
                msg: data.msg || data.message || '',
                timestamp: data.timestamp || data.time || new Date().toISOString()
            };

            const elem = createMessageElement(messageData);
            chatLog.appendChild(elem);
            chatLog.scrollTop = chatLog.scrollHeight;

            let historyLog = JSON.parse(localStorage.getItem('chat_history_data')) || [];
            historyLog.push(messageData);
            
            if (historyLog.length > MAX_HISTORY) {
                historyLog = historyLog.slice(-MAX_HISTORY);
            }
            localStorage.setItem('chat_history_data', JSON.stringify(historyLog));
        });

        const modal = document.getElementById('settings-modal');
        
        document.getElementById('settings-icon').addEventListener('click', function() {
            modal.style.display = 'block';
            modal.setAttribute('aria-hidden', 'false');
        });

        function closeModal() {
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        }

        document.getElementById('close-modal-btn').addEventListener('click', closeModal);
        window.addEventListener('click', function(event) {
            if (event.target === modal) closeModal();
        });

        document.getElementById('save-settings-btn').addEventListener('click', function() {
            const pwd = document.getElementById('settings-password').value;
            const name = document.getElementById('settings-name').value;
            const timestampChecked = document.getElementById('settings-timestamp').checked;

            localStorage.setItem('chat_password', pwd);
            localStorage.setItem('chat_name', name);
            localStorage.setItem('chat_timestamp', timestampChecked);

            renderLocalHistory();
            alert("Settings saved!");
            closeModal();
        });
    </script>
</body>
</html>
"""

# -------------------------------------------------------------------------
# Flask ルーティング定義
# -------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# -------------------------------------------------------------------------
# Socket.IO イベントハンドラ定義（バックエンド処理の実装）
# -------------------------------------------------------------------------
@socketio.on('connect')
def handle_connect():
    """ユーザー接続時に、Supabaseから最新100件の履歴を取得して一斉送信する"""
    history = get_history()
    emit('load_history', history)

@socketio.on('send_message')
def handle_send_message(data):
    """メッセージを受信し、DBへの保存と全クライアントへのリアルタイムブロードキャストを行う"""
    # フロントエンドから送られてくる可能性のある各種キー名を柔軟にフォールバック
    msg_content = data.get('msg') or data.get('message', '')
    user_name = data.get('name') or data.get('user') or data.get('username', 'Anonymous')
    
    # メッセージにサーバー側でのタイムスタンプ（ISOフォーマット）を付与
    current_time = datetime.utcnow().isoformat() + 'Z'
    sender_id = data.get('password', '') # 部屋のパスワードなどを識別子として利用
    
    # データベースへの非同期保存
    save_message(user_name, msg_content, current_time, sender_id)
    
    # 接続中の全員（自分を含む）にメッセージをリレー転送
    emit('receive_message', {
        'name': user_name,
        'msg': msg_content,
        'timestamp': current_time,
        'sender_id': sender_id
    }, broadcast=True)

# アプリケーションの起動（Renderなど外部公開用に0.0.0.0ポートを指定）
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)