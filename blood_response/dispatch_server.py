"""Local-only server for the hackathon demo. No database, frontend build or secret in JS."""
import argparse
import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlparse
from .dispatch import Simulation, iso
from .decisions import Controller, DecisionsClient
from .model import DEFAULT_DATA, ROOT

ASSETS = Path(__file__).with_name("web")


class App:
    def __init__(self, controller, output, data=DEFAULT_DATA, scheduler='greedy'):
        self.output, self.data, self.controller = Path(output), data, controller
        self.scheduler = scheduler
        self.output.mkdir(parents=True, exist_ok=False)
        self.sim = Simulation(data, controller, scheduler=scheduler)
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.root_output = self.output
        self.run_number = 1

    def state(self):
        return self.sim.snapshot()


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # No request headers or bodies in logs.
            pass

        def respond(self, code, data, mime="application/json"):
            body = json.dumps(data, ensure_ascii=False).encode() if mime == "application/json" else data
            self.send_response(code)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.end_headers()
            self.wfile.write(body)

        def host_valid(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.host_valid():
                return self.respond(403, {"error": "Local host required"})
            path = urlparse(self.path).path
            if path == "/api/state":
                with app.lock:
                    return self.respond(200, app.state())
            if path == "/api/export":
                with app.lock:
                    app.sim.export(app.output)
                    return self.respond(200, (app.output / "replay.json").read_bytes(), "application/octet-stream")
            if path == "/":
                content = (ASSETS / "index.html").read_text(encoding="utf-8").replace("__CSRF_TOKEN__", app.token)
                return self.respond(200, content.encode(), "text/html")
            allowed = {"/app.js": "application/javascript", "/style.css": "text/css", "/vendor/leaflet.js": "application/javascript",
                       "/vendor/leaflet.css": "text/css"}
            if path in allowed:
                return self.respond(200, (ASSETS / path.lstrip("/")).read_bytes(), allowed[path])
            self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.host_valid() or self.headers.get("X-Demo-Token") != app.token:
                return self.respond(403, {"error": "Local demo token required"})
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.respond(403, {"error": "Same-origin request required"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond(415, {"error": "JSON required"})
            if not app.lock.acquire(blocking=False):
                return self.respond(409, {"error": "A decision is in progress; try again shortly"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 <= size <= 16384:
                    raise ValueError("Request is too large")
                body = json.loads(self.rfile.read(size) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("Expected an object")
                if self.path == "/api/step":
                    app.sim.step()
                elif self.path == "/api/tick":
                    app.sim.tick()
                elif self.path == "/api/request":
                    minutes = body.pop("deadline_minutes", 45)
                    if type(minutes) is not int or not 1 <= minutes <= 180:
                        raise ValueError("Deadline must be 1–180 minutes")
                    body["deadline"] = iso(app.sim.now + minutes*60)
                    body["source"] = "manual_demo_request"
                    app.sim.inject(body)
                elif self.path == "/api/what-if":
                    app.sim.what_helps(body.get('request_id'))
                    app.sim.capture()
                elif self.path == "/api/restart":
                    app.sim.export(app.output)
                    app.run_number += 1
                    app.output = app.root_output / f"run-{app.run_number}"
                    app.output.mkdir(exist_ok=False)
                    app.sim = Simulation(app.data, app.controller, scheduler=app.scheduler)
                else:
                    return self.respond(404, {"error": "Unknown action"})
                if not app.sim.queue:
                    app.sim.export(app.output)
                result = app.state()
            except (ValueError, KeyError, TypeError) as error:
                result = {"error": str(error)}
            finally:
                app.lock.release()
            # Finish the state transaction before the client can send its next action.
            self.respond(400 if "error" in result else 200, result)
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Paris drone blood-distribution simulation")
    parser.add_argument("--controller", choices=["algorithm", "decisions"], default="algorithm")
    parser.add_argument("--scheduler", choices=['greedy', 'rolling'], default='rolling', help='Rolling lookahead or the unchanged greedy baseline')
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "drone-demo")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--prompt-key", action="store_true", help="Read key without echo; keep it in memory")
    parser.add_argument("--env-file", type=Path, help="Read only OPENAI_API_KEY from a local .env file")
    parser.add_argument("--max-api-calls", type=int, default=200)
    parser.add_argument("--run-all", action="store_true", help="Run the entire scenario and export, without a server")
    args = parser.parse_args(argv)
    key = os.environ.get("OPENAI_API_KEY")
    if args.env_file:
        for line in args.env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if args.prompt_key:
        key = getpass.getpass("OpenAI API key (hidden, memory only): ")
    if args.output.exists():
        parser.error("Output directory already exists; choose a new run directory")
    client = DecisionsClient(key, args.output, args.max_api_calls) if args.controller == "decisions" else None
    app = App(Controller(client), args.output, args.data, args.scheduler)
    if args.run_all:
        while app.sim.queue:
            app.sim.step()
        print(json.dumps(app.sim.export(app.output), indent=2))
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler(app))
    print(f"Paris dispatch demo: http://127.0.0.1:{args.port}/ · controller={args.controller}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        app.sim.export(app.output)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
