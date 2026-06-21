import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meet_backchat_secret_key'

# Windows環境でeventletを安定稼働させるための設定を自動選択
socketio = SocketIO(app, cors_allowed_origins="*")

# -------------------------------------------------------------------------
# スクリーンリーダー（アクセシビリティ）に配慮したHTMLテンプレート
# -------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>共通ミーティングチャット</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 20px auto; padding: 0 10px; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
        #chat-log { border: 2px solid #ccc; height: 400px; overflow-y: scroll; padding: 15px; margin-bottom: 15px; background: #f9f9f9; }
        .message { margin-bottom: 10px; padding: 8px; border-bottom: 1px solid #eee; }
        .input-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"] { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
    </style>
</head>
<body>

    <header>
        <h1>共通ミーティングチャット</h1>
        <p>Meet参加者も、そうでない人もリアルタイムで会話できる部屋です。</p>
    </header>

    <main>
        <section aria-labelledby="log-heading">
            <h2 id="log-heading" class="sr-only">チャット履歴</h2>
            <div id="chat-log" role="log" aria-live="polite" aria-relevant="additions">
                <div class="message"><em>システム: チャットルームに接続しました。発言を待っています。</em></div>
            </div>
        </section>

        <section aria-labelledby="form-heading">
            <h2 id="form-heading" class="sr-only">メッセージ投稿</h2>
            
            <div class="input-group">
                <label for="username">お名前</label>
                <input id="username" type="text" placeholder="例：鈴木" autocomplete="name">
            </div>

            <div class="input-group">
                <label for="myMessage">メッセージ本文</label>
                <input id="myMessage" type="text" placeholder="ここにメッセージを入力してEnter" onkeypress="handleKeyPress(event)">
            </div>

            <button onclick="sendMessage()">送信する</button>
        </section>
    </main>

    <script>
        var socket = io();

        // サーバーから新しいメッセージを受け取ったときの処理
        socket.on('message', function(data) {
            var log = document.getElementById('chat-log');
            var div = document.createElement('div');
            div.className = 'message';
            
            // スクリーンリーダーが「誰々：内容」と自然に聞き取れる形に整形して追加
            div.innerHTML = '<strong>' + data.user + ':</strong> ' + data.msg;
            log.appendChild(div);
            
            // 新しいメッセージが来たら自動で一番下までスクロール
            log.scrollTop = log.scrollHeight;
        });

        // メッセージを送信する処理
        function sendMessage() {
            var userField = document.getElementById('username');
            var msgField = document.getElementById('myMessage');
            
            var user = userField.value.trim() || '匿名ユーザー';
            var msg = msgField.value.trim();
            
            if(msg) {
                // サーバーにデータを送信
                socket.emit('message', {user: user, msg: msg});
                // 入力欄を空にして、次の入力をしやすくするためにフォーカスを戻す
                msgField.value = '';
                msgField.focus();
            }
        }

        // Enterキーが押されたときにも送信する工夫
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
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

@socketio.on('message')
def handle_message(data):
    # 受信した発言を、接続している全員の画面にリアルタイムで送り返す
    emit('message', data, broadcast=True)

if __name__ == '__main__':
    # どこのパソコンからでもアクセスを待ち受けられるように 0.00.00 で起動
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)