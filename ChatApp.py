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
// キーボード入力欄の設定（Enterキーでの送信を最優先・強制実行）
        document.getElementById('message-input').addEventListener('keydown', function(event) {
            // Tab / Shift + Tab によるフォーカス移動は維持
            if (event.key === 'Tab' && event.shiftKey) {
                const messages = document.querySelectorAll('#chat-log .message');
                if (messages.length > 0) {
                    event.preventDefault();
                    messages[messages.length - 1].focus();
                }
                return;
            }

            // Enterキーが押されたら、改行のデフォルト動作を完全に潰して送信する
            if (event.key === 'Enter') {
                event.preventDefault();
                sendMessage();
            }
        });

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
