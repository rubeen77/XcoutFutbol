import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / ".env")

_url = os.environ.get("SUPABASE_URL")
_key = os.environ.get("SUPABASE_KEY")

if not _url or not _key:
    raise EnvironmentError("SUPABASE_URL y SUPABASE_KEY deben estar definidas en backend/.env")

supabase: Client = create_client(_url, _key)
