#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

_RESPONSE = {
    "status": "success",
    "api_version": "1.1",
    "contractor_id": "CONTRACTOR_DASMAP",
    "rows_returned": 2,
    "errors": [],
    "writes": [
        {
            "table": "satellite_data",
            "columns": ["block_id","acquisition_date","sensor","cloud_cover","ndvi","evi","ndre","savi","gndvi","features"],
            "conflict_columns": ["block_id","acquisition_date","sensor"],
            "presence_check": {"block_id_column":"block_id","recency_column":"acquisition_date","recency_days":14},
            "records": [{
                "block_id": "18", "acquisition_date": "2026-04-18", "sensor": "sentinel-2",
                "cloud_cover": "3.20", "ndvi": "0.6124", "evi": "0.3891",
                "ndre": "0.4201", "savi": "0.5012", "gndvi": "0.5534",
                "features": "{\"valid_pixel_ratio\": 0.968, \"low_quality\": false}"
            }]
        },
        {
            "table": "patcher_write_test",
            "columns": ["block_id","acquisition_date","sensor","test_value"],
            "conflict_columns": ["block_id","acquisition_date","sensor"],
            "presence_check": None,
            "records": [{
                "block_id": "18", "acquisition_date": "2026-04-18",
                "sensor": "sentinel-2", "test_value": "stage2_test"
            }]
        }
    ]
}


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.headers.get("X-API-Key"):
            self._send(401, {"error": "unauthorized", "api_version": "1.1"})
            return
        resp = {**_RESPONSE, "timestamp": datetime.now(timezone.utc).isoformat()}
        self._send(200, resp)

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)
        print(f"[mock_cloud] {self.command} {self.path} → {code}")

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print("[mock_cloud] Listening on port 8080 — Phase D two-entry writes mock")
    HTTPServer(("0.0.0.0", 8080), MockHandler).serve_forever()
