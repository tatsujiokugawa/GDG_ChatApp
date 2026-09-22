import os
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

print(f"URL: {url}")
print(f"KEY exists: {bool(key)}")

if not url or not key:
	print("エラー: 環境変数が設定されていません。")
	exit(1)

supabase = create_client(url, key)

# テストデータの挿入
test_data = {
	"content": "テストメッセージです",
	"user": "DebugUser"
}

try:
	print("SupabaseへのINSERTを試行します...")
	response = supabase.table("messages").insert(test_data).execute()
	print("成功しました！レスポンス:", response)
except Exception as e:
	print("失敗しました。エラー内容:", e)
