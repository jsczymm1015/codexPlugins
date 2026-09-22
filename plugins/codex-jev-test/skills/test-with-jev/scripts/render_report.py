#!/usr/bin/env python3
"""Render evidence and optional Jev review into a Chinese Markdown table report, offline."""
import argparse
from collections import Counter
import hashlib
import html
import json
import os
import re
import sys

import jev_test as core

STATUS = {"passed": "通过", "failed": "失败", "error": "执行异常", "skipped": "已跳过", "not_run": "尚未执行"}
COVERAGE = {"covered": "案例设计已覆盖（不代表通过）", "partial": "仅部分覆盖", "missing": "缺少覆盖", "insufficient": "材料不足，无法判断"}
FAILURE = {"implementation": "业务代码实现问题", "test": "测试代码或断言问题", "environment": "运行环境问题", "data": "测试数据问题", "unknown": "原因尚不明确"}


def cell(value):
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\r", "").replace("\n", "<br>").replace("`", "&#96;")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows]) + "\n"


def chinese(value):
    core.require(isinstance(value, str) and 0 < len(value) <= 1200 and re.search(r"[\u4e00-\u9fff]", value),
                 "Report notes must contain concise Chinese explanations, up to 1200 characters each")


def validate_notes(notes, evidence):
    core.fields(notes, ["title", "context", "requirements", "cases"], ["title", "context", "requirements", "cases"], "notes")
    chinese(notes["title"])
    chinese(notes["context"])
    for key in ["requirements", "cases"]:
        core.require(isinstance(notes[key], dict) and set(notes[key]) == {x["id"] for x in evidence[key]},
                     "Notes IDs must exactly match evidence " + key)
    for value in notes["requirements"].values():
        chinese(value)
    for case in evidence["cases"]:
        note = notes["cases"][case["id"]]
        core.fields(note, ["scenario", "expected", "observed", "cause", "impact", "action", "evidence_summary"],
                    ["scenario", "expected", "observed", "evidence_summary"], "case notes")
        if case["status"] in {"failed", "error"}:
            core.require(all(k in note for k in ["cause", "impact", "action"]), "Failed cases require cause, impact and action notes")
        if case["status"] in {"skipped", "not_run"}:
            core.require("action" in note, "Unexecuted cases require next action notes")
        for value in note.values():
            chinese(value)


def checked_reviews(evidence, review):
    if review is None:
        return {}, "未提供本轮有效评估；本报告仅汇总本地证据"
    core.require(isinstance(review, dict) and review.get("jev_status") == "completed", "Supply a completed Jev review or omit --review")
    digest = hashlib.sha256(json.dumps(core.redact(evidence), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    core.require(review.get("evidence_sha256") == digest, "Evidence hash mismatch: review belongs to different input")
    summary = core.execution_summary(evidence)
    core.require(all(review.get(k) == summary[k] for k in ["case_counts", "case_results", "execution_status"]),
                 "Review execution results do not match evidence")
    payload, mapping = core.build_request(evidence, review.get("model", ""))
    entries = review.get("reviews")
    core.require(isinstance(entries, list), "Invalid review entries")
    lookup = {}
    for item in entries:
        core.require(isinstance(item, dict) and isinstance(item.get("kind"), str) and isinstance(item.get("id"), str), "Invalid review item")
        key = (item["kind"], item["id"])
        core.require(key not in lookup, "Duplicate review item")
        lookup[key] = item
    core.require(set(lookup) == {(m["kind"], m["id"]) for m in mapping.values()}, "Missing or extra review items")
    answers = {}
    for qid, item in mapping.items():
        entry = lookup[(item["kind"], item["id"])]
        answers[qid] = {"type": "choice", **{k: entry.get(k) for k in ["choice", "confidence", "probabilities"]}}
    normalized = core.validate_response({"model": review["model"], "usage": review.get("usage"), "answers": answers}, payload, mapping)
    return {(e["kind"], e["id"]): e for e in normalized["reviews"]}, "已完成，模型 " + review["model"]


def judgment(item, labels):
    if not item:
        return "未评估"
    suffix = "；需复核" if item["requires_review"] else "；辅助判断"
    return labels[item["choice"]] + "；置信度 " + format(item["confidence"], ".0%") + suffix


def render(evidence, review, notes):
    core.validate_evidence(evidence)
    validate_notes(notes, evidence)
    reviews, jev_status = checked_reviews(evidence, review)
    counts = Counter(c["status"] for c in evidence["cases"])
    execution = core.execution_summary(evidence)["execution_status"]
    verdict = {"failed": "未通过：存在失败用例或执行异常", "incomplete": "验证未完成：存在未执行、跳过或缺少用例",
               "reported_passed": "已执行用例通过；不等于全部需求验收通过"}[execution]
    output = ["# " + cell(notes["title"]), cell(notes["context"]), "## 一、结果总览",
              table(["项目", "结果", "如何理解"], [
                  ["本地验证结论", verdict, "由原始状态和命令退出码计算，Jev不能覆盖此结论"],
                  ["案例总数", len(evidence["cases"]), "通过/失败/异常属于已执行；跳过/尚未执行单独统计"],
                  ["已执行", sum(counts[s] for s in ["passed", "failed", "error"]),
                   f"通过 {counts['passed']}；失败 {counts['failed']}；异常 {counts['error']}"],
                  ["未完成", counts["skipped"] + counts["not_run"], f"已跳过 {counts['skipped']}；尚未执行 {counts['not_run']}"],
                  ["Jev评估", jev_status, "模型辅助判断，不是新增测试；置信度不等于正确率"]])]
    requirements = []
    for req in evidence["requirements"]:
        cases = [c for c in evidence["cases"] if req["id"] in c["requirement_ids"]]
        local = Counter(c["status"] for c in cases)
        status = "已关联用例通过，仍需确认覆盖充分"
        if local["failed"] or local["error"]:
            status = "未通过"
        elif not cases or local["not_run"] or local["skipped"]:
            status = "未验证完整"
        requirements.append([req["id"], notes["requirements"][req["id"]], status,
            "；".join(f"{STATUS[s]} {local[s]}" for s in STATUS if local[s]) or "没有关联用例",
            judgment(reviews.get(("coverage", req["id"])), COVERAGE)])
    output += ["## 二、需求逐项结论", table(["编号", "需求说明", "本地结论", "用例统计", "Jev覆盖提示"], requirements),
               "同一案例可以关联多条需求，本表各行数量不能相加作为总测试数。", "## 三、全部测试明细"]
    output.append(table(["编号／结果", "测试场景", "预期应该怎样", "实际发生什么", "证据说明"], [
        [c["id"] + "／" + STATUS[c["status"]], notes["cases"][c["id"]]["scenario"],
         notes["cases"][c["id"]]["expected"], notes["cases"][c["id"]]["observed"],
         notes["cases"][c["id"]]["evidence_summary"]] for c in evidence["cases"]]))
    output.append("## 四、问题原因与处理建议")
    failures = [c for c in evidence["cases"] if c["status"] in {"failed", "error"}]
    if not failures:
        output.append("当前材料没有失败或异常案例；这不表示不存在未覆盖问题。")
    for c in failures:
        note = notes["cases"][c["id"]]
        output += ["### " + cell(c["id"] + "：" + note["scenario"]), table(["项目", "说明"], [
            ["实际结果", note["observed"]], ["原因（Codex复核／推断）", note["cause"]],
            ["业务影响（Codex分析）", note["impact"]], ["建议下一步，尚未执行", note["action"]],
            ["Jev失败分类", judgment(reviews.get(("failure", c["id"])), FAILURE)]])]
    pending = [c for c in evidence["cases"] if c["status"] in {"not_run", "skipped"}]
    output += ["## 五、尚未验证与后续行动", table(["编号", "当前状态／限制", "下一步"], [
        [c["id"], notes["cases"][c["id"]]["observed"], notes["cases"][c["id"]]["action"]] for c in pending])
        if pending else "输入未列出未执行案例；仍应核对环境与覆盖边界。",
        "## 六、判读说明", table(["术语", "中文含义"], [
            ["通过", "给定场景的实际断言通过；不能外推到其他场景"],
            ["设计覆盖", "Jev认为案例描述涉及需求，不表示案例已执行或断言通过"],
            ["需复核", "分类置信度较低，或材料/覆盖不足，应回到代码和证据确认"],
            ["建议下一步", "Codex给出的处理建议，不表示代码已修复或测试已补跑"],
            ["报告来源", "数字与状态来自原始证据；中文归纳及影响说明由Codex整理，Jev提供结构化分类"]])]
    return "\n\n".join(output) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--review")
    parser.add_argument("--notes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = core.load_json(args.input)
        review = core.load_json(args.review) if args.review else None
        notes = core.redact(core.load_json(args.notes))
        report = render(evidence, review, notes)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(report)
        print("中文表格报告已生成；未联网，未重新执行测试。")
        return 0
    except (core.ReviewError, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, core.ReviewError) else "无法读写报告文件；检查输入及输出是否已存在", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
