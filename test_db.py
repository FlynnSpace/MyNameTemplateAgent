import os
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. 加载环境变量
load_dotenv()

# 2. 获取配置
url = os.getenv("VITE_SUPABASE_URL") or "https://rgmbmxczzgjtinoncdor.supabase.co"
# 尝试读取两个可能的 Key 变量名
key = os.getenv("VITE_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

print("=" * 50)
print("🧪 Supabase Database Connection Test")
print("=" * 50)

if not url or not key:
    print("\n❌ Error: Missing Supabase configuration in .env file.")
    print(f"   VITE_SUPABASE_URL: {url}")
    print(f"   VITE_SUPABASE_ANON_KEY: {'*' * 5 if key else 'None'}")
    exit(1)

# 3. 初始化客户端
print(f"\n🔌 Connecting to Supabase...")
print(f"   URL: {url}")
try:
    supabase: Client = create_client(url, key)
    print("✅ Client initialized successfully.")
except Exception as e:
    print(f"❌ Failed to initialize client: {e}")
    exit(1)

# 4. 定义测试数据
test_id = str(uuid.uuid4())
table_name = "ppio_task_status"  # 请确认这是正确的表名
test_data = {
    "id": test_id,
    "url": "https://example.com/test-image.png",
    # 如果表中有其他必填字段（如 prompt, status），请在这里取消注释并添加
    # "prompt": "Test prompt from script",
    # "status": "success"
}

print(f"\n📝 Preparing to insert test data into table '{table_name}':")
print(f"   ID: {test_id}")
print(f"   URL: {test_data['url']}")

# 5. 执行插入
try:
    print("\n🚀 Inserting data...")
    response = supabase.table(table_name).insert(test_data).execute()
    print("✅ Insert operation executed.")
    # print("Response data:", response.data) 
except Exception as e:
    print(f"❌ Insert failed: {e}")
    print("\n💡 Tip: Check if table name is correct and RLS (Row Level Security) policies allow insertion.")
    exit(1)

# 6. 执行查询验证
print(f"\n🔍 Verifying data insertion...")
try:
    response = supabase.table(table_name).select("*").eq("id", test_id).execute()
    
    if response.data and len(response.data) > 0:
        record = response.data[0]
        print("✅ Verification SUCCESSFUL! Record found in database:")
        print("-" * 30)
        print(f"ID: {record.get('id')}")
        print(f"URL: {record.get('url')}")
        print(f"Created At: {record.get('created_at', 'N/A')}")
        print("-" * 30)
        
        # 可选：清理测试数据
        # print("\n🧹 Cleaning up test data...")
        # supabase.table(table_name).delete().eq("id", test_id).execute()
        # print("✅ Test data deleted.")
        
    else:
        print("❌ Verification FAILED: Record not found after insertion.")
        print("   This might be due to RLS policies hiding the row.")
except Exception as e:
    print(f"❌ Query failed: {e}")

print("\n✨ Test completed.")

