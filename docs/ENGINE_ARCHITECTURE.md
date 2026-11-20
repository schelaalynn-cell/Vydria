# Vydria Engine Architecture and Integration Assessment

**Status:** initial source-level assessment  
**Scope:** repository metadata, Python packaging, CLI, resource planner, ComfyUI bridge, agent API/MCP, request contracts, dependency pins, and model manifests.  
**Not a security certification:** this review did not execute the application, inspect every route or dependency, run the test suite, or validate model licensing with counsel.

## Executive summary

Vydria inherits a substantial local inference application rather than a small model wrapper. The current codebase already contains a resource-aware inference engine, a ComfyUI integration, a persistent job system, a versioned local agent HTTP API, and an MCP server. The next engineering step should preserve these capabilities while separating the inference runtime from the product-facing orchestration layer.

The safest integration model is **Zyvano as the product/control plane and Vydria as a separately operated inference worker**. Zyvano should not receive model weights, local filesystem paths, ComfyUI credentials, or Vydria installation tokens. A Vydria worker should initiate an authenticated outbound connection to a Zyvano-controlled broker and accept only explicitly authorized, schema-validated jobs.

## 1. Observed architecture

### Packaging and identity

- `pyproject.toml` declares the distribution as `freevideo-engine`, version `2026.9.16.41444`, and the CLI as `freevideo`.
- The import namespace remains `freevideo_engine`; `freevideo_engine.__init__` initializes platform-specific process, compiler, and library-path behavior.
- The project requires Python `>=3.12,<3.13`. Runtime extras pin major GPU/runtime components, including Triton, Transformers, Accelerate, PEFT, Diffusers-related dependencies, and model download clients.
- This is an important compatibility constraint: renaming the distribution or CLI in-place could break existing launchers, scripts, ComfyUI integrations, and installed environments. Keep compatibility entry points during any later Vydria identity migration.

### Inference and resource management

- `freevideo_engine.cli` exposes planning, diagnostics, optimization, history, preparation, encoding, and generation commands.
- `freevideo_engine.policy`, `hardware`, `kernel_capabilities`, and related modules form the hardware/resource planning layer.
- `docs/execution-planning.md` describes per-request placement across GPU memory, host memory, and disk, with kernel selection, activation staging, chunking, and bounded recovery behavior.
- `freevideo_engine.comfy_bridge` supervises the engine CLI in child processes and forwards progress. Its module documentation explicitly keeps Torch/model imports out of the ComfyUI process.
- `freevideo_engine.processes` contains process supervision and platform-specific worker handling.

### ComfyUI and agent interfaces

- `freevideo_engine.agent.routes` registers the versioned HTTP API under `/freevideo/agent/v1/*` on ComfyUI's `PromptServer`.
- `freevideo_engine.agent.schema` describes itself as the single request contract shared by runtime, OpenAPI, MCP, and CLI.
- `freevideo_engine.agent.client` is a standard-library HTTP client that reads a local endpoint and installation token, uploads local media, and talks to the local API.
- `freevideo_engine.agent.mcp` exposes the existing functionality through MCP stdio, delegating to the local HTTP API.
- Agent jobs and session data are stored below the ComfyUI output root in a `FreeVideo/.agent` directory. This is useful for a local desktop workflow, but it is not yet a durable cloud job store.

## 2. Security and operational observations

### Existing protections observed

- Agent API requests use a per-installation bearer token. The token is created with restrictive file handling and POSIX mode `0600`; existing token files are checked for regular-file type and ownership.
- The API has a peer/origin policy in `agent/access.py`. Local routes require loopback access; non-loopback private-network access requires explicit LAN configuration. Host and Origin checks are also performed.
- The route layer validates method, path, query, and request body against explicit contracts, bounds JSON/upload sizes, and returns structured errors.
- The HTTP client refuses credential-bearing cross-origin redirects.
- The ComfyUI bridge uses child processes and runtime/device leases to isolate expensive inference and coordinate shared GPU access.
- Model/dependency manifests pin upstream source revisions. The model file manifest includes file sizes and SHA-256 values for many large artifacts.

### Items requiring targeted verification

These are review targets, not confirmed vulnerabilities:

1. **Default agent activation:** `FREEVIDEO_AGENT` is enabled unless explicitly set to `0/false/no/off`. The route code contains meaningful local-peer and token protections, so default-on does not by itself establish remote exposure. Still, deployments should make the intended exposure mode explicit and verify the ComfyUI bind address and LAN setting.
2. **ComfyUI trust boundary:** the API is mounted into the ComfyUI server. Review the complete route table and any reverse-proxy/device-identity paths before placing ComfyUI behind a public proxy.
3. **Local filesystem authority:** agent tools can import local media, retrieve library assets, and operate on projects. Continue validating every path at the boundary; never translate a cloud-supplied path into an unrestricted local filesystem read.
4. **Upload and media parsing:** large uploads and image/video/audio decoding are resource-intensive. Verify decompression limits, duration/dimension limits, temporary-file cleanup, and cancellation behavior under malformed and concurrent inputs.
5. **Model and dependency supply chain:** immutable revisions and hashes are a strong base, but the audit should verify that every downloaded artifact is checked before use, all mirrors map to the same content, and license/NOTICE files are retained.
6. **Persistent job recovery:** verify crash recovery, idempotency, queue fairness, cancellation races, and cleanup/retention for jobs, sessions, imports, and generated assets.
7. **Telemetry and privacy:** confirm that prompts, media, filesystem paths, tokens, and diagnostic bundles are not sent to third parties without explicit user action.

