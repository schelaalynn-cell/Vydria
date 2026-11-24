import unittest
from uuid import uuid4

from vydria_worker.protocol import (
    JobCompletion,
    JobEnvelope,
    ProgressEvent,
    ProgressSequenceTracker,
    ProtocolError,
    WorkerRegistration,
    canonical_request_sha256,
)


class WorkerProtocolTests(unittest.TestCase):
    def registration(self):
        return {
            "worker_id": "vydria-test-worker-01",
            "engine_version": "0.1.0",
            "protocol_version": "1",
            "tasks": ["video_text_to_video", "video_image_to_video"],
            "models": [{"id": "vdn-h3", "version": "stage-dmd-step-250"}],
            "device": "cuda",
            "vram_bytes": 24 * 1024**3,
            "ram_bytes": 64 * 1024**3,
        }

    def job(self, **overrides):
        value = {
            "job_id": str(uuid4()),
            "idempotency_key": "job-key-0001",
            "owner_id": str(uuid4()),
            "project_id": str(uuid4()),
            "task": "video_text_to_video",
            "model_id": "vdn-h3",
            "model_version": "stage-dmd-step-250",
            "prompt": "A cinematic aerial view of a coastal city at sunrise",
            "width": 1344,
            "height": 768,
            "frames": 345,
            "fps": 24,
            "input_asset_refs": [],
            "expires_at": 2_000_000_000,
            "request_sha256": "a" * 64,
        }
        value.update(overrides)
        value["request_sha256"] = canonical_request_sha256(value)
        return value

    def test_registration_accepts_exact_model_versions(self):
        result = WorkerRegistration.from_dict(self.registration())
        self.assertEqual(result.models, (("vdn-h3", "stage-dmd-step-250"),))
        self.assertEqual(result.protocol_version, "1")

    def test_registration_rejects_unknown_task_and_secret_fields(self):
        with self.assertRaises(ProtocolError):
            WorkerRegistration.from_dict({**self.registration(), "tasks": ["shell"]})
        with self.assertRaises(ProtocolError):
            WorkerRegistration.from_dict({**self.registration(), "zyvano_user_token": "secret"})

    def test_job_accepts_opaque_asset_references(self):
        result = JobEnvelope.from_dict(self.job(
            task="video_image_to_video", input_asset_refs=["asset_01HZX8J8W2M3"]
        ))
        self.assertEqual(result.input_asset_refs, ("asset_01HZX8J8W2M3",))

    def test_job_rejects_paths_urls_and_raw_input_paths(self):
        for ref in ("/etc/passwd", "../private.mp4", "https://example.test/file.png"):
            with self.subTest(ref=ref), self.assertRaises(ProtocolError):
                JobEnvelope.from_dict(self.job(
                    task="video_image_to_video", input_asset_refs=[ref]
                ))
        with self.assertRaises(ProtocolError):
            JobEnvelope.from_dict({**self.job(), "input_paths": ["/tmp/input.png"]})

    def test_job_requires_exact_model_version_and_bounded_dimensions(self):
        with self.assertRaises(ProtocolError):
            JobEnvelope.from_dict(self.job(model_version=""))
        with self.assertRaises(ProtocolError):
            JobEnvelope.from_dict(self.job(width=16384))

    def test_job_rejects_expired_requests(self):
        value = self.job(expires_at=999)
        with self.assertRaisesRegex(ProtocolError, "expired"):
            JobEnvelope.from_dict(value, now=1000)
        self.assertEqual(JobEnvelope.from_dict(self.job(expires_at=1001), now=1000).expires_at, 1001)

    def test_job_rejects_tampered_request_digest(self):
        value = self.job()
        value["width"] = 1920
        with self.assertRaisesRegex(ProtocolError, "request_sha256"):
            JobEnvelope.from_dict(value)

    def test_job_rejects_malformed_idempotency_keys(self):
        for key in ("", "contains spaces", "../unsafe"):
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                JobEnvelope.from_dict(self.job(idempotency_key=key))

    def test_progress_is_bounded_and_typed(self):
        result = ProgressEvent.from_dict({
            "job_id": str(uuid4()), "sequence": 1, "stage": "inference", "progress": 45
        })
        self.assertEqual(result.progress, 45)
        with self.assertRaises(ProtocolError):
            ProgressEvent.from_dict({
                "job_id": str(uuid4()), "sequence": 0, "stage": "inference", "progress": 101
            })

    def test_progress_tracker_rejects_replay_reordering_and_regression(self):
        tracker = ProgressSequenceTracker()
        job_id = str(uuid4())
        first = {"job_id": job_id, "sequence": 1, "stage": "accepted", "progress": 5}
        second = {"job_id": job_id, "sequence": 2, "stage": "inference", "progress": 45}
        tracker.accept(first)
        tracker.accept(second)
        with self.assertRaisesRegex(ProtocolError, "sequence"):
            tracker.accept(second)
        with self.assertRaisesRegex(ProtocolError, "sequence"):
            tracker.accept({**first, "sequence": 1, "progress": 50})
        with self.assertRaisesRegex(ProtocolError, "must not decrease"):
            tracker.accept({"job_id": job_id, "sequence": 3, "stage": "decoding", "progress": 40})
        tracker.forget(job_id)
        self.assertEqual(tracker.accept(first).sequence, 1)

    def test_completion_requires_opaque_output_reference(self):
        result = JobCompletion.from_dict({
            "job_id": str(uuid4()), "status": "succeeded", "output_asset_refs": ["asset_output_1"]
        })
        self.assertEqual(result.status, "succeeded")
        with self.assertRaises(ProtocolError):
            JobCompletion.from_dict({
                "job_id": str(uuid4()), "status": "succeeded", "output_asset_refs": ["/tmp/out.mp4"]
            })
        with self.assertRaises(ProtocolError):
            JobCompletion.from_dict({
                "job_id": str(uuid4()), "status": "failed", "output_asset_refs": []
            })


if __name__ == "__main__":
    unittest.main()
