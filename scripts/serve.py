import json
import os
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.config import AppConfig, ConfigError
from automation.confirmed import (
    ConfirmedPayloadError,
    ConfirmedPayloadProcessor,
    validate_confirmed_payload,
)
from automation.roster import LearnedRosterStore, normalize_names

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
    processor = None
    roster_store = None

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
        try:
            validate_confirmed_payload(payload)
            return True
        except ConfirmedPayloadError:
            return False

    def do_GET(self):
        if self.path == "/api/roster":
            names = self.roster_store.load() if self.roster_store else []
            self._reply(200, {"ok": True, "names": names})
            return
        super().do_GET()

    def do_POST(self):
        if self.path not in {"/api/confirm", "/api/roster"}:
            self._reply(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                self._reply(400, {"ok": False, "error": "bad content length"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/roster":
                names = normalize_names(payload.get("names", []) if isinstance(payload, dict) else [])
                if not names or len(names) > 100:
                    self._reply(400, {"ok": False, "error": "invalid roster names"})
                    return
                if not self.roster_store:
                    self._reply(503, {"ok": False, "error": "local roster is unavailable"})
                    return
                result = self.roster_store.add(names)
                self._reply(200, {"ok": True, **result})
                return
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
            if self.processor:
                result = self.processor.process_file(target)
                self._reply(
                    200,
                    {
                        "ok": True,
                        "status": "finalized",
                        "file": Path(result["processed_file"]).name,
                        "meetings": len(result["outputs"]),
                        "replacements": sum(
                            output["replacements"] for output in result["outputs"]
                        ),
                        "roster_added": result["roster_added"],
                    },
                )
                return
            self._reply(200, {"ok": True, "status": "queued", "file": target.name, "meetings": len(payload["batch"])})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._reply(400, {"ok": False, "error": "invalid JSON request"})
        except ConfirmedPayloadError as error:
            self._reply(400, {"ok": False, "error": str(error)})
        except Exception as error:
            self._reply(500, {"ok": False, "error": str(error)})


def main():
    host = os.environ.get("PLOTLOOP_HOST", "127.0.0.1")
    port = int(os.environ.get("PLOTLOOP_PORT", "4173"))
    config_path = _expand_path(os.environ.get("PLOTLOOP_CONFIG", DEFAULT_CONFIG_PATH))
    try:
        config = AppConfig.load(config_path)
    except ConfigError:
        config = None
    if config:
        NoCacheHandler.processor = ConfirmedPayloadProcessor(config)
        NoCacheHandler.roster_store = LearnedRosterStore(config.state_dir / "roster.json")
    handler = partial(NoCacheHandler, directory=str(PROJECT_ROOT))
    ThreadingHTTPServer((host, port), handler).serve_forever()


if __name__ == "__main__":
    main()
