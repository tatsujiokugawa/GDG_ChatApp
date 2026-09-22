import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ご提示いただいたSupabaseの接続情報
SUPABASE_URL = "https://lkixnehkduusziskeufz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxraXhuZWhrZHV1c3ppc2tldWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIyNjY0MjMsImV4cCI6MjA5Nzg0MjQyM30.LkBvg6pa1Ub91idPApT1ri3UyYNpuWfWYsf6lvBVxpU"

# Supabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# def load_server_history():
#     """Supabaseから直接メッセージ履歴を最大100件取得する"""
#     try:
#         # 古い順（昇順）で取得
#         response = supabase.table("").select("*").order("timestamp", desc=False).limit(100).execute()
#         print(f"Loaded history from Supabase: {len(response.data) if response.data else 0} messages")
#         return response.data if response.data else []
#     except Exception as e:
#         print(f"❌ Error loading history from Supabase: {e}")
#         return []
def load_server_history():
    """Supabaseから直接メッセージ履歴を最大100件取得する"""
    try:
        # 古い順（昇順）で取得（テーブル名を "chat_messages" に、順序の基準を "time_str" に修正）
        response = supabase.table("chat_messages").select("*").order("time_str", desc=False).limit(100).execute()
        print(f"Loaded history from Supabase: {len(response.data) if response.data else 0} messages")
        return response.data if response.data else []
    except Exception as e:
        print(f"❌ Error loading history from Supabase: {e}")
        return []
    
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global Discussion Group ChatRoom v3.0 (Supabase)</title>
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
            background: #f8f9fa; 
            border: 1px solid #ced4da; 
            padding: 0;     
            cursor: pointer; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            transition: transform 0.2s, background 0.2s; 
            flex-shrink: 0;
            width: 38px; 
            height: 38px; 
            border-radius: 50%;
        }
        .settings-btn:hover { background: #e2e6ea; transform: rotate(45deg); }
        .settings-btn svg { width: 20px; height: 20px; fill: #333; display: block; }

        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: #fefefe; margin: 15% auto; padding: 20px; border: 1px solid #888; width: 90%; max-width: 400px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .modal-header h2 { margin: 0; font-size: 1.3em; }
        .close-btn { font-size: 28px; font-weight: bold; cursor: pointer; background: none; border: none; color: #aaa; padding: 0; line-height: 1; }
        .close-btn:hover { color: #000; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
        .modal-actions button { padding: 8px 16px; font-size: 15px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        .modal-actions button:hover { background: #0056b3; }
        
        .msg-text { 
            color: #333; 
            overflow-wrap: break-word; 
            word-break: normal; 
            line-height: 1.4;
        }
        .msg-text a { color: #007bff; text-decoration: underline; }
        .msg-text a:hover { color: #0056b3; }
    </style>
</head>
<body>
    <header>
        <h1>Global Discussion Group ChatRoom v3</h1>
    </header>

    <main>
        <div class="welcome-container">
            <p class="welcome-text">Welcome to the real-time chatroom for all GDG members.</p>
            <button id="settings-icon" class="settings-btn" title="Settings" aria-label="Open Settings">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-.97l2.11-1.66c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.66c-.04.32-.07.65-.07.97 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/>
                </svg>
            </button>
        </div>

        <div id="chat-area">
            <div id="chat-log" role="log" aria-label="Chat Log History"></div>
            <div class="input-group">
                <label for="message-input">Message</label>
                <small>Press Enter to send / Shift + Enter for a new line (URLs are auto-linked)</small>
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
        const socket = io({ transports: ['polling'] });

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

// 1. ページ読み込み時に保存された設定をフォームに反映
        window.addEventListener('DOMContentLoaded', () => {
            const savedPassword = localStorage.getItem('chat_password') || '';
            const savedName = localStorage.getItem('chat_name') || '';
            const savedTimestamp = localStorage.getItem('chat_timestamp') === 'true';

            const nameInput = document.getElementById('settings-name');
            const passwordInput = document.getElementById('settings-password');
            const timestampCheckbox = document.getElementById('settings-timestamp');

            if (nameInput) nameInput.value = savedName;
            if (passwordInput) passwordInput.value = savedPassword;
            if (timestampCheckbox) timestampCheckbox.checked = savedTimestamp;

            // 2. 歯車アイコンで設定モーダルを開く処理（もし未設定であれば）
            const settingsBtn = document.getElementById('settings-btn'); // 歯車ボタンのID
            const settingsModal = document.getElementById('settings-modal');
            if (settingsBtn && settingsModal) {
                settingsBtn.addEventListener('click', () => {
                    settingsModal.style.display = 'block';
                    settingsModal.setAttribute('aria-hidden', 'false');
                });
            }

            // 3. 閉じるボタン（×）でモーダルを非表示にする処理
            const closeBtn = document.getElementById('close-modal-btn');
            if (closeBtn && settingsModal) {
                closeBtn.addEventListener('click', () => {
                    settingsModal.style.display = 'none';
                    settingsModal.setAttribute('aria-hidden', 'true');
                });
            }

            // 4. 【追加】Saveボタンが押されたときの処理（保存 ＆ モーダルを閉じる）
            const saveBtn = document.getElementById('save-settings-btn');
            if (saveBtn && settingsModal) {
                saveBtn.addEventListener('click', () => {
                    // 入力値を chat_name などのキーで保存
                    if (nameInput) {
                        localStorage.setItem('chat_name', nameInput.value.trim());
                    }
                    if (passwordInput) {
                        localStorage.setItem('chat_password', passwordInput.value);
                    }
                    if (timestampCheckbox) {
                        localStorage.setItem('chat_timestamp', timestampCheckbox.checked);
                    }

                    // モーダルを非表示にして閉じる
                    settingsModal.style.display = 'none';
                    settingsModal.setAttribute('aria-hidden', 'true');
                });
            }
        });

        // 5. メッセージ送信処理
        function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            // 常に最新の chat_name を取得するので Anonymous に戻らなくなります
            const name = localStorage.getItem('chat_name') || 'Anonymous';
            const password = localStorage.getItem('chat_password') || '';
            
            if (message !== "") {
                socket.emit('send_message', { 
                    msg: message, 
                    name: name,
                    password: password 
                });
                input.value = ''; 
            }
        }

        document.getElementById('message-input').addEventListener('keydown', function(event) {
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
                    return;
                } else {
                    event.preventDefault();
                    sendMessage();
                }
            }
        });

        socket.on('load_history', function(history) {
            if (Array.isArray(history)) {
                renderHistoryList(history);
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
            return linkedText.replace(/\r\n/g, '<br>').replace(/\n/g, '<br>').replace(/\r/g, '<br>');
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
            const incomingName = data.name || 'Anonymous';
            
            const messageData = {
                name: incomingName,
                msg: data.msg || '',
                timestamp: data.timestamp || new Date().toISOString()
            };

            const elem = createMessageElement(messageData);
            chatLog.appendChild(elem);
            chatLog.scrollTop = chatLog.scrollHeight;

            playDingDong();
        });

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
            const name = document.getElementById('settings-name', name).value;
            const timestampChecked = document.getElementById('settings-timestamp').checked;

            localStorage.setItem('chat_password', pwd);
            localStorage.setItem('chat_name', name);
            localStorage.setItem('chat_timestamp', timestampChecked);

            location.reload();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    # 接続時にSupabaseから履歴を取得して送信
    history = load_server_history()
    emit('load_history', history)

# @socketio.on('send_message')
# def handle_message(data):
#     msg = data.get('msg', '').strip()
#     if not msg:
#         return
        
#     name = data.get('name', 'Anonymous')
#     JST = timezone(timedelta(hours=+9), 'JST')
#     timestamp = datetime.now(JST).isoformat()
    
#     message_data = {
#         'name': name,
#         'msg': msg,
#         'timestamp': timestamp
#     }
    
#     # Supabaseの 'messages' テーブルへ直接保存（インサート）
#     # try:
#     #     response = supabase.table("chat_messages).insert(message_data).execute()
#     #     print(f"✅ Successfully saved to Supabase: {response}")
#     try:
#         response = supabase.table("chat_messages").insert(message_data).execute()
#         print(f"✅ Successfully saved to Supabase: {response}")
#     except Exception as e:
#         print(f"❌ Error saving to Supabase: {e}")
    
#     # 全員にブロードキャスト送信
#     socketio.emit('receive_message', message_data)
@socketio.on('send_message')
def handle_message(data):
    msg = data.get('msg', '').strip()
    if not msg:
        return
        
    name = data.get('name', 'Anonymous')
    JST = timezone(timedelta(hours=+9), 'JST')
    timestamp = datetime.now(JST).isoformat()
    
    # Supabaseの実際のカラム名（username, msg, time_str）に合わせる
    message_data = {
        'username': name,
        'msg': msg,
        'time_str': timestamp
    }
    
    # Supabaseの 'chat_messages' テーブルへ保存
    try:
        response = supabase.table("chat_messages").insert(message_data).execute()
        print(f"✅ Successfully saved to Supabase: {response}")
    except Exception as e:
        print(f"❌ Error saving to Supabase: {e}")
    
    # ブラウザ側に送るデータ（画面表示用にはこれまで通り元のキー名で送信してもOKです）
    socketio.emit('receive_message', {
        'name': name,
        'msg': msg,
        'timestamp': timestamp
    })
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)