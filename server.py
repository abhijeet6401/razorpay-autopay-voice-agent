"""Loopback demo server. Python 3.10+, no third-party dependencies."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from recovery import CUSTOMERS, Ledger, RecoveryError
from assistant import config

ROOT = Path(__file__).resolve().parent


def create_server(port=8765):
    ledger = Ledger()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def origin_ok(self):
            origin = self.headers.get("Origin")
            allowed = {"http://127.0.0.1:" + str(self.server.server_port), "http://localhost:" + str(self.server.server_port)}
            return self.headers.get("Host") in {"127.0.0.1:" + str(self.server.server_port), "localhost:" + str(self.server.server_port)} and (not origin or origin in allowed)

        def send(self, status, data, mime="application/json"):
            raw = json.dumps(data).encode() if mime == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.origin_ok():
                return self.send(403, {"error": "Local origin required"})
            path = urlsplit(self.path).path
            if path == "/api/customers":
                return self.send(200, {"customers": CUSTOMERS, "fictional": True})
            if path == "/api/assistant":
                return self.send(200, config())
            routes = {"/": "web/index.html", "/app.js": "web/app.js", "/style.css": "web/style.css", "/vapi.js": "web/dist/vapi.js"}
            if path not in routes:
                return self.send(404, {"error": "Not found"})
            target = ROOT / routes[path]
            if not target.is_file():
                return self.send(404, {"error": "Run npm install and npm run build for the live Vapi bundle"})
            mime = "text/html" if path == "/" else "text/css" if path.endswith(".css") else "text/javascript"
            return self.send(200, target.read_bytes(), mime)

        def do_POST(self):
            if not self.origin_ok():
                return self.send(403, {"error": "Local origin required"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16000 or not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise RecoveryError("Expected bounded JSON body")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise RecoveryError("Expected object")
                path = urlsplit(self.path).path
                if path == "/api/session":
                    result = ledger.start(body.get("customer_id"), body.get("mode"))
                elif path == "/api/tool":
                    result = ledger.tool(body.get("token"), body.get("name"), body.get("arguments"), body.get("tool_call_id"))
                elif path == "/api/state":
                    result = ledger.view(body.get("token"))
                elif path == "/api/settle":
                    result = ledger.settle(body.get("token"), body.get("reference"))
                elif path == "/api/live-event":
                    result = ledger.live_event(body.get("token"), body.get("call_id"))
                else:
                    return self.send(404, {"error": "Not found"})
                return self.send(200, result)
            except (RecoveryError, ValueError, TypeError):
                return self.send(400, {"ok": False, "error": "Request rejected; check identity, consent, action eligibility or session state."})
            except Exception:
                return self.send(500, {"ok": False, "error": "Demo backend unavailable"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.port)
    print("Cedar voice recovery demo: http://127.0.0.1:" + str(server.server_port), flush=True)
    print("Fictional records only. No telephone or real payment integration.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
