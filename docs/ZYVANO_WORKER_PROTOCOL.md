# Vydria ↔ Zyvano Worker Protocol (v1)

**Status:** protocol contract and validation primitives only. This document does not claim that a network worker, broker, deployment, or model runtime integration is complete.

## Responsibility boundary

- **Zyvano** owns users, authentication, authorization, projects, credit policy, job state, asset ownership, retention, and audit records.
- **Vydria** owns local model installation, hardware detection, inference, temporary execution files, and local resource measurements.
- Vydria must remain independently installable and usable through its existing local CLI, ComfyUI bridge, and MCP interfaces.

## Transport and credentials

The production worker transport must be outbound-only over authenticated TLS. The inference host must not expose ComfyUI or the local agent API to the public internet. Zyvano issues a short-lived, revocable worker credential; user access tokens, payment secrets, and long-lived platform secrets never enter Vydria.

The protocol module in `vydria_worker.protocol` is transport-neutral and intentionally has no network client. A later worker process will use it to validate broker messages before translating accepted jobs into the existing local engine execution path.

## Message contract

- **Registration:** worker ID, engine/protocol version, task capabilities, exact model ID/version pairs, device, VRAM bytes, and RAM bytes.
- **Heartbeat:** worker liveness, availability, and bounded resource summary.
- **Job envelope:** opaque job/project/owner UUIDs, idempotency key, exact task/model/version, prompt, bounded generation settings, expiry, request hash, and opaque input asset references.
- **Progress:** job UUID, monotonically increasing sequence number, bounded stage and progress percentage.
- **Completion:** terminal status and opaque output asset references, or a bounded error code.
- **Cancellation:** authenticated job ID and acknowledgement; terminal state remains authoritative in Zyvano.

## Security invariants

1. No local filesystem path or arbitrary URL is accepted as an input/output asset reference.
2. No Zyvano user token, billing secret, or platform credential is accepted in worker registration or job payloads.
3. A model is selected by an exact immutable version; workers must reject unknown versions.
4. Jobs have an enforced expiry, a strictly formatted idempotency key, and a SHA-256 digest of the canonical wire request (all fields except `request_sha256`, JSON-encoded with sorted keys and compact separators). The worker verifies the digest before accepting the job.
5. Task names, dimensions, frame count, FPS, asset-reference count, progress values, and diagnostics are bounded. Expired jobs are rejected at validation time; callers may inject a clock value in tests.
6. Progress consumers use `ProgressSequenceTracker` to reject duplicate/replayed sequence numbers and decreasing progress percentages per job. The tracker is process-local; the broker remains authoritative for durable deduplication across restarts.
7. Unknown fields fail closed rather than being silently ignored.
8. The worker reports opaque asset references; Zyvano remains responsible for authenticated upload/download and asset ownership.
9. License policy and device eligibility must be checked before a job is dispatched.

## VDN-H3 model policy

The VDN-H3 model is a **zero-Zyvano-generation-credit, local-compute model option** only where the user's hardware is eligible and the model terms permit the intended use. This is not a promise of zero infrastructure cost or universal mobile compatibility. The published full checkpoint is large; the exact installed model revision, model-weight license, territorial eligibility, VRAM/RAM, disk requirements, and runtime support must be verified independently.

Do not download or redistribute weights as part of this protocol change. Do not mark VDN-H3 production-ready until the exact weight license is reviewed, model hashes are verified on the target installation, and a real inference smoke test succeeds.

## Validation

Run the GPU-free contract tests with:

```bash
python -m unittest discover -s tests -p 'test_worker_protocol.py' -v
```

These tests validate message shape and security boundaries; they do not prove GPU inference, network transport, or end-to-end Zyvano integration.


## Current Zyvano backend compatibility checkpoint

The current Zyvano backend exposes an internal Pulse API at `/internal/pulse/video-jobs` using the backend-only `x-zyvano-pulse-key` credential. Its request contract is a script plus a 30/60-second duration, resolution, orientation, and MP4 format. The current Pulse worker executes through Zyvano's own `NativeGenerationService` and database-backed lease queue.

That API is **not** the v1 Vydria worker protocol: it has no Vydria worker registration, heartbeat, broker job-pull, progress-event ingestion, scoped asset transfer, or worker cancellation endpoints. The general Zyvano native-generation worker registry is also currently database/Redis-backed inside the Zyvano deployment, not a remote worker broker.

Therefore, do not point a Vydria worker at the Pulse API or reuse the Pulse shared secret as a worker credential. Before enabling remote Vydria execution, Zyvano needs a separate authenticated worker-broker adapter that maps authorized project-owned generation jobs to v1 envelopes, issues short-lived revocable worker credentials, and durably validates progress/completion/cancellation. This compatibility checkpoint is based on the current Zyvano repository source and must be rechecked when that backend contract changes.
