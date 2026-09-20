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
            # メッセージの挿入
            cursor.execute(
                'INSERT INTO chat_messages (username, msg, time_str, sender_id) VALUES (%s, %s, %s, %s)',
                (user, msg, time, sender_id)
            )
            # 【修正】PostgreSQLで正しく動くようにサブクエリを二重にして古いものを削除
            cursor.execute('''
                DELETE FROM chat_messages 
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM chat_messages ORDER BY id DESC LIMIT %s
                    ) AS temp_table
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

                    'name': row['username'],   

                    'msg': row['msg'],
                    'timestamp': row['time_str'], 
                    'sender_id': row['sender_id']
                })
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
    return history

# データベースの初期化
init_db()

# Completely English & Accessibility-friendly HTML Template (V6)

# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global Discussion Group ChatRoom v2</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 0 10px; position: relative; box-sizing: border-box; }
        *, *:before, *:after { box-sizing: inherit; }
        
        h1 { font-size: 1.5em; margin-bottom: 15px; }
        
        #chat-area { display: block; }
        #chat-log { border: 2px solid #ccc; height: 400px; overflow-y: scroll; padding: 15px; margin-bottom: 15px; background: #f9f9f9; border-radius: 4px; }
        
        .message { margin-bottom: 10px; padding: 8px; border-bottom: 1px solid #eee; display: flex; flex-direction: column; outline: none; }
        .message:focus { border: 2px solid #007bff; background: #eef7ff; border-radius: 4px; }
        
        .msg-meta { font-size: 0.85em; color: #0056b3; margin-bottom: 4px; display: flex; gap: 8px; }
        .msg-user { font-weight: bold; color: #0056b3; }
        .timestamp { font-weight: normal; color: #0056b3; }
        
        .input-group { margin-bottom: 15px; }
        .checkbox-group { margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
        .checkbox-group label { margin-bottom: 0; font-weight: bold; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        
        textarea { width: 100%; height: 80px; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; font-family: sans-serif; resize: vertical; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; }
        
        .welcome-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; gap: 10px; }
        .welcome-text { font-size: 1em; font-weight: bold; margin: 0; flex-grow: 1; }
        
        .settings-btn { 
            background: none; 
            border: none; 
            padding: 4px; 
            cursor: pointer; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            transition: transform 0.2s; 
            flex-shrink: 0;
            width: 36px; 
            height: 36px; 
            border-radius: 50%;
        }
        .settings-btn:hover { background: #eee; transform: rotate(45deg); }
        .settings-btn svg { width: 22px; height: 22px; fill: #333; display: block; }
        
        #history-status { color: #666; font-style: italic; margin: 5px 0 15px 0; font-size: 0.9em; }

        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: #fefefe; margin: 15% auto; padding: 20px; border: 1px solid #888; width: 90%; max-width: 400px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .modal-header h2 { margin: 0; font-size: 1.3em; }
        .close-btn { font-size: 28px; font-weight: bold; cursor: pointer; background: none; border: none; color: #aaa; padding: 0; line-height: 1; }
        .close-btn:hover { color: #000; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
        .modal-actions button { padding: 8px 16px; font-size: 15px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        .modal-actions button:hover { background: #0056b3; }
        
        .msg-text a { color: #007bff; text-decoration: underline; }
        .msg-text a:hover { color: #0056b3; }
        .note-hint { font-size: 0.85em; color: #666; margin-bottom: 5px; }
    </style>
</head>
<body>
    <header>
        <h1>Global Discussion Group ChatRoom v2</h1>
    </header>

    <main>
        <div class="welcome-container">
            <p class="welcome-text">Welcome to the real-time chatroom for all GDG members.</p>
            <button id="settings-icon" class="settings-btn" title="Settings" aria-label="Open Settings">
                <svg viewBox="0 0 24 24">
                    <path d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69-.98l.38-2.65c.03-.24.24-.42.49-.42h4c.25 0 .46.18.49.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"/>
                </svg>
            </button>
        </div>

        <p id="history-status">System: History being loaded from server...</p>

        <div id="chat-area">
            <div id="chat-log" role="log" aria-label="Chat Log History"></div>
            <div class="input-group">
                <label for="message-input">Message</label>
                <div class="note-hint">※送信: Enterキー / 改行: Shift + Enterキー (URLは自動リンク)</div>
                <textarea id="message-input" placeholder="Type a message..."></textarea>
            </div>
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

        // Web Audio API による通知音
        function playDingDong() {
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                const ctx = new AudioContext();
                
                const osc1 = ctx.createOscillator();
                const gain1 = ctx.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(587.33, ctx.currentTime);
                gain1.gain.setValueAtTime(0.1, ctx.currentTime);
                gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.start(ctx.currentTime);
                osc1.stop(ctx.currentTime + 0.4);

                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.setValueAtTime(440.00, ctx.currentTime + 0.15);
                gain2.gain.setValueAtTime(0.1, ctx.currentTime + 0.15);
                gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start(ctx.currentTime + 0.15);
                osc2.stop(ctx.currentTime + 0.6);
            } catch (e) {
                console.log("Audio playback failed:", e);
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            const savedPassword = localStorage.getItem('chat_password') || '';
            const savedName = localStorage.getItem('chat_name') || '';
            const savedTimestamp = localStorage.getItem('chat_timestamp') === 'true';

            document.getElementById('settings-password').value = savedPassword;
            document.getElementById('settings-name').value = savedName;
            document.getElementById('settings-timestamp').checked = savedTimestamp;

            // ローカルストレージに履歴があれば初期表示しておく（真っ白になるのを防ぐ）
            const cachedHistory = JSON.parse(localStorage.getItem('chat_history_data'));
            if (cachedHistory && Array.isArray(cachedHistory) && cachedHistory.length > 0) {
                renderHistoryList(cachedHistory);
            }
        });

        // メッセージ送信処理
        function sendMessage() {
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
        }

        // キーボード操作（Enter送信、Shift+Enter改行、Shift+Tabフォーカス移動）
        document.getElementById('message-input').addEventListener('keydown', function(event) {
            if (event.isComposing || event.keyCode === 229) return;

            if (event.key === 'Tab' && event.shiftKey) {
                const messages = document.querySelectorAll('#chat-log .message');
                if (messages.length > 0) {
                    event.preventDefault();
                    messages[messages.length - 1].focus();
                }
                return;
            }

            if (event.key === 'Enter') {
                if (event.shiftKey) {
                    return; // 改行
                } else {
                    event.preventDefault();
                    sendMessage();
                }
            }
        });

        socket.on('load_history', function(history) {
            const statusMessage = document.getElementById('history-status');
            if (statusMessage) statusMessage.remove();
            
            if (Array.isArray(history)) {
                const standardHistory = history.slice(-MAX_HISTORY).map(item => ({
                    name: item.name || item.user || item.username || 'Anonymous',
                    msg: item.msg || item.message || '',
                    timestamp: item.timestamp || item.time || new Date().toISOString()
                }));
                localStorage.setItem('chat_history_data', JSON.stringify(standardHistory));
                renderHistoryList(standardHistory);
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

        function escapeHtml(str) {
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function formatMessageText(text) {
            const safeText = escapeHtml(text);
            const urlRegex = /(https?:\/\/[^\s]+)/g;
            const linkedText = safeText.replace(urlRegex, function(url) {
                return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>';
            });
            return linkedText.replace(/\\n/g, '<br>').replace(/\\r\\n/g, '<br>').replace(/\\r/g, '<br>');
        }

        function createMessageElement(data) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message');
            messageElement.setAttribute('tabindex', '0');
            
            const name = data.name || 'Anonymous';
            const showTimestamp = localStorage.getItem('chat_timestamp') === 'true';
            const timeFormatted = showTimestamp ? formatTimestamp(data.timestamp) : '';
            
            const ariaText = `${name} says: ${data.msg}. ${showTimestamp ? 'Sent at ' + timeFormatted : ''}`;
            messageElement.setAttribute('aria-label', ariaText);

            const metaElement = document.createElement('div');
            metaElement.classList.add('msg-meta');
            metaElement.setAttribute('aria-hidden', 'true');
            
            const nameSpan = document.createElement('span');
            nameSpan.classList.add('msg-user');
            nameSpan.textContent = name;
            metaElement.appendChild(nameSpan);

            if (showTimestamp) {
                const timeSpan = document.createElement('span');
                timeSpan.classList.add('timestamp');
                timeSpan.textContent = timeFormatted;
                metaElement.appendChild(timeSpan);
            }
            
            messageElement.appendChild(metaElement);

            const textElement = document.createElement('div');
            textElement.classList.add('msg-text');
            textElement.style.color = '#333';
            textElement.style.wordBreak = 'break-all';
            textElement.innerHTML = formatMessageText(data.msg);

            messageElement.appendChild(textElement);
            return messageElement;
        }

        function renderHistoryList(historyLog) {
            const chatLog = document.getElementById('chat-log');
            chatLog.innerHTML = '';
            
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

            playDingDong();

            let historyLog = JSON.parse(localStorage.getItem('chat_history_data')) || [];
            historyLog.push(messageData);
            
            if (historyLog.length > MAX_HISTORY) {
                historyLog = historyLog.slice(-MAX_HISTORY);
            }
            localStorage.setItem('chat_history_data', JSON.stringify(historyLog));
        });

        // モーダル設定の開閉ロジック
        const modal = document.getElementById('settings-modal');
        const settingsIcon = document.getElementById('settings-icon');
        const closeModalBtn = document.getElementById('close-modal-btn');

        settingsIcon.addEventListener('click', function() {
            modal.style.display = 'block';
            modal.setAttribute('aria-hidden', 'false');
        });

        function closeModal() {
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        }

        closeModalBtn.addEventListener('click', closeModal);
        window.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeModal();
            }
        });

        document.getElementById('save-settings-btn').addEventListener('click', function() {
            const pwd = document.getElementById('settings-password').value;
            const name = document.getElementById('settings-name').value;
            const timestampChecked = document.getElementById('settings-timestamp').checked;

            localStorage.setItem('chat_password', pwd);
            localStorage.setItem('chat_name', name);
            localStorage.setItem('chat_timestamp', timestampChecked);

            const currentHistory = JSON.parse(localStorage.getItem('chat_history_data')) || [];
            renderHistoryList(currentHistory);
            
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
# Socket.IO イベントハンドラ定義
# -------------------------------------------------------------------------
@socketio.on('connect')
def handle_connect():
    """ユーザー接続時に、Supabaseから最新100件の履歴を取得して一斉送信する"""
    history = get_history()
    emit('load_history', history)

@socketio.on('send_message')
def handle_send_message(data):


    """メッセージを受信し、DBへの保存と全クライアントへのリアルタイムブロードキャストを行う"""

    msg_content = data.get('msg') or data.get('message', '')
    user_name = data.get('name') or data.get('user') or data.get('username', 'Anonymous')
    
    current_time = datetime.utcnow().isoformat() + 'Z'
    sender_id = data.get('password', '') 
    
    save_message(user_name, msg_content, current_time, sender_id)
    
    emit('receive_message', {
        'name': user_name,
        'msg': msg_content,
        'timestamp': current_time,
        'sender_id': sender_id
    }, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)