import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / "skills/test-with-jev/scripts/jev_test.py"
spec = importlib.util.spec_from_file_location("jev_test", SCRIPT)
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


def evidence(status="failed"):
    return {"requirements": [{"id": "R1", "text": "Duplicate submission creates one record"}],
            "cases": [{"id": "C1", "requirement_ids": ["R1"], "scenario": "Submit same request twice",
                       "expected": "One record", "observed": "Two records", "status": status,
                       "evidence": ["Fresh isolated test: expected 1 but got 2"]}],
            "runs": [{"command": "project-test", "exit_code": 1 if status == "failed" else 0}]}


def response(payload):
    answers = {}
    for name, question in payload["questions"].items():
        choice = next(iter(question["criteria"]))
        answers[name] = {"type": "choice", "choice": choice, "confidence": 0.9,
                         "probabilities": {k: int(k == choice) for k in question["criteria"]}}
    return {"model": "jev-contract-fixture", "answers": answers,
            "usage": {"input_tokens": 100, "output_tokens": 20}}


class EvidenceTests(unittest.TestCase):
    def test_bad_schemas_rejected(self):
        transforms = [lambda d: d.update(secret="never upload"),
                      lambda d: d["requirements"].append(d["requirements"][0]),
                      lambda d: d["cases"][0].update(requirement_ids=["missing"]),
                      lambda d: d["cases"][0].update(status="probably_passed"),
                      lambda d: d["cases"][0].update(evidence=[]),
                      lambda d: d["runs"][0].update(exit_code=True),
                      lambda d: d["cases"][0].update(status={}),
                      lambda d: d.update(cases=d["cases"] * 101)]
        for change in transforms:
            with self.subTest(change=change):
                data = evidence()
                change(data)
                with self.assertRaises(jev.ReviewError):
                    jev.validate_evidence(data)

    def test_pass_skip_failure_and_nonzero_are_distinct(self):
        for case_status, expected in [("failed", "failed"), ("error", "failed"),
                                      ("passed", "reported_passed"), ("skipped", "incomplete"),
                                      ("not_run", "incomplete")]:
            with self.subTest(case_status=case_status):
                self.assertEqual(jev.execution_summary(evidence(case_status))["execution_status"], expected)
        data = evidence("passed")
        data["runs"][0]["exit_code"] = 1
        self.assertEqual(jev.execution_summary(data)["execution_status"], "failed")
        data["runs"] = []
        data["cases"] = []
        self.assertEqual(jev.execution_summary(data)["execution_status"], "incomplete")

    def test_bound_request_and_no_silent_truncation(self):
        data = evidence()
        data["cases"][0]["observed"] = "测" * 8000
        data["cases"][0]["expected"] = "测" * 8000
        data["cases"][0]["scenario"] = "测" * 8000
        with self.assertRaises(jev.ReviewError):
            jev.build_request(data, "jev-latest")

    def test_redaction(self):
        raw = {"evidence": ["password=abc123 api_key='hidden-value' Bearer abc.def",
                            "person@example.com", "literal-example-credential",
                            "-----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----"]}
        cleaned = str(jev.redact(raw, "literal-example-credential"))
        for secret in ["abc123", "hidden-value", "abc.def", "person@example.com", "literal-example-credential", "\nprivate\n"]:
            self.assertNotIn(secret, cleaned)

    def test_questions_are_atomic_and_include_case_paths(self):
        payload, mapping = jev.build_request(evidence(), "jev-latest")
        self.assertEqual(set(payload), {"state", "model", "questions"})
        self.assertEqual(len(mapping), 2)
        self.assertIn("requirements[0].text", payload["questions"]["coverage_0"]["instructions"])
        self.assertIn("cases[0]", payload["questions"]["failure_0"]["instructions"])
        self.assertIn("unknown", payload["questions"]["failure_0"]["criteria"])


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.payload, self.mapping = jev.build_request(evidence(), "jev-latest")

    def test_low_confidence_and_unknown_require_review(self):
        res = response(self.payload)
        res["answers"]["coverage_0"]["confidence"] = 0.2
        a = res["answers"]["failure_0"]
        a.update(choice="unknown", probabilities={k: int(k == "unknown") for k in jev.FAILURES})
        output = jev.validate_response(res, self.payload, self.mapping)
        self.assertTrue(all(item["requires_review"] for item in output["reviews"]))

    def test_bad_answers_fail_closed(self):
        transforms = [lambda r: r["answers"].pop("coverage_0"),
                      lambda r: r["answers"]["coverage_0"].update(choice="anything"),
                      lambda r: r["answers"]["coverage_0"].update(confidence=float("nan")),
                      lambda r: r["answers"]["coverage_0"].update(confidence=True),
                      lambda r: r["answers"]["coverage_0"].update(type="noul"),
                      lambda r: r["answers"]["coverage_0"].update(probabilities={"covered": 1}),
                      lambda r: r["answers"]["coverage_0"]["probabilities"].update(covered=0.3),
                      lambda r: r["answers"]["coverage_0"].update(choice="missing"),
                      lambda r: r.update(usage={}),
                      lambda r: r.update(model="")]
        for change in transforms:
            with self.subTest(change=change):
                res = response(self.payload)
                change(res)
                with self.assertRaises(jev.ReviewError):
                    jev.validate_response(res, self.payload, self.mapping)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.payload, _ = jev.build_request(evidence(), "jev-latest")

    def test_official_contract_and_timeout(self):
        client = Mock()
        client.open.return_value = io.BytesIO(json.dumps(response(self.payload)).encode())
        answer = jev.call_jev(self.payload, "test-fixture-key", client)
        request = client.open.call_args.args[0]
        self.assertEqual(request.full_url, jev.ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer test-fixture-key")
        self.assertEqual(json.loads(request.data), self.payload)
        self.assertEqual(client.open.call_args.kwargs["timeout"], 20)
        self.assertEqual(answer["model"], "jev-contract-fixture")

    def test_429_then_success(self):
        client = Mock()
        client.open.side_effect = [urllib.error.HTTPError(jev.ENDPOINT, 429, "rate", {}, None),
                                   io.BytesIO(json.dumps(response(self.payload)).encode())]
        sleeper = Mock()
        jev.call_jev(self.payload, "fixture", client, sleeper)
        self.assertEqual(client.open.call_count, 2)
        sleeper.assert_called_once_with(1)

    def test_retry_limits_and_errors_do_not_leak(self):
        for code, calls in [(401, 1), (422, 1), (302, 1), (529, 3), (503, 3)]:
            with self.subTest(code=code):
                client = Mock()
                client.open.side_effect = urllib.error.HTTPError(jev.ENDPOINT, code, "secret-body", {}, None)
                with self.assertRaises(jev.ReviewError) as error:
                    jev.call_jev(self.payload, "fixture", client, Mock())
                self.assertNotIn("secret-body", str(error.exception))
                self.assertEqual(client.open.call_count, calls)

    def test_timeout_is_bounded(self):
        client = Mock()
        client.open.side_effect = TimeoutError("secret")
        with self.assertRaises(jev.ReviewError):
            jev.call_jev(self.payload, "fixture", client, Mock())
        self.assertEqual(client.open.call_count, 3)

    def test_redirect_refused(self):
        self.assertIsNone(jev.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))

    def test_invalid_and_oversized_json(self):
        for content in [b"not-json", b'{"a": NaN}', b"x" * (jev.MAX_RESPONSE + 1)]:
            with self.subTest(size=len(content)):
                client = Mock()
                client.open.return_value = io.BytesIO(content)
                with self.assertRaises(jev.ReviewError):
                    jev.call_jev(self.payload, "fixture", client)

    def test_missing_key_never_calls_network(self):
        client = Mock()
        with self.assertRaises(jev.MissingKey):
            jev.call_jev(self.payload, "", client)
        client.open.assert_not_called()


class LocalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"JEV_API_KEY_FILE": str(self.root / "absent")}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_environment_and_file_key_precedence(self):
        path = self.root / "credential"
        jev.emit("not-a-real-key", path)
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "primary", "JEV_API_KEY": "secondary", "JEV_API_KEY_FILE": str(path)}):
            self.assertEqual(jev.load_key(), ("primary", "TYPESAFE_API_KEY"))
        self.assertEqual(jev.load_key(), ("", "not_configured"))

    @unittest.skipUnless(os.name == "posix", "POSIX permission check")
    def test_loose_credential_permissions_rejected(self):
        path = self.root / "credential"
        path.write_text("fixture")
        path.chmod(0o644)
        with patch.dict(os.environ, {"JEV_API_KEY_FILE": str(path)}):
            with self.assertRaises(jev.ReviewError):
                jev.load_key()

    def test_configure_hides_key_and_refuses_overwrite(self):
        with patch.object(sys.stdin, "isatty", return_value=True), patch.object(jev.getpass, "getpass", return_value="fixture-key"):
            result = jev.configure()
            self.assertNotIn("fixture-key", str(result))
            self.assertEqual(jev.load_key(), ("fixture-key", "credential_file"))
            with self.assertRaises(jev.ReviewError):
                jev.configure()

    def test_doctor_outputs_no_secret(self):
        out = io.StringIO()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "hidden-fixture"}), contextlib.redirect_stdout(out):
            self.assertEqual(jev.main(["doctor"]), 0)
        self.assertNotIn("hidden-fixture", out.getvalue())

    def test_junit_collects_only_explicit_case_metadata(self):
        path = self.root / "report.xml"
        path.write_text('<testsuites><testsuite><testcase name="one"/><testcase name="two"><failure>PRIVATE</failure></testcase>'
                        '<testcase name="three"><error/></testcase><testcase name="four"><skipped/></testcase>'
                        '<system-out>password=PRIVATE</system-out></testsuite></testsuites>')
        collected = jev.collect_junit([path])
        self.assertEqual([c["status"] for c in collected["template"]["cases"]], ["passed", "failed", "error", "skipped"])
        self.assertNotIn("PRIVATE", str(collected))
        self.assertEqual(len(collected["sources"][0]["sha256"]), 64)

    def test_junit_rejects_entities_and_no_cases(self):
        path = self.root / "report.xml"
        for xml in ['<!DOCTYPE a [<!ENTITY x "secret">]><testsuite/>', '<testsuite tests="5"/>', '<html/>']:
            with self.subTest(xml=xml):
                path.write_text(xml)
                with self.assertRaises(jev.ReviewError):
                    jev.collect_junit([path])

    def test_cli_dry_run_and_missing_key(self):
        path = self.root / "evidence.json"
        path.write_text(json.dumps(evidence()))
        args = [sys.executable, str(SCRIPT), "analyze", "--input", str(path)]
        result = subprocess.run(args + ["--dry-run"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["jev_status"], "not_called")
        self.assertEqual(output["execution_status"], "failed")
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["jev_status"], "not_called")

    def test_cli_mocked_live_preserves_test_failure(self):
        path = self.root / "evidence.json"
        path.write_text(json.dumps(evidence()))
        payload, _ = jev.build_request(evidence(), "jev-latest")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "fixture"}), patch.object(jev, "call_jev", return_value=response(payload)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(jev.main(["analyze", "--input", str(path)]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["jev_status"], "completed")
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual(result["reviews"][0]["choice"], "covered")

    def test_existing_output_not_overwritten(self):
        path = self.root / "report.json"
        path.write_text("original")
        with self.assertRaises(FileExistsError):
            jev.emit({"new": True}, path)
        self.assertEqual(path.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
