from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DATA = json.loads((Path(__file__).parent / "dispatch_data.json").read_text(encoding="utf-8"))
PAGE_HITS = {}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(200, {"status": "ok", "service": "flasheats-dispatch-api"})
            return
        if parsed.path != "/dispatch/orders":
            self._send(404, {"error": "not found"})
            return
        query = parse_qs(parsed.query)
        page = max(1, int(query.get("page", [1])[0]))
        page_size = min(200, max(1, int(query.get("page_size", [50])[0])))
        PAGE_HITS[page] = PAGE_HITS.get(page, 0) + 1
        if page == 3 and PAGE_HITS[page] == 1:
            self._send(500, {"error": "temporary upstream failure", "retryable": True})
            return
        if page == 5 and PAGE_HITS[page] == 1:
            self._send(429, {"error": "rate limit exceeded", "retry_after_seconds": 0.25})
            return
        start = (page - 1) * page_size
        end = start + page_size
        self._send(200, {
            "data": DATA[start:end],
            "page": page,
            "page_size": page_size,
            "has_more": end < len(DATA),
            "total_records": len(DATA),
        })

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
