import os
os.add_dll_directory(r"F:\BrfCs\Studies\GlobalDiscussionGroup\meet-backchat")
# --- ここから下に既存のコード（import psycopg as psycopg2 など）が続くようにします ---
import os
import sys
from flask import Flask
from flask_socketio import SocketIO, emit

# -------------------------------------------------------------------------
# 【重要】Windows環境 + Python 3.15 用の psycopg2 互換レイヤー
# -------------------------------------------------------------------------
# 先ほどPCにインストールした psycopg(v3) を使って、古い psycopg2 の動きを完全再現します。
# これにより、以降のデータベース処理コードを一切汚さずにそのまま動かすことができます。
import psycopg

class DictCursorAdapter:
    """psycopg2 の DictCursor の挙動を psycopg v3 で再現するアダプター"""
    def __init__(self, cursor):
        self.cursor = cursor
    def execute(self, query, params=None):
        # v3のプレースホルダー（%s）形式をそのまま実行
        self.cursor.execute(query, params)
    def fetchall(self):
        # 取得したデータを辞書型のように扱える形式（dict_row）に変換して返却
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
        # v3の標準カーソルを取得し、DictCursor要求時はアダプターを噛ませる
        cur = self.conn.cursor()
        if cursor_factory is not None:
            return DictCursorAdapter(cur)
        return cur
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

class psycopg2_mock:
    """psycopg2 モジュールのダミーオブジェクト"""
    @staticmethod
    def connect(url):
        # Supabaseのプール接続(6543)に最適化したパラメータに自動調整
        if "pooler.supabase.com" in url and "prepare_threshold" not in url:
            if "?" in url:
                url += "&prepare_threshold=0"
            else:
                url += "?prepare_threshold=0"
        conn = psycopg.connect(url)
        return PostgresConnectionAdapter(conn)

# 既存のコードが「psycopg2」として認識できるように偽装します
psycopg2 = psycopg2_mock
DictCursor = "DictCursor"  # ダミー定義

# -------------------------------------------------------------------------
# ここから元のプログラムのメイン処理
# -------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'meet_backchat_secret_key')
 
# 共通パスワードの設定
CHAT_PASSWORD = os.environ.get('CHAT_PASSWORD', 'gdg2026')
 
# SocketIOの設定
socketio = SocketIO(app, cors_allowed_origins="*")
 
# Supabaseの接続情報（環境変数から取得、なければデフォルト値）
# ⚠️ テスト時はここに直接「postgresql://...」のURLを書いても動きます
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
    </header>
    </body>
</html>
"""

# HTMLを表示するための仮ルート（前回の構成に合わせて調整してください）
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)