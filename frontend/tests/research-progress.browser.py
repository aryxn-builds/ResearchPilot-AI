"""Run with Python Playwright and Chromium installed: python tests/research-progress.browser.py."""

import base64
import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

SESSION_ID = "79d64b7b-98db-4e7f-884d-536ae562cf12"
USER = {"id": "b79e6e32-8007-4f94-bb5e-f9fcaa882213", "email": "qa@example.test", "aud": "authenticated"}


def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


class Fixture(BaseHTTPRequestHandler):
    status = "researching"
    auth = ""

    def reply(self, code, body="", content_type="application/json"):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Accept, Apikey, X-Client-Info")
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_OPTIONS(self):
        self.reply(204)

    def do_GET(self):
        if self.headers.get("Authorization") != self.auth:
            self.reply(401, "{}")
        elif self.path == "/auth/v1/user":
            self.reply(200, json.dumps(USER))
        elif self.path == f"/api/v1/research/{SESSION_ID}/stream":
            self.reply(200, 'event: status_update\ndata: {"status":"researching"}\n\n', "text/event-stream")
        elif self.path == f"/api/v1/research/{SESSION_ID}" and self.status != "missing":
            self.reply(200, json.dumps({"data": {
                "id": SESSION_ID, "question": "what is GPT?", "status": self.status, "config": {"mode": "fast"},
            }}))
        else:
            self.reply(404, "{}")

    def log_message(self, *_args):
        pass


def main():
    fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    mock_url = f"http://127.0.0.1:{fixture.server_port}"
    expires = int(time.time()) + 3600
    token = f'{encode({"alg": "HS256", "typ": "JWT"})}.{encode({"sub": USER["id"], "exp": expires})}.fixture'
    Fixture.auth = f"Bearer {token}"
    session = {"access_token": token, "refresh_token": "fixture", "expires_at": expires, "user": USER}
    frontend = Path(__file__).resolve().parents[1]
    (frontend / "scratch").mkdir(exist_ok=True)
    env = {**os.environ, "NEXT_PUBLIC_SUPABASE_URL": mock_url,
           "NEXT_PUBLIC_SUPABASE_ANON_KEY": "local-fixture", "NEXT_PUBLIC_API_URL": mock_url}
    with (frontend / "scratch" / "research-progress-browser.log").open("w") as log:
        process = subprocess.Popen(
            ["node", "node_modules/next/dist/bin/next", "dev", "-H", "127.0.0.1", "-p", str(port)],
            cwd=frontend, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("Next.js browser fixture exited. See scratch/research-progress-browser.log.")
                try:
                    with urlopen(origin, timeout=2):
                        break
                except OSError:
                    time.sleep(0.5)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context()
                context.add_cookies([{"name": "sb-127-auth-token", "value": f"base64-{encode(session)}", "url": origin}])
                page = context.new_page()
                active = f"{origin}/research/active/{SESSION_ID}"
                Fixture.status = "missing"
                page.goto(active)
                expect(page.get_by_role("main").get_by_role("alert")).to_have_text(
                    "This research session could not be found."
                )
                Fixture.status = "researching"
                page.reload()
                expect(page.get_by_text("what is GPT?", exact=True)).to_be_visible()
                expect(page.get_by_role("list", name="Received research updates")).to_contain_text("Gathering sources")
                expect(page.get_by_text("Live updates interrupted. Checking research status.")).to_be_visible()
                page.reload()
                expect(page.get_by_text("what is GPT?", exact=True)).to_be_visible()
                Fixture.status = "completed"
                page.wait_for_url(f"{origin}/report/{SESSION_ID}", timeout=20000)
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
            fixture.shutdown()
    print("Chromium progress recovery passed")


if __name__ == "__main__":
    main()
