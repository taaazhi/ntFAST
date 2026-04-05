"""
Get Gmail API Refresh Token
Run this script once to get a refresh token for Gmail API.
"""
import http.server
import urllib.parse
import webbrowser
import httpx

CLIENT_ID = "GMAIL_CLIENT_ID_REMOVED"
CLIENT_SECRET = "GMAIL_CLIENT_SECRET_REMOVED"
REDIRECT_URI = "http://localhost:8090"
SCOPE = "https://www.googleapis.com/auth/gmail.send"

auth_url = (
    f"https://accounts.google.com/o/oauth2/v2/auth?"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={REDIRECT_URI}&"
    f"response_type=code&"
    f"scope={SCOPE}&"
    f"access_type=offline&"
    f"prompt=consent"
)

print("Opening browser for Google authorization...")
print(f"\nIf browser doesn't open, go to:\n{auth_url}\n")
webbrowser.open(auth_url)

class Handler(http.server.BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        Handler.code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Success! You can close this window.</h1>")
    def log_message(self, *args):
        pass

server = http.server.HTTPServer(("localhost", 8090), Handler)
print("Waiting for authorization...")
server.handle_request()

if Handler.code:
    print(f"\nGot authorization code. Exchanging for tokens...")
    resp = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": Handler.code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    tokens = resp.json()
    if "refresh_token" in tokens:
        print(f"\n{'='*50}")
        print(f"REFRESH TOKEN (save this!):")
        print(f"{tokens['refresh_token']}")
        print(f"{'='*50}")
        print(f"\nAdd to Railway variables:")
        print(f"GMAIL_CLIENT_ID = {CLIENT_ID}")
        print(f"GMAIL_CLIENT_SECRET = {CLIENT_SECRET}")
        print(f"GMAIL_REFRESH_TOKEN = {tokens['refresh_token']}")
    else:
        print(f"Error: {tokens}")
else:
    print("No authorization code received.")
