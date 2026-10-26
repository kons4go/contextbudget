"""contextbudget —— 给上下文算账，看预算花在哪。

设计原则：
1. **归因，不是建议**。超预算就说清楚是哪一段吃掉的，不笼统地说「建议精简」。
2. **估算就标明是估算**。token 数依赖具体分词器，这里给的是量级估计。
3. **不自动压缩**。压缩是另一件事，本工具只负责把账摊开。

仅依赖 Python 标准库。

用法:
    python contextbudget.py --help
    python contextbudget.py --file context.txt --budget 4000
    python contextbudget.py --file context.txt --budget 4000 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# token 估算
# ---------------------------------------------------------------------------

# 拉丁文：一个 token 大约 4 个字符
# 中文：一个汉字大约 1 个 token（偏保守，宁可高估）
CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯]")
WORD_RE = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9一-鿿]")


def estimate_tokens(text: str) -> int:
    """估算一段文本的 token 数。

    这是**量级估计**，不是精确计数——真实值取决于模型的分词器。
    规则：CJK 字符按 1 个 token 算，其余按 4 字符 1 token 算。
    """
    if not text:
        return 0
    cjk = len(CJK_RE.findall(text))
    rest = len(text) - cjk
    return cjk + max(1, round(rest / 4)) if rest else cjk


# ---------------------------------------------------------------------------
# 片段切分
# ---------------------------------------------------------------------------

# 按 markdown 标题切；没有标题就按空行段落切。
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def split_segments(text: str) -> list[dict]:
    """把上下文切成片段，每段带标题与层级。"""
    segments: list[dict] = []
    cur = {"title": "(开头)", "level": 0, "lines": []}

    for raw in text.splitlines():
        m = HEADING_RE.match(raw)
        if m:
            if cur["lines"] and any(l.strip() for l in cur["lines"]):
                segments.append(cur)
            cur = {"title": m.group(2).strip(), "level": len(m.group(1)), "lines": []}
        else:
            cur["lines"].append(raw)

    if cur["lines"] and any(l.strip() for l in cur["lines"]):
        segments.append(cur)

    out: list[dict] = []
    for seg in segments:
        body = "\n".join(seg["lines"])
        if not body.strip():
            continue
        out.append({
            "title": seg["title"],
            "level": seg["level"],
            "chars": len(body),
            "tokens": estimate_tokens(body),
            "text": body,
        })
    return out


# ---------------------------------------------------------------------------
# 分析
# ---------------------------------------------------------------------------

# 可裁剪候选的识别：明显是低价值内容
TRIM_SIGNALS = [
    (re.compile(r"^```", re.M), "代码块"),
    (re.compile(r"^\s*[>|].*", re.M), "引用/日志"),
    (re.compile(r"^\s*[-*]\s", re.M), "长列表"),
    (re.compile(r"^\s*\|.*\|\s*$", re.M), "表格"),
]


def trim_candidates(seg: dict) -> list[str]:
    """列出这个片段里可能的可裁剪部分。"""
    reasons: list[str] = []
    for pattern, label in TRIM_SIGNALS:
        if pattern.search(seg["text"]):
            reasons.append(label)
    return reasons


def analyze(text: str, budget: int) -> dict:
    """给上下文算账。"""
    segments = split_segments(text)
    total_tokens = sum(s["tokens"] for s in segments)
    total_chars = sum(s["chars"] for s in segments)

    rows = []
    for i, seg in enumerate(segments):
        share = (seg["tokens"] / total_tokens) if total_tokens else 0.0
        rows.append({
            "index": i,
            "title": seg["title"],
            "level": seg["level"],
            "tokens": seg["tokens"],
            "chars": seg["chars"],
            "share": round(share, 4),
            "over_budget_alone": seg["tokens"] > budget,
            "trim_candidates": trim_candidates(seg),
        })

    # 按占用排序，找出最该先看的
    ranked = sorted(rows, key=lambda r: -r["tokens"])

    # 单段超预算
    oversize = [r for r in rows if r["over_budget_alone"]]

    # 可裁剪部分总量估计
    trimmable_tokens = 0
    for seg in segments:
        if trim_candidates(seg):
            # 保守估计：这类片段的一半可裁
            trimmable_tokens += seg["tokens"] // 2

    return {
        "budget": budget,
        "total_tokens": total_tokens,
        "total_chars": total_chars,
        "over_budget": total_tokens > budget,
        "overage": max(0, total_tokens - budget),
        "usage_ratio": round(total_tokens / budget, 4) if budget else None,
        "segments": rows,
        "ranked_by_size": ranked[:10],
        "oversize_segments": [r["title"] for r in oversize],
        "trimmable_estimate": trimmable_tokens,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(result: dict) -> str:
    out: list[str] = []
    b = result["budget"]
    out.append("上下文预算账单")
    out.append("=" * 56)
    out.append(f"预算      {b} tokens")
    out.append(f"实际占用  {result['total_tokens']} tokens "
               f"（{result['total_chars']} 字符）")
    if result["usage_ratio"] is not None:
        out.append(f"占用率    {result['usage_ratio'] * 100:.1f}%")
    if result["over_budget"]:
        out.append(f"★ 超预算  {result['overage']} tokens")
    else:
        out.append("未超预算")
    out.append("")

    out.append("按占用排序（最该先看的在前）：")
    for r in result["ranked_by_size"]:
        bar_len = int(r["share"] * 40)
        bar = "█" * bar_len
        flag = " ★单段就超预算" if r["over_budget_alone"] else ""
        out.append(f"  {r['tokens']:>6} tok  {r['share'] * 100:>5.1f}%  {bar}")
        out.append(f"          「{r['title']}」{flag}")
        if r["trim_candidates"]:
            out.append(f"          可裁剪部分：{'、'.join(r['trim_candidates'])}")
        out.append("")

    if result["trimmable_estimate"]:
        out.append(f"保守估计可裁掉约 {result['trimmable_estimate']} tokens"
                   f"（按含上述结构的片段的一半估算，需人工确认）。")
    out.append("")
    out.append("注：token 数为量级估计，真实值取决于模型分词器。")
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contextbudget",
        description="给上下文算账，看预算花在哪（仅依赖标准库）",
        epilog=(
            "示例:\n"
            "  python contextbudget.py --file context.md --budget 4000\n"
            "  python contextbudget.py --file context.md --budget 4000 --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--file", required=True, help="上下文文件")
    ap.add_argument("--budget", type=int, required=True, help="token 预算")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"读不了文件：{e}", file=sys.stderr)
        return 2

    if args.budget <= 0:
        print("预算必须是正数。", file=sys.stderr)
        return 2

    result = analyze(text, args.budget)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(render(result))
    return 1 if result["over_budget"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
