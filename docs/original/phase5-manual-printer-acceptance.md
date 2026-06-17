# Phase 5 Manual Printer Acceptance Notes

Use only local environment variables for bridge secrets. Do not write printer bridge tokens, local file paths, or sensitive document contents in notes, logs, fixtures, or screenshots.

1. Start the printer bridge on the host and expose its HTTP URL only through `PRINTER_BRIDGE_URL`.
2. Set `PRINTER_BRIDGE_API_KEY` locally if the bridge requires authentication.
3. Start the gateway with a local config that enables `printer` and allowlists exactly the printer ID being tested.
4. Confirm ZeroClaw discovers `home__printer_list` and `home__printer_print_file`.
5. Call `home__printer_list` and verify only allowlisted printers are returned with `allowed: true`.
6. Create or reuse a small PDF, PNG, or JPEG artifact through the gateway.
7. Call `home__printer_print_file` with the artifact ID, allowlisted printer ID, copies, duplex, and color options.
8. Verify the physical printer output, bridge job status, gateway job record, and paired audit events.
9. Confirm a non-allowlisted printer returns `POLICY_DENIED`.
10. Confirm unsupported MIME types and oversized artifacts are rejected before reaching the printer bridge.
