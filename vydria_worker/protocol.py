"""Transport-neutral, GPU-free protocol types for the Vydria worker boundary.

This module deliberately uses only the Python standard library. It validates
opaque Zyvano asset references and never accepts local paths, arbitrary URLs,
user credentials, or platform secrets in job envelopes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
from threading import Lock
from typing import Any
from uuid import UUID

PROTOCOL_VERSION = "1"
TASKS = frozenset({"video_text_to_video", "video_image_to_video"})
PROGRESS_STAGES = frozenset({
    "accepted", "preparing", "loading_model", "encoding_prompt",
    "inference", "decoding", "packaging",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$")
_OPAQUE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_WORKER_ID = re.compile(r"^vydria-[A-Za-z0-9][A-Za-z0-9._-]{0,72}$")


class ProtocolError(ValueError):
    """Raised when a worker message violates the versioned protocol."""


def canonical_request_sha256(value: dict[str, Any]) -> str:
    """Hash the exact wire request, excluding only its self-referential digest."""
    if not isinstance(value, dict):
        raise ProtocolError("job must be an object")
    payload = {key: item for key, item in value.items() if key != "request_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: Any, name: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(f"{name} must be an object")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise ProtocolError(f"{name} contains unsupported fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ProtocolError(f"{name} is missing fields: {', '.join(sorted(missing))}")
    return value


def _text(value: Any, name: str, maximum: int, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProtocolError(f"{name} must be a non-empty string of at most {maximum} characters")
    if pattern and not pattern.fullmatch(value):
        raise ProtocolError(f"{name} has an invalid format")
    return value


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ProtocolError(f"{name} must be an integer between {low} and {high}")
    return value


def _uuid(value: Any, name: str) -> str:
    try:
        return str(UUID(_text(value, name, 36)))
    except (ValueError, AttributeError):
        raise ProtocolError(f"{name} must be a UUID") from None


@dataclass(frozen=True)
class WorkerRegistration:
    worker_id: str
    engine_version: str
    protocol_version: str
    tasks: tuple[str, ...]
    models: tuple[tuple[str, str], ...]
    device: str
    vram_bytes: int | None
    ram_bytes: int

    @classmethod
    def from_dict(cls, value: Any) -> "WorkerRegistration":
        data = _mapping(value, "registration",
            {"worker_id", "engine_version", "protocol_version", "tasks", "models",
             "device", "vram_bytes", "ram_bytes"},
            {"worker_id", "engine_version", "protocol_version", "tasks", "models", "device", "ram_bytes"})
        worker_id = _text(data["worker_id"], "worker_id", 80)
        if not _WORKER_ID.fullmatch(worker_id):
            raise ProtocolError("worker_id must use the vydria- prefix")
        version = _text(data["protocol_version"], "protocol_version", 8)
        if version != PROTOCOL_VERSION:
            raise ProtocolError("unsupported worker protocol version")
        tasks = data["tasks"]
        if not isinstance(tasks, list) or not tasks or len(tasks) > len(TASKS):
            raise ProtocolError("tasks must be a non-empty list of supported tasks")
        if any(not isinstance(task, str) or task not in TASKS for task in tasks) or len(set(tasks)) != len(tasks):
            raise ProtocolError("tasks contains an unsupported or duplicate task")
        models = data["models"]
        if not isinstance(models, list) or not models or len(models) > 64:
            raise ProtocolError("models must contain between 1 and 64 exact model versions")
        normalized = []
        for item in models:
            model = _mapping(item, "model", {"id", "version"}, {"id", "version"})
            normalized.append((
                _text(model["id"], "model.id", 96, _MODEL_ID),
                _text(model["version"], "model.version", 64, _VERSION),
            ))
        if len(set(normalized)) != len(normalized):
            raise ProtocolError("models contains duplicate model versions")
        vram = data.get("vram_bytes")
        if vram is not None:
            vram = _integer(vram, "vram_bytes", 0, 2**63 - 1)
        return cls(
            worker_id=worker_id,
            engine_version=_text(data["engine_version"], "engine_version", 64),
            protocol_version=version,
            tasks=tuple(tasks),
            models=tuple(normalized),
            device=_text(data["device"], "device", 32),
            vram_bytes=vram,
            ram_bytes=_integer(data["ram_bytes"], "ram_bytes", 0, 2**63 - 1),
        )


@dataclass(frozen=True)
class JobEnvelope:
    job_id: str
    idempotency_key: str
    owner_id: str
    project_id: str
    task: str
    model_id: str
    model_version: str
    prompt: str
    width: int
    height: int
    frames: int
    fps: int
    seed: int | None
    input_asset_refs: tuple[str, ...]
    expires_at: int
    request_sha256: str
    protocol_version: str = PROTOCOL_VERSION

    @classmethod
    def from_dict(cls, value: Any, *, now: int | None = None) -> "JobEnvelope":
        allowed = {"job_id", "idempotency_key", "owner_id", "project_id", "task",
                   "model_id", "model_version", "prompt", "width", "height", "frames",
                   "fps", "seed", "input_asset_refs", "expires_at", "request_sha256",
                   "protocol_version"}
        required = allowed - {"seed", "input_asset_refs", "protocol_version"}
        data = _mapping(value, "job", allowed, required)
        protocol = _text(data.get("protocol_version", PROTOCOL_VERSION), "protocol_version", 8)
        if protocol != PROTOCOL_VERSION:
            raise ProtocolError("unsupported job protocol version")
        task = data["task"]
        if not isinstance(task, str) or task not in TASKS:
            raise ProtocolError("unsupported video task")
        model_id = _text(data["model_id"], "model_id", 96, _MODEL_ID)
        model_version = _text(data["model_version"], "model_version", 64, _VERSION)
        prompt = _text(data["prompt"], "prompt", 20000)
        refs = data.get("input_asset_refs", [])
        if not isinstance(refs, list) or len(refs) > 8:
            raise ProtocolError("input_asset_refs must be a list of at most 8 opaque references")
        normalized_refs = tuple(_text(ref, "input_asset_refs[]", 128, _OPAQUE_REF) for ref in refs)
        if any("/" in ref or "\\" in ref or "://" in ref for ref in normalized_refs):
            raise ProtocolError("input_asset_refs must be opaque IDs, not paths or URLs")
        if task == "video_image_to_video" and not normalized_refs:
            raise ProtocolError("video_image_to_video requires at least one input asset reference")
        seed = data.get("seed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or not -(2**63) <= seed < 2**63:
                raise ProtocolError("seed must be a signed 64-bit integer")
        digest = _text(data["request_sha256"], "request_sha256", 64, _SHA256)
        if digest != canonical_request_sha256(data):
            raise ProtocolError("request_sha256 does not match the canonical job request")
        expiry = _integer(data["expires_at"], "expires_at", 1, 2**63 - 1)
        current_time = int(time.time()) if now is None else _integer(now, "now", 0, 2**63 - 1)
        if expiry <= current_time:
            raise ProtocolError("job has expired")
        return cls(
            job_id=_uuid(data["job_id"], "job_id"),
            idempotency_key=_text(data["idempotency_key"], "idempotency_key", 128, _IDEMPOTENCY_KEY),
            owner_id=_uuid(data["owner_id"], "owner_id"),
            project_id=_uuid(data["project_id"], "project_id"),
            task=task,
            model_id=model_id,
            model_version=model_version,
            prompt=prompt,
            width=_integer(data["width"], "width", 64, 4096),
            height=_integer(data["height"], "height", 64, 4096),
            frames=_integer(data["frames"], "frames", 1, 4096),
            fps=_integer(data["fps"], "fps", 1, 120),
            seed=seed,
            input_asset_refs=normalized_refs,
            expires_at=expiry,
            request_sha256=digest,
            protocol_version=protocol,
        )


@dataclass(frozen=True)
class ProgressEvent:
    job_id: str
    sequence: int
    stage: str
    progress: int
    message: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> "ProgressEvent":
        data = _mapping(value, "progress", {"job_id", "sequence", "stage", "progress", "message"},
                        {"job_id", "sequence", "stage", "progress"})
        stage = data["stage"]
        if not isinstance(stage, str) or stage not in PROGRESS_STAGES:
            raise ProtocolError("unsupported progress stage")
        return cls(
            job_id=_uuid(data["job_id"], "job_id"),
            sequence=_integer(data["sequence"], "sequence", 1, 2**31 - 1),
            stage=stage,
            progress=_integer(data["progress"], "progress", 0, 100),
            message="" if data.get("message") is None else _text(data["message"], "message", 500),
        )


class ProgressSequenceTracker:
    """Thread-safe per-job guard for strictly increasing sequence and progress."""

    def __init__(self) -> None:
        self._last: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    def accept(self, value: Any) -> ProgressEvent:
        event = ProgressEvent.from_dict(value)
        with self._lock:
            previous = self._last.get(event.job_id)
            if previous is not None:
                last_sequence, last_progress = previous
                if event.sequence <= last_sequence:
                    raise ProtocolError("progress sequence must increase for each job")
                if event.progress < last_progress:
                    raise ProtocolError("progress percentage must not decrease for a job")
            self._last[event.job_id] = (event.sequence, event.progress)
        return event

    def forget(self, job_id: str) -> None:
        """Release sequence state after the owning job reaches a terminal state."""
        normalized = _uuid(job_id, "job_id")
        with self._lock:
            self._last.pop(normalized, None)


@dataclass(frozen=True)
class JobCompletion:
    job_id: str
    status: str
    output_asset_refs: tuple[str, ...]
    error_code: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "JobCompletion":
        data = _mapping(value, "completion", {"job_id", "status", "output_asset_refs", "error_code"},
                        {"job_id", "status", "output_asset_refs"})
        status = data["status"]
        if not isinstance(status, str) or status not in {"succeeded", "failed", "cancelled"}:
            raise ProtocolError("completion status must be terminal")
        refs = data["output_asset_refs"]
        if not isinstance(refs, list) or len(refs) > 8:
            raise ProtocolError("output_asset_refs must be a list of at most 8 opaque references")
        normalized = tuple(_text(ref, "output_asset_refs[]", 128, _OPAQUE_REF) for ref in refs)
        if any("/" in ref or "\\" in ref or "://" in ref for ref in normalized):
            raise ProtocolError("output_asset_refs must be opaque IDs, not paths or URLs")
        if status == "succeeded" and not normalized:
            raise ProtocolError("successful completion requires at least one output asset")
        error = data.get("error_code")
        if error is not None:
            error = _text(error, "error_code", 64, re.compile(r"^[a-z0-9_]+$"))
        if status != "succeeded" and not error:
            raise ProtocolError("failed or cancelled completion requires an error_code")
        return cls(job_id=_uuid(data["job_id"], "job_id"), status=status,
                   output_asset_refs=normalized, error_code=error)