## 3. Zyvano integration boundary

### Recommended responsibility split

| Zyvano control plane | Vydria inference worker |
| --- | --- |
| User identity, authentication, authorization | Local model/runtime installation |
| Projects, ownership, quotas, billing | GPU/CPU/RAM detection and scheduling |
| Prompt/product experience and workflow orchestration | Model loading, inference, decoding |
| Job request authorization and audit events | Execution progress, resource measurements |
| Output metadata, retention policy, asset ownership | Temporary files and local execution cache |
| Worker registration and revocation | Outbound worker connection and job execution |

### Required transport-neutral job contract

The first integration contract should be independent of ComfyUI and MCP. It should define:

- `worker.register`: worker identity, software version, supported models/tasks, hardware capabilities, and a short-lived credential.
- `worker.heartbeat`: liveness, availability, resource summary, and active-job count.
- `job.submit`: an opaque job ID, idempotency key, authorized model/task, validated generation parameters, and references to uploaded assets.
- `job.progress`: monotonic progress events with stage, timestamp, and bounded diagnostic details.
- `job.complete`: status, output asset references, generation metadata, and measured resource usage.
- `job.cancel`: authenticated cancellation with a defined acknowledgement and terminal state.
- `asset.upload` / `asset.download`: short-lived, scoped transfer URLs; never arbitrary filesystem paths.

Every job should carry an immutable owner/project reference, a request hash, an idempotency key, and an explicit model/license policy decision. The worker must reject unknown task types, unsupported model revisions, expired credentials, and parameters outside the shared schema.

### Network and credential model

- The worker should establish an **outbound TLS connection** to the Zyvano broker. Do not expose the local ComfyUI server or its agent token to the public internet.
- Use a short-lived worker credential scoped to registration and job execution; support revocation and rotation.
- Use signed or otherwise authenticated job envelopes and verify their owner, expiry, request hash, and model policy before execution.
- Keep Zyvano user credentials, billing secrets, and long-lived platform keys off the worker.
- Transfer media using scoped, expiring object URLs or a brokered stream. Do not allow user-supplied URLs to become unrestricted server-side fetches.
- Keep the existing local MCP API as a developer/local-automation interface. It should not become the cloud integration protocol.

## 4. Implementation sequence

1. **Compatibility baseline:** capture current branch/commit, Python packaging metadata, CLI behavior, existing tests, and supported ComfyUI integration points.
2. **Security regression suite:** cover local-only access, LAN opt-in, bearer-token validation, origin/host rejection, credential redirect refusal, upload bounds, path traversal, and job cancellation/idempotency.
3. **Stable engine contract:** define typed request/result/event schemas and capability negotiation, reusing the existing validation model where appropriate.
4. **Worker adapter:** implement an outbound-only worker process that translates broker jobs into the existing local engine/ComfyUI execution path. Keep inference implementation unchanged initially.
5. **Asset and job lifecycle:** add scoped transfer, durable state transitions, retry semantics, cleanup, and auditable completion metadata.
6. **Vydria identity migration:** introduce Vydria package/CLI names with compatibility aliases and a deprecation plan; do not break the inherited `freevideo_engine` namespace prematurely.
7. **Zyvano integration:** connect the platform to the broker contract, not directly to ComfyUI or the local agent API.

## 5. Acceptance criteria for the first worker release

- No inbound public port is required on the inference machine.
- No Zyvano user session or platform secret is stored in the worker.
- A job cannot be executed twice when the same idempotency key is replayed.
- Cancellation has deterministic acknowledged and terminal states.
- Unsupported models, tasks, hardware, and license states fail closed.
- Every output is attributable to a project/job and has reproducible generation metadata.
- Local MCP and desktop workflows continue to work.
- Security tests run without loading multi-gigabyte model weights or requiring a GPU.

## 6. Evidence and limitations

This assessment is based on source files inspected in the repository, including:

- `pyproject.toml`
- `freevideo_engine/__init__.py`
- `freevideo_engine/cli.py`
- `freevideo_engine/bootstrap.py`
- `freevideo_engine/comfy_bridge.py`
- `freevideo_engine/processes.py`
- `freevideo_engine/agent/__init__.py`
- `freevideo_engine/agent/routes.py`
- `freevideo_engine/agent/access.py`
- `freevideo_engine/agent/schema.py`
- `freevideo_engine/agent/client.py`
- `freevideo_engine/agent/mcp.py`
- `freevideo_engine/dependencies.json`
- `freevideo_engine/model_files.json`
- `docs/execution-planning.md`

No application code or runtime behavior is changed by this assessment. The next code change should be the security regression suite and worker contract, not a broad rename or a direct public exposure of the existing ComfyUI API.
