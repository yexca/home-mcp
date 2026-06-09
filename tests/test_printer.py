from __future__ import annotations

import asyncio
import base64
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.errors import INVALID_ARGUMENT, POLICY_DENIED, UNSUPPORTED_MEDIA_TYPE
from modules.printer.providers.bridge_http import BridgeHttpPrinterProvider
from tests.helpers import fresh_phase5_gateway

PDF_BYTES = b"%PDF-1.4\n%test\n"


class PrinterBridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    requests = []
    printers = [
        {"id": "office_pdf", "name": "Office PDF", "status": "idle", "capabilities": {"duplex": True}},
        {"id": "secret_lab", "name": "Secret Lab", "status": "idle"},
    ]

    def do_GET(self) -> None:
        type(self).requests.append(
            {
                "method": "GET",
                "path": self.path,
                "auth": self.headers.get("Authorization", ""),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"printers": type(self).printers}).encode("utf-8"))

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(
            {
                "method": "POST",
                "path": self.path,
                "auth": self.headers.get("Authorization", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": body,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"job_id": "bridge-job-123", "status": "queued"}).encode("utf-8"))

    def log_message(self, format, *args):
        return


class PrinterProviderAndWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        PrinterBridgeHTTPRequestHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PrinterBridgeHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.bridge_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_bridge_provider_lists_and_prints_file(self) -> None:
        provider = BridgeHttpPrinterProvider(base_url=self.bridge_url, timeout_seconds=2, api_key="test-printer-token")

        printers = provider.list_printers()
        response = provider.print_file(
            printer_id="office_pdf",
            filename="test.pdf",
            mime_type="application/pdf",
            data=PDF_BYTES,
            copies=2,
            duplex="long_edge",
            color="monochrome",
            artifact_id="art_test",
        )

        self.assertEqual(printers[0].id, "office_pdf")
        self.assertEqual(response.bridge_job_id, "bridge-job-123")
        self.assertEqual(PrinterBridgeHTTPRequestHandler.requests[0]["auth"], "Bearer test-printer-token")
        request_body = json.loads(PrinterBridgeHTTPRequestHandler.requests[1]["body"].decode("utf-8"))
        self.assertEqual(request_body["printer_id"], "office_pdf")
        self.assertEqual(request_body["options"]["copies"], 2)
        self.assertEqual(base64.b64decode(request_body["data_b64"]), PDF_BYTES)

    def test_dispatcher_lists_only_allowlisted_printers_and_creates_print_job(self) -> None:
        services, _, dispatcher = fresh_phase5_gateway()
        services.config.raw["modules"]["printer"]["bridge_http"]["url"] = self.bridge_url
        artifact = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="application/pdf",
            extension="pdf",
            data=PDF_BYTES,
            owner="host_assistant",
            source_tool="test",
        )

        listed = asyncio.run(dispatcher.dispatch("printer_list", authorization="Bearer test-host-token"))
        printed = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {
                    "printer_id": "office_pdf",
                    "artifact_id": artifact.id,
                    "copies": 2,
                    "duplex": "long_edge",
                    "color": "monochrome",
                },
                authorization="Bearer test-host-token",
            )
        )
        job = services.jobs.get(printed["job_id"], services.policy.resolve_caller("Bearer test-host-token"))
        audit_rows = services.artifacts.conn.execute(
            "SELECT tool_name, status FROM audit_events WHERE tool_name = 'printer_print_file'"
        ).fetchall()

        self.assertTrue(listed["ok"])
        self.assertEqual([printer["id"] for printer in listed["printers"]], ["office_pdf"])
        self.assertTrue(all(printer["allowed"] for printer in listed["printers"]))
        self.assertTrue(printed["ok"])
        self.assertEqual(printed["print_job"]["bridge_job_id"], "bridge-job-123")
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.tool_name, "printer_print_file")
        self.assertTrue(audit_rows)
        self.assertNotIn("test-printer-token", str(printed))
        self.assertNotIn("test-printer-token", str([tuple(row) for row in audit_rows]))

    def test_print_security_rejects_policy_mime_size_copies_and_local_paths(self) -> None:
        services, _, dispatcher = fresh_phase5_gateway()
        services.config.raw["modules"]["printer"]["bridge_http"]["url"] = self.bridge_url
        pdf = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="application/pdf",
            extension="pdf",
            data=PDF_BYTES,
            owner="host_assistant",
            source_tool="test",
        )
        text = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="text/plain",
            extension="txt",
            data=b"text",
            owner="host_assistant",
            source_tool="test",
        )
        oversized = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="application/pdf",
            extension="pdf",
            data=b"x" * 129,
            owner="host_assistant",
            source_tool="test",
        )

        denied_printer = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {"printer_id": "secret_lab", "artifact_id": pdf.id},
                authorization="Bearer test-host-token",
            )
        )
        bad_mime = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {"printer_id": "office_pdf", "artifact_id": text.id},
                authorization="Bearer test-host-token",
            )
        )
        bad_size = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {"printer_id": "office_pdf", "artifact_id": oversized.id},
                authorization="Bearer test-host-token",
            )
        )
        bad_copies = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {"printer_id": "office_pdf", "artifact_id": pdf.id, "copies": 3},
                authorization="Bearer test-host-token",
            )
        )
        local_path = asyncio.run(
            dispatcher.dispatch(
                "printer_print_file",
                {"printer_id": "office_pdf", "artifact_id": pdf.id, "path": "C:/secret.pdf"},
                authorization="Bearer test-host-token",
            )
        )

        self.assertEqual(denied_printer["error"]["code"], POLICY_DENIED)
        self.assertEqual(bad_mime["error"]["code"], UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(bad_size["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_copies["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(local_path["error"]["code"], INVALID_ARGUMENT)


if __name__ == "__main__":
    unittest.main()
