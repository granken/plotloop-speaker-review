import json
import os
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "plotloop-speaker-review" / "config.json"
MAX_BODY = 5 * 1024 * 1024


def _expand_path(value):
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()


def resolve_confirmed_dir(environ=None, project_root=PROJECT_ROOT):
    env = os.environ if environ is None else environ
    explicit = env.get("PLOTLOOP_CONFIRMED_DIR")
    if explicit:
        return _expand_path(explicit)

    config_path = _expand_path(env.get("PLOTLOOP_CONFIG", DEFAULT_CONFIG_PATH))
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"cannot read PlotLoop config: {config_path}") from error
        if config.get("confirmed_dir"):
            return _expand_path(config["confirmed_dir"])
        if config.get("work_target"):
            return _expand_path(config["work_target"]) / "confirmed"

    return Path(project_root).resolve() / ".local" / "confirmed"


CONFIRMED_DIR = resolve_confirmed_dir()


class NoCacheHandler(SimpleHTTPRequestHandler):
    confirmed_dir = CONFIRMED_DIR

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def _reply(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _valid_payload(payload):
        return (
            isinstance(payload, dict)
            and payload.get("type") == "speaker-review"
            and payload.get("version") == 2
            and isinstance(payload.get("batch"), list)
            and bool(payload["batch"])
        )

    def do_POST(self):
        if self.path != "/api/confirm":
            self._reply(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                self._reply(400, {"ok": False, "error": "bad content length"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not self._valid_payload(payload):
                self._reply(400, {"ok": False, "error": "not a speaker-review v2 payload"})
                return
            self.confirmed_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = self.confirmed_dir / ("speaker-review-" + stamp + ".json")
            tmp = target.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(target)
            self._reply(
                200,
                {"ok": True, "file": target.name, "meetings": len(payload["batch"])},
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._reply(400, {"ok": False, "error": "invalid JSON request"})
        except Exception as error:
            self._reply(500, {"ok": False, "error": str(error)})


def main():
    host = os.environ.get("PLOTLOOP_HOST", "127.0.0.1")
    port = int(os.environ.get("PLOTLOOP_PORT", "4173"))
    handler = partial(NoCacheHandler, directory=str(PROJECT_ROOT))
    ThreadingHTTPServer((host, port), handler).serve_forever()


if __name__ == "__main__":
    main()
