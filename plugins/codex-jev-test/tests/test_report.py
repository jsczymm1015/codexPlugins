import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/test-with-jev/scripts"))
import jev_test as core
import render_report as report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data = {"requirements": [{"id": "R1", "text": "Only one record"}], "cases": [
            {"id": "C1", "requirement_ids": ["R1"], "scenario": "Repeat", "expected": "one", "observed": "two",
             "status": "failed", "evidence": ["actual=2"]}], "runs": []}
        self.notes = {"title": "功能验证", "context": "本轮执行隔离测试", "requirements": {"R1": "只允许一条记录"},
            "cases": {"C1": {"scenario": "重复提交", "expected": "一条记录", "observed": "两条记录",
                "evidence_summary": "实际计数断言失败", "cause": "原因待确认", "impact": "可能重复下单", "action": "检查幂等条件"}}}

    def review(self):
        payload, mapping = core.build_request(self.data, "fixture")
        answers = {q: {"type": "choice", "choice": next(iter(v["criteria"])), "confidence": 0.9,
                      "probabilities": {k: int(k == next(iter(v["criteria"]))) for k in v["criteria"]}}
                   for q, v in payload["questions"].items()}
        normalized = core.validate_response({"model": "fixture", "answers": answers,
                "usage": {"input_tokens": 1, "output_tokens": 1}}, payload, mapping)
        return {"jev_status": "completed", **core.execution_summary(self.data), **normalized,
                "evidence_sha256": hashlib.sha256(json.dumps(core.redact(self.data), sort_keys=True, ensure_ascii=False).encode()).hexdigest()}

    def test_model_covered_does_not_override_failure(self):
        text = report.render(self.data, self.review(), self.notes)
        self.assertIn("未通过", text)
        self.assertIn("不代表通过", text)
        self.assertIn("业务代码实现问题", text)
        self.assertNotIn("actual=2", text)

    def test_offline_does_not_claim_jev_ran(self):
        text = report.render(self.data, None, self.notes)
        self.assertIn("未提供本轮有效评估", text)
        self.assertIn("原因待确认", text)

    def test_stale_evidence_rejected(self):
        review = self.review()
        self.data["cases"][0]["observed"] = "new result"
        with self.assertRaises(core.ReviewError):
            report.render(self.data, review, self.notes)

    def test_tampered_counts_rejected(self):
        review = self.review()
        review["case_counts"] = {"passed": 1}
        with self.assertRaises(core.ReviewError):
            report.render(self.data, review, self.notes)

    def test_unknown_ids_and_status_override_in_notes_rejected(self):
        for change in [lambda n: n["cases"].update(C2=n["cases"]["C1"]),
                       lambda n: n["cases"]["C1"].update(status="passed"),
                       lambda n: n["cases"]["C1"].pop("cause")]:
            notes = copy.deepcopy(self.notes)
            change(notes)
            with self.assertRaises(core.ReviewError):
                report.render(self.data, None, notes)

    def test_missing_translation_rejected(self):
        self.notes["cases"]["C1"]["scenario"] = "English-only result"
        with self.assertRaises(core.ReviewError):
            report.render(self.data, None, self.notes)

    def test_html_and_table_pipes_escaped(self):
        self.notes["cases"]["C1"]["observed"] = "结果<script>bad()</script>|下一列\n第二行"
        text = report.render(self.data, None, self.notes)
        self.assertNotIn("<script>", text)
        self.assertIn("&#124;下一列<br>第二行", text)

    def test_not_run_is_not_counted_as_executed(self):
        self.data["cases"][0]["status"] = "not_run"
        text = report.render(self.data, None, self.notes)
        self.assertIn("| 已执行 | 0 |", text)
        self.assertIn("| 未完成 | 1 |", text)
        self.assertIn("尚未执行", text)

    def test_false_requires_review_flag_is_recomputed(self):
        review = self.review()
        review["reviews"][0]["confidence"] = 0.2
        review["reviews"][0]["requires_review"] = False
        self.assertIn("20%；需复核", report.render(self.data, review, self.notes))

    def test_error_and_skipped_remain_distinct(self):
        for status, expected in [("error", "执行异常"), ("skipped", "已跳过")]:
            self.data["cases"][0]["status"] = status
            text = report.render(self.data, None, self.notes)
            self.assertIn("C1／" + expected, text)


if __name__ == "__main__":
    unittest.main()
