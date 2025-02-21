import os

# -------------------------------
# Supabase Connection Settings
# -------------------------------

# Supabase project URL (set via environment variable on Streamlit Cloud)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://gjhhvxmfyyaqerubiugx.supabase.co")

# Supabase anon (public) API key (this is safe to expose in a client app when RLS is enabled)
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdqaGh2eG1meXlhcWVydWJpdWd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDAxMzcxODAsImV4cCI6MjA1NTcxMzE4MH0.HCSBX2VOFrZk_hIF60l9JSLx4l6r8Qjg8uLM2o4Eb1k"
)

# The database schema you wish to work in
SUPABASE_SCHEMA = os.getenv("SUPABASE_SCHEMA", "public")

# -------------------------------
# Connection Pooling (Supavisor) Settings
# -------------------------------

# Pool Mode:
# 'transaction' mode (default) runs on port 6543 and returns connections after each transaction.
# To use 'session' mode, you would connect on port 5432 instead.
POOL_MODE = os.getenv("POOL_MODE", "transaction")  # options: "transaction" or "session"

# Pool Size:
# Maximum number of connections made to your underlying Postgres cluster per user+db combination.
POOL_SIZE = int(os.getenv("POOL_SIZE", "15"))

# Maximum client connections allowed (fixed based on your compute size)
MAX_CLIENT_CONNECTIONS = int(os.getenv("MAX_CLIENT_CONNECTIONS", "200"))

# -------------------------------
# SSL Configuration
# -------------------------------

# Enforce SSL on incoming connections (recommended for security).
ENFORCE_SSL = os.getenv("ENFORCE_SSL", "true").lower() in ["true", "1", "yes"]

# Optionally specify an SSL certificate path (if you need to provide one for your client).
SSL_CERT_PATH = os.getenv("SSL_CERT_PATH", None)

# -------------------------------
# Extra Settings / Notes
# -------------------------------
# - Extra Search Path (for Data API): "public, extensions" is typical.
#   This setting is managed in your Supabase project settings.
#
# - Max Rows is set to 1000 by default in the Data API to limit payload size.
#
# - These configuration values can be set via environment variables in your Streamlit Cloud app settings.
