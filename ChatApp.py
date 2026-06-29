import os
import sys

# Windows（自分のパソコン）のときだけDLLディレクトリを設定
if os.name == 'nt':
    os.add_dll_directory(r"F:\BrfCs\Studies\GlobalDiscussionGroup\meet-backchat")

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# -------------------------------------------------------------------------
# 【重要】Windows環境 + Python 3.15 用の psycopg2 互換レイヤー
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

# class psycopg2_mock:
#     """psycopg2 モジュールのダミーオブジェクト"""
#     @staticmethod
#     def connect(url):
#         if "pooler.supabase.com" in url and "prepare_threshold" not in url:
#             if "?" in url:
#                 url += "&prepare_threshold=0"
#             else:
#                 url += "?prepare_threshold=0"
#         conn = psycopg.connect(url)
#         return PostgresConnectionAdapter(conn)
class psycopg2_mock:
    """psycopg2 モジュールのダミーオブジェクト"""
    @staticmethod
    def connect(url):
        # URLに「?」が含まれている場合、それ以降の邪魔なオプション（pgbouncer等）をすべて切り捨てる
        if "?" in url:
            url = url.split("?")[0]
        
        conn = psycopg.connect(url)
        return PostgresConnectionAdapter(conn)
# class psycopg2_mock:
#     """psycopg2 モジュールのダミーオブジェクト"""
#     @staticmethod
#     def connect(url):
#         # Supabaseのプール接続(6543)に最適化したパラメータに自動調整
#         if "pooler.supabase.com" in url and "prepare_threshold" not in url:
#             if "?" in url:
#                 url += "&prepare_threshold=0"
#             else:
#                 url += "?prepare_threshold=0"
        
#         # 追加：新しいpsycopgが嫌がるパラメータを安全に削除
#         url = url.replace("pgbouncer=true", "").replace("&&", "&").replace("?&", "?")
        
#         conn = psycopg.connect(url)
#         return PostgresConnectionAdapter(conn)
psycopg2 = psycopg2_mock
DictCursor = "DictCursor"

# -------------------------------------------------------------------------
# ここから元のプログラムのメイン処理
# -------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meet_backchat_secret_key')

CHAT_PASSWORD = os.environ.get('CHAT_PASSWORD', 'gdg2026')
socketio = SocketIO(app, cors_allowed_origins="*")

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'ここに手順1-7でコピーしたURIを貼り付ける')
MAX_HISTORY = 100

def get_db_connection():
    return psycopg2.connect(SUPABASE_URL)

def init_db():
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
    conn = get_db_connection()
    history = []
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute('SELECT username, msg, time_str, sender_id FROM chat_messages ORDER BY id DESC LIMIT %s', (MAX_HISTORY,))
            rows = cursor.fetchall()
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
        
        /* 追加：ヘッダーのレイアウトと歯車用スタイル */
        .welcome-container { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
        .welcome-text { font-size: 1.1em; font-weight: bold; margin: 0; }
        .settings-btn { cursor: pointer; font-size: 24px; user-select: none; transition: transform 0.2s; }
        .settings-btn:hover { transform: rotate(45deg); }
        #history-status { color: #888; font-style: italic; margin: 5px 0 15px 0; }
    </style>
</head>
<body>
    <header>
        <h1>Global Discussion Group ChatRoom</h1>
    </header>

    <main>
        <div class="welcome-container">
            <p class="welcome-text">Welcome to the real-time chatroom for all GDG members..</p>
            <span id="settings-icon" class="settings-btn" title="Settings">⚙</span>
        </div>

        <p id="history-status">System: History being loaded.</p>

        <div id="auth-area">
            <div class="input-group">
                <label for="password">Password</label>
                <input type="password" id="password" placeholder="Enter room password">
            </div>
            <button id="login-btn">Join Chat</button>
        </div>

        <div id="chat-area">
            <div id="chat-log" role="log" aria-live="polite"></div>
            <div class="input-group">
                <input type="text" id="message-input" placeholder="Type a message...">
            </div>
            <button id="send-btn">Send</button>
        </div>
    </main>

    <script>
        // 本番/ローカル共通のSocket.IO初期化
        const socket = io();

        // ダミーログイン処理（必要に応じて既存の認証ロジックと統合してください）
        document.getElementById('login-btn').addEventListener('click', () => {
            document.getElementById('auth-area').style.display = 'none';
            document.getElementById('chat-area').style.display = 'block';
            
            // ログイン成功時にサーバーへ履歴を要求（または自動で降ってくるイベントを模擬）
            // ここでは1.5秒後に読み込みが完了したと仮定してステータスを消去するデモを兼ねています
            setTimeout(() => {
                const statusMessage = document.getElementById('history-status');
                if (statusMessage) {
                    statusMessage.remove(); // 読み込み完了後に要素を完全に消去
                }
            }, 1500);
        });

        // 💡 サーバーから履歴データが届いた時の正規の処理（Socket.IOイベント）
        socket.on('load_history', function(history) {
            const chatLog = document.getElementById('chat-log');
            // ここで履歴を画面に描画する処理を挟む
            
            // 描画が完了したら、読み込み中メッセージを完全に消去する
            const statusMessage = document.getElementById('history-status');
            if (statusMessage) {
                statusMessage.remove();
            }
        });

        // 💡 歯車アイコンがクリックされた時のイベント監視（次のステップ用）
        document.getElementById('settings-icon').addEventListener('click', function() {
            console.log("歯車アイコンがクリックされました。");
            alert("*** Under Construction; To be built by July 11th ***");
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)