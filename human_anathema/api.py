"""Small JSON-over-HTTP adapter. The game engine itself has no web dependency.

Start with: py -m human_anathema.api
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import Game

game = Game()


class Handler(BaseHTTPRequestHandler):
    server_version = "HumanAnathemaAPI/1.0"

    def _send(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def do_GET(self):
        if self.path == "/api/v1/state":
            return self._send(game.state_json())
        if self.path == "/api/v1/catalog":
            return self._send({"ok": True, "catalog": game.catalog})
        if self.path == "/api/v1/health":
            return self._send({"ok": True, "service": "human-anathema", "api_version": "v1"})
        return self._send({"ok": False, "error": "Route not found"}, 404)

    def do_POST(self):
        global game
        if self.path not in ("/api/v1/action", "/api/v1/new-game"):
            return self._send({"ok": False, "error": "Route not found"}, 404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 65536:
                return self._send({"ok": False, "error": "Request too large"}, 413)
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path.endswith("new-game"):
                game = Game()
                result = game.state_json()
            else:
                result = game.act(payload)
            return self._send(result, 200 if result.get("ok") else 400)
        except (ValueError, json.JSONDecodeError) as error:
            return self._send({"ok": False, "error": str(error)}, 400)

    def log_message(self, fmt, *args):
        print("[api] " + fmt % args)


def main():
    host, port = "127.0.0.1", 8765
    print(f"Human & Anathema API listening on http://{host}:{port}/api/v1")
    print("Use GET /state, GET /catalog, POST /action, POST /new-game")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
