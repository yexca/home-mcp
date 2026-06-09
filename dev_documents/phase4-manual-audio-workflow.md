# Phase 4 Manual Audio Workflow Notes

Use only local environment variables for secrets. Do not write Matrix tokens in notes, logs, fixtures, or screenshots.

1. Start the gateway with a local config that enables `tts` and `matrix`.
2. Confirm ZeroClaw discovers `home__tts_synthesize`, `home__matrix_send_text`, and `home__matrix_send_audio`.
3. Call `home__tts_synthesize` with a short text sample and record only the returned `request_id`, `job_id`, and `artifact.id`.
4. Call `home__matrix_send_audio` with the returned audio artifact and an allowlisted `room_id`.
5. Verify Matrix returns an `event_id` and that the received message contains playable audio.
6. Confirm a non-allowlisted `room_id` returns `POLICY_DENIED`.
