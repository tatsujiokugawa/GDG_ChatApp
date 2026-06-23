import os
from collections import deque
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meet_backchat_secret_key')

# 共通パスワードの設定（環境変数から取得、未設定ならデフォルト値）
CHAT_PASSWORD = os.environ.get('CHAT_PASSWORD', 'gdg2026')

# 自動で最適な非同期モードを選択
socketio = SocketIO(app, cors_allowed_origins="*")

# サーバーのメモリ上に過去ログを保存するキュー（最大100件）
MAX_HISTORY = 100
chat_history = deque(maxlen=MAX_HISTORY)

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
        var socket = io({ autoConnect: false }); // 認証後に接続するため最初は自動接続しない
        var myClientId = null;
        var enteredPassword = "";

        // 画面読み込み時に名前の自動復元と、パスワードがあれば自動入力（またはローカルストレージからの復元も可能ですが、今回は安全のため都度入力）
        window.addEventListener('DOMContentLoaded', (event) => {
            var savedUser = localStorage.getItem('chat_username');
            if (savedUser) {
                document.getElementById('username').value = savedUser;
            }
            document.getElementById('room-password').focus();
        });

        // 認証処理
        function authenticate() {
            var pwdField = document.getElementById('room-password');
            enteredPassword = pwdField.value.trim();
            
            if (!enteredPassword) {
                showAuthError("Password cannot be empty.");
                return;
            }

            // WebSocket接続を開始し、認証用パスワードを同封して接続を要求する
            socket.auth = { password: enteredPassword };
            socket.connect();
        }

        function showAuthError(msg) {
            var errEl = document.getElementById('auth-error');
            errEl.textContent = msg;
            errEl.style.display = "block";
        }

        // 認証パスワード入力欄でのEnterキー制御
        function handleAuthKeyPress(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                authenticate();
            }
        }

        // ブラウザの機能で「ピピッ」と通知音を鳴らす関数
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

        // 接続成功（認証成功）時
        socket.on('connect', function() {
            myClientId = socket.id;
            document.getElementById('auth-area').style.display = 'none';
            document.getElementById('chat-area').style.display = 'block';
            
            var sysMsg = document.getElementById('system-msg');
            if (sysMsg) sysMsg.innerHTML = '<em>System: Connected to the chatroom.</em>';
        });

        // 認証失敗時
        socket.on('connect_error', function(err) {
            showAuthError(err.message || "Authentication failed.");
        });

        // 過去のログを一括で受け取る処理
        socket.on('chat_history', function(historyData) {
            var log = document.getElementById('chat-log');
            log.innerHTML = '<div class="message"><em>System: History loaded.</em></div>';
            
            historyData.forEach(function(data) {
                appendMessage(data);
            });
            log.scrollTop = log.scrollHeight;
        });

        // 単発のメッセージ受信処理
        socket.on('message', function(data) {
            appendMessage(data);
            
            if (data.sender_id !== myClientId) {
                playNotificationSound();
            }
            
            var log = document.getElementById('chat-log');
            log.scrollTop = log.scrollHeight;
        });

        // メッセージを画面に追加する共通関数
        function appendMessage(data) {
            var log = document.getElementById('chat-log');
            var div = document.createElement('div');
            div.className = 'message';
            div.innerHTML = '<strong>' + data.user + '</strong>' + 
                            '<span class="timestamp">(' + data.time + '):</span> ' + 
                            data.msg;
            log.appendChild(div);
        }

        // メッセージ送信関数
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

                // タイムスタンプを YYYY/MM/DD/HH/MM 形式で生成
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

                // YYYY/MM/DD/HH/MM の形に組み立て
                var timestamp = year + '/' + month + '/' + date + '/' + hours + '/' + minutes + tz;

                socket.emit('message', {user: user, msg: msg, time: timestamp, sender_id: myClientId, password: enteredPassword});
                msgField.value = '';
                msgField.focus();
            }
        }

        // キーボード入力時の処理
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

# 接続要求があった時の認証チェック
@socketio.on('connect')
def handle_connect(auth):
    # パスワードが一致しない場合は接続を拒否
    if not auth or auth.get('password') != CHAT_PASSWORD:
        return False  # Falseを返すとクライアント側にconnect_errorイベントが飛ぶ
    
    # 認証成功の場合のみ過去のログを送信
    emit('chat_history', list(chat_history))

@socketio.on('message')
def handle_message(data):
    # メッセージ送信時も簡易的なパスワードチェック（セキュリティ強化）
    if data.get('password') != CHAT_PASSWORD:
        return
        
    # クライアントに送り返すデータからパスワードを除外
    broadcast_data = {
        'user': data.get('user'),
        'msg': data.get('msg'),
        'time': data.get('time'),
        'sender_id': data.get('sender_id')
    }
    
    chat_history.append(broadcast_data)
    emit('message', broadcast_data, broadcast=True)

if __name__ == '__main__':
    # socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)