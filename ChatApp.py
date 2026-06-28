import os
import urllib.parse
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
#import psycopg2
import psycopg as psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meet_backchat_secret_key')

# 共通パスワードの設定
CHAT_PASSWORD = os.environ.get('CHAT_PASSWORD', 'gdg2026')

# SocketIOの設定
socketio = SocketIO(app, cors_allowed_origins="*")

# Supabaseの接続情報（環境変数から取得、なければデフォルト値）
# ⚠️ テスト時はここに直接手順1-7のURLを書いても動きます
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'ここに手順1-7でコピーしたURIを貼り付ける')
MAX_HISTORY = 100

def get_db_connection():
    """Supabase(PostgreSQL)への接続を確立する関数"""
    return psycopg2.connect(SUPABASE_URL)

def init_db():
    """テーブルの初期化を行う関数"""
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
    """メッセージをSupabaseに保存し、100件を超えた古いログを自動削除する"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # メッセージの挿入
            cursor.execute(
                'INSERT INTO chat_messages (username, msg, time_str, sender_id) VALUES (%s, %s, %s, %s)',
                (user, msg, time, sender_id)
            )
            
            # 最新の100件以外（古いレコード）を自動的に削除
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
    """Supabaseから最新の100件を古い順に取得する"""
    conn = get_db_connection()
    history = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('SELECT username, msg, time_str, sender_id FROM chat_messages ORDER BY id DESC LIMIT %s', (MAX_HISTORY,))
            rows = cursor.fetchall()
            
            # 降順で取得されるため、チャット表示用に反転（昇順）させる
            for row in reversed(rows):
                history.append({
                    'user': row['username'],
                    'msg': row['msg'],
                    'time': row['time_str'],
                    'sender_id': row['sender_id']
                })
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
    return history

# 起動時にデータベース構造を確認・作成
init_db()

# -------------------------------------------------------------------------
# Completely English & Accessibility-friendly HTML Template
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
        body { font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 0 10px; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        #chat-log { border: 2px solid #ccc; height: 400px; overflow-y: scroll; padding: 15px; margin-bottom: 15px; background: #f9f9f9; }
        .message { margin-bottom: 10px; padding: 8px; border-bottom: 1px solid #eee; }
        .timestamp { color: #666; font-size: 0.9em; margin-left: 5px; margin-right: 5px; }
        .input-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        #auth-area { background: #f0f0f0; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #ddd; }
        #chat-area { display: none; }
    </style>
</head>
<body>

    <header>
        <h1>Global Discussion Group ChatRoom</h1>
        <p>Welcome to the real-time chatroom for all GDG members.</p>
    </header>

    <main>
        <section id="auth-area" aria-labelledby="auth-heading">
            <h2 id="auth-heading">Authentication Required</h2>
            <div class="input-group">
                <label for="room-password">Enter Room Password</label>
                <input id="room-password" type="password" placeholder="Password" onkeypress="handleAuthKeyPress(event)">
            </div>
            <button onclick="authenticate()">Enter Room</button>
            <p id="auth-error" style="color: red; margin-top: 10px; display: none;"></p>
        </section>

        <section id="chat-area">
            <section aria-labelledby="log-heading">
                <h2 id="log-heading" class="sr-only">Chat History</h2>
                <div id="chat-log" role="log" aria-live="polite" aria-relevant="additions">
                    <div class="message" id="system-msg"><em>System: Connected to the chatroom. Loading history...</em></div>
                </div>
            </section>

            <section aria-labelledby="form-heading">
                <h2 id="form-heading" class="sr-only">Send a Message</h2>
                
                <div class="input-group">
                    <label for="username">Your Name</label>
                    <input id="username" type="text" placeholder="e.g., John" autocomplete="name">
                </div>

                <div class="input-group">
                    <label for="myMessage">Message</label>
                    <textarea id="myMessage" rows="2" placeholder="Type your message here and press Enter" onkeypress="handleKeyPress(event)" style="width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; resize: none; overflow-y: auto; font-family: sans-serif;"></textarea>
                </div>

                <button onclick="sendMessage()">Send</button>
            </section>
        </section>
    </main>

    <script>
        var socket = io({ autoConnect: false }); 
        var myClientId = null;
        var enteredPassword = "";

        window.addEventListener('DOMContentLoaded', (event) => {
            var savedUser = localStorage.getItem('chat_username');
            if (savedUser) {
                document.getElementById('username').value = savedUser;
            }
            
            // パスワード自動復元
            var savedPassword = localStorage.getItem('chat_password');
            if (savedPassword) {
                document.getElementById('room-password').value = savedPassword;
                enteredPassword = savedPassword;
                executeConnect(savedPassword);
            } else {
                document.getElementById('room-password').focus();
            }
        });

        function authenticate() {
            var pwdField = document.getElementById('room-password');
            enteredPassword = pwdField.value.trim();
            
            if (!enteredPassword) {
                showAuthError("Password cannot be empty.");
                return;
            }
            executeConnect(enteredPassword);
        }

        function executeConnect(pwd) {
            socket.auth = { password: pwd };
            socket.connect();
        }

        function showAuthError(msg) {
            var errEl = document.getElementById('auth-error');
            errEl.textContent = msg;
            errEl.style.display = "block";
            localStorage.removeItem('chat_password');
        }

        function handleAuthKeyPress(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                authenticate();
            }
        }

        function playNotificationSound() {
            try {
                var AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                var context = new AudioContext();
                
                var osc1 = context.createOscillator();
                var gain1 = context.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(600, context.currentTime); 
                gain1.gain.setValueAtTime(0.05, context.currentTime);
                gain1.gain.exponentialRampToValueAtTime(0.00001, context.currentTime + 0.08);
                osc1.connect(gain1);
                gain1.connect(context.destination);
                osc1.start();
                osc1.stop(context.currentTime + 0.08);

                setTimeout(function() {
                    var osc2 = context.createOscillator();
                    var gain2 = context.createGain();
                    osc2.type = 'sine';
                    osc2.frequency.setValueAtTime(800, context.currentTime);
                    gain2.gain.setValueAtTime(0.05, context.currentTime);
                    gain2.gain.exponentialRampToValueAtTime(0.00001, context.currentTime + 0.1);
                    osc2.connect(gain2);
                    gain2.connect(context.destination);
                    osc2.start();
                    osc2.stop(context.currentTime + 0.1);
                }, 80);
            } catch (e) {
                console.log("Audio play blocked or not supported:", e);
            }
        }

        socket.on('connect', function() {
            myClientId = socket.id;
            document.getElementById('auth-area').style.display = 'none';
            document.getElementById('chat-area').style.display = 'block';
            
            // ログイン成功したパスワードをブラウザに記憶
            localStorage.setItem('chat_password', enteredPassword);
            
            var sysMsg = document.getElementById('system-msg');
            if (sysMsg) sysMsg.innerHTML = '<em>System: Connected to the chatroom.</em>';
        });

        socket.on('connect_error', function(err) {
            showAuthError(err.message || "Authentication failed. Please check your password.");
        });

        socket.on('chat_history', function(historyData) {
            var log = document.getElementById('chat-log');
            log.innerHTML = '<div class="message"><em>System: History loaded.</em></div>';
            
            historyData.forEach(function(data) {
                appendMessage(data);
            });
            log.scrollTop = log.scrollHeight;
        });

        socket.on('message', function(data) {
            appendMessage(data);
            if (data.sender_id !== myClientId) {
                playNotificationSound();
            }
            var log = document.getElementById('chat-log');
            log.scrollTop = log.scrollHeight;
        });

        function appendMessage(data) {
            var log = document.getElementById('chat-log');
            var div = document.createElement('div');
            div.className = 'message';
            div.innerHTML = '<strong>' + data.user + '</strong>' + 
                            '<span class="timestamp">(' + data.time + '):</span> ' + 
                            data.msg;
            log.appendChild(div);
        }

        function sendMessage() {
            var userField = document.getElementById('username');
            var msgField = document.getElementById('myMessage');
            
            var user = userField.value.trim() || 'Anonymous';
            var msg = msgField.value.trim();
            
            if(msg) {
                if(userField.value.trim()) {
                    localStorage.setItem('chat_username', userField.value.trim());
                } else {
                    localStorage.removeItem('chat_username');
                }

                var now = new Date();
                var year = now.getFullYear();
                var month = String(now.getMonth() + 1).padStart(2, '0');
                var date = String(now.getDate()).padStart(2, '0');
                var hours = String(now.getHours()).padStart(2, '0');
                var minutes = String(now.getMinutes()).padStart(2, '0');
                
                var tz = '';
                try {
                    var options = { timeZoneName: 'short' };
                    var formatter = new Intl.DateTimeFormat('en-US', options);
                    var parts = formatter.formatToParts(now);
                    var tzPart = parts.find(p => p.type === 'timeZoneName');
                    tz = tzPart ? ' ' + tzPart.value : '';
                } catch(e) {
                    tz = '';
                }

                var timestamp = year + '/' + month + '/' + date + '/' + hours + '/' + minutes + tz;

                socket.emit('message', {user: user, msg: msg, time: timestamp, sender_id: myClientId, password: enteredPassword});
                msgField.value = '';
                msgField.focus();
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault(); 
                sendMessage();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect(auth):
    if not auth or auth.get('password') != CHAT_PASSWORD:
        return False
    emit('chat_history', get_history())

@socketio.on('message')
def handle_message(data):
    if data.get('password') != CHAT_PASSWORD:
        return
        
    broadcast_data = {
        'user': data.get('user'),
        'msg': data.get('msg'),
        'time': data.get('time'),
        'sender_id': data.get('sender_id')
    }
    
    save_message(
        broadcast_data['user'],
        broadcast_data['msg'],
        broadcast_data['time'],
        broadcast_data['sender_id']
    )
    
    emit('message', broadcast_data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)