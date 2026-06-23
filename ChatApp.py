import os
from collections import deque
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meet_backchat_secret_key'

# 自動で最適な非同期モード（eventletなど）を選択
socketio = SocketIO(app, cors_allowed_origins="*")

# サーバーのメモリ上に過去ログを保存するキュー（最大100件に拡張）
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
        input[type="text"] { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
    </style>
</head>
<body>

    <header>
        <h1>Global Discussion Group ChatRoom</h1>
        <p>Welcome to the real-time chatroom for all GDG members.</p>
    </header>

    <main>
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
    </main>

    <script>
        var socket = io();
        var myClientId = null;

        // 画面が読み込まれたら、ブラウザから前回の名前を自動復元する
        window.addEventListener('DOMContentLoaded', (event) => {
            var savedUser = localStorage.getItem('chat_username');
            if (savedUser) {
                document.getElementById('username').value = savedUser;
            }
        });

        // ブラウザの機能で「ピピッ」と通知音を鳴らす関数（外部ファイル不要）
        function playNotificationSound() {
            try {
                var AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                var context = new AudioContext();
                
                // 1つ目の音（ピ）
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

                // 2つ目の音（ピッ）少しずらして高めの音
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

        // 接続時、サーバーから自分のソケットIDを受け取る
        socket.on('connect', function() {
            myClientId = socket.id;
            var sysMsg = document.getElementById('system-msg');
            if (sysMsg) sysMsg.innerHTML = '<em>System: Connected to the chatroom.</em>';
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
            
            // 他の人が書き込んだ（送信者のIDが自分と違う）場合のみ音を鳴らす
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
                // 入力された名前をブラウザに保存（空欄なら削除）
                if(userField.value.trim()) {
                    localStorage.setItem('chat_username', userField.value.trim());
                } else {
                    localStorage.removeItem('chat_username');
                }

                var now = new Date();
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

                var timestamp = hours + ':' + minutes + tz;

                // 自分のID(myClientId)も一緒にサーバーに送る
                socket.emit('message', {user: user, msg: msg, time: timestamp, sender_id: myClientId});
                msgField.value = '';
                msgField.focus();
            }
        }

        // キーボード入力時の処理
        function handleKeyPress(event) {
            // Enter単体であれば送信、Shift + Enter であれば改行
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault(); // Enterによる標準の改行を防止して送信
                sendMessage();
            }
            // 3行目以降の自動スクロールはブラウザの標準挙動により追従します
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# 新しく誰かが接続した際、その人だけに過去のログ（最大100件）を送信する
@socketio.on('connect')
def handle_connect():
    emit('chat_history', list(chat_history))

@socketio.on('message')
def handle_message(data):
    # メッセージを受け取ったら、まずサーバーのメモリ（最大100件）に追加
    chat_history.append(data)
    # 全員にブロードキャスト
    emit('message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)