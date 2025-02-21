import os

# -------------------------------
# Supabase Connection Settings
# -------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://gjhhvxmfyyaqerubiugx.supabase.co")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdqaGh2eG1meXlhcWVydWJpdWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDAxMzcxODAsImV4cCI6MjA1NTcxMzE4MH0.HCSBX2VOFrZk_hIF60l9JSLx4l6r8Qjg8uLM2o4Eb1k"
)
SUPABASE_SCHEMA = os.getenv("SUPABASE_SCHEMA", "public")
