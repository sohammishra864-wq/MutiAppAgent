"""One-time script to get a Spotify refresh token. Run: python scripts/spotify_auth.py"""
import http.server
import urllib.parse
import webbrowser
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8888/callback"
SCOPES = "playlist-modify-public playlist-modify-private"

if not CLIENT_ID or not CLIENT_SECRET:
    print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env first")
    exit(1)

auth_url = (
    f"https://accounts.spotify.com/authorize?client_id={CLIENT_ID}"
    f"&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
)

code = None

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global code
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Got it! You can close this tab.")

    def log_message(self, *args):
        pass

print(f"Opening browser for Spotify login...")
webbrowser.open(auth_url)

server = http.server.HTTPServer(("localhost", 8888), Handler)
server.handle_request()

if not code:
    print("No auth code received.")
    exit(1)

resp = httpx.post("https://accounts.spotify.com/api/token", data={
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": REDIRECT_URI,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
})

data = resp.json()
if "refresh_token" in data:
    print(f"\nYour refresh token:\n\n  SPOTIFY_REFRESH_TOKEN={data['refresh_token']}\n\nPaste that into your .env file.")
else:
    print(f"Error: {data}")
