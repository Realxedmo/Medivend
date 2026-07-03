"""
Supabase client singleton for MediVend backend.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hdpbzflntprxnctucyfp.supabase.co")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkcGJ6ZmxudHByeG5jdHVjeWZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzOTI4NzksImV4cCI6MjA4OTk2ODg3OX0."
        "Uw942S1TgTwJANz6p-3VReJuB8F-0cVDOTt8SpWq02s"
    )
)

_client: Client = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
