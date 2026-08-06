"""Sinh trang demo so sanh baseline / corrupted / repaired - Role 1.

Doc artifact THAT trong `data/`, tinh diff theo tung dong va xuat mot file HTML
tu chua. Thiếu artifact nào thì trang ghi rõ là thiếu, không bịa số.

Chay:
    uv run python script/build_demo.py
"""
from __future__ import annotations

from html import escape
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import load_settings  # noqa: E402

TRACKED_FIELDS = ("title", "summary", "published", "age_days", "authors_joined", "categories_joined")
METRIC_LABELS = {
    "retrieval_hit_rate": "Retrieval hit rate",
    "mean_token_f1": "Mean token F1",
    "judge_accuracy": "Judge accuracy",
    "mean_judge_score": "Mean judge score",
}


def load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def rows_by_id(records) -> dict:
    if not records:
        return {}
    return {str(row["paper_id"]): row for row in records}


def shorten(value, limit: int = 90) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ")
    if not text.strip():
        return "(rỗng)"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def diff_rows(baseline: dict, corrupted, repaired) -> list[dict]:
    """So tung paper_id giua baseline va corrupted, kem trang thai repaired."""
    if corrupted is None:
        return []
    corrupted_counts: dict[str, int] = {}
    for row in corrupted:
        key = str(row["paper_id"])
        corrupted_counts[key] = corrupted_counts.get(key, 0) + 1
    corrupted_by_id = rows_by_id(corrupted)
    repaired_by_id = rows_by_id(repaired)

    out: list[dict] = []
    for paper_id, base_row in baseline.items():
        after = corrupted_by_id.get(paper_id)
        issues: list[dict] = []
        if after is None:
            issues.append({"field": "toàn bộ bản ghi", "before": "có trong baseline", "after": "bị xoá"})
        else:
            if corrupted_counts.get(paper_id, 0) > 1:
                issues.append(
                    {
                        "field": "paper_id",
                        "before": "1 dòng",
                        "after": f"{corrupted_counts[paper_id]} dòng trùng",
                    }
                )
            for field in TRACKED_FIELDS:
                before, now = base_row.get(field), after.get(field)
                if str(before) != str(now):
                    issues.append({"field": field, "before": before, "after": now})
        if not issues:
            continue
        restored = paper_id in repaired_by_id and all(
            str(repaired_by_id[paper_id].get(item["field"])) == str(base_row.get(item["field"]))
            for item in issues
            if item["field"] in TRACKED_FIELDS
        )
        out.append(
            {
                "paper_id": paper_id,
                "title": base_row.get("title", ""),
                "issues": issues,
                "restored": restored if repaired is not None else None,
            }
        )
    return out


CSS = """
:root{
  --ground:#f6f7f9; --panel:#ffffff; --ink:#12161c; --ink-soft:#5a6472;
  --line:#dfe3ea; --line-soft:#eceff4;
  --base:#5a6472; --corrupt:#b23c17; --corrupt-bg:#fdf0ea;
  --repair:#0f6b60; --repair-bg:#e8f4f2; --warn:#8a6100;
}
@media (prefers-color-scheme:dark){
  :root{
    --ground:#0f1216; --panel:#161b21; --ink:#e6eaf0; --ink-soft:#96a0ae;
    --line:#262d36; --line-soft:#1d232b;
    --base:#96a0ae; --corrupt:#f08a5f; --corrupt-bg:#2a1a13;
    --repair:#5fc9b8; --repair-bg:#0f2320; --warn:#d3a44a;
  }
}
:root[data-theme="dark"]{
  --ground:#0f1216; --panel:#161b21; --ink:#e6eaf0; --ink-soft:#96a0ae;
  --line:#262d36; --line-soft:#1d232b;
  --base:#96a0ae; --corrupt:#f08a5f; --corrupt-bg:#2a1a13;
  --repair:#5fc9b8; --repair-bg:#0f2320; --warn:#d3a44a;
}
:root[data-theme="light"]{
  --ground:#f6f7f9; --panel:#ffffff; --ink:#12161c; --ink-soft:#5a6472;
  --line:#dfe3ea; --line-soft:#eceff4;
  --base:#5a6472; --corrupt:#b23c17; --corrupt-bg:#fdf0ea;
  --repair:#0f6b60; --repair-bg:#e8f4f2; --warn:#8a6100;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.55}
.wrap{max-width:1120px;margin:0 auto;padding:40px 24px 72px;display:flex;flex-direction:column;gap:32px}
header{border-bottom:2px solid var(--ink);padding-bottom:20px;
  display:flex;flex-wrap:wrap;gap:16px;align-items:baseline;justify-content:space-between}
h1{font-size:1.7rem;margin:0;letter-spacing:-.02em;text-wrap:balance}
.sub{color:var(--ink-soft);font-size:.86rem;margin:6px 0 0}
.stamp{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.74rem;
  color:var(--ink-soft);text-align:right}
h2{font-size:1.02rem;margin:0 0 4px;letter-spacing:.04em;text-transform:uppercase}
h2 .n{color:var(--ink-soft);font-family:ui-monospace,monospace;margin-right:8px;font-weight:500}
section{display:flex;flex-direction:column;gap:14px}
.note{color:var(--ink-soft);font-size:.88rem;margin:0;max-width:70ch}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.86rem}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line-soft);vertical-align:top}
th{font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-soft);
  font-weight:600;background:var(--line-soft);white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
td.num{text-align:right;font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}
.chip{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.71rem;font-weight:600;
  letter-spacing:.03em;white-space:nowrap}
.chip-corrupt{background:var(--corrupt-bg);color:var(--corrupt)}
.chip-repair{background:var(--repair-bg);color:var(--repair)}
.chip-miss{background:var(--line-soft);color:var(--ink-soft)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px;
  display:flex;flex-direction:column;gap:6px;border-left:3px solid var(--line)}
.card.bad{border-left-color:var(--corrupt)}
.card.good{border-left-color:var(--repair)}
.card .k{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-soft)}
.card .v{font-size:1.5rem;font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums}
.card .d{font-size:.78rem;color:var(--ink-soft)}
.delta-bad{color:var(--corrupt);font-weight:600}
.delta-good{color:var(--repair);font-weight:600}
.before{color:var(--ink-soft);text-decoration:line-through;text-decoration-color:var(--corrupt)}
.after{color:var(--corrupt);font-weight:500}
.missing{background:var(--corrupt-bg);border:1px solid var(--corrupt);color:var(--corrupt);
  padding:12px 16px;border-radius:6px;font-size:.88rem}
ul.log{margin:0;padding-left:18px;font-size:.86rem}
ul.log li{margin-bottom:4px}
footer{border-top:1px solid var(--line);padding-top:16px;color:var(--ink-soft);font-size:.78rem}
"""


def metric_cards(baseline, corrupted, repaired) -> str:
    if not baseline:
        return '<p class="missing">Chưa có baseline_metrics.json.</p>'
    cards = []
    for key, label in METRIC_LABELS.items():
        if key not in baseline:
            continue
        base = baseline[key]
        cur = corrupted.get(key) if corrupted else None
        rep = repaired.get(key) if repaired else None
        detail, cls = "chưa có corrupted", ""
        if cur is not None:
            delta = cur - base
            worse = delta < -1e-9
            cls = "bad" if worse else ""
            arrow = "▼" if worse else ("▲" if delta > 1e-9 else "=")
            span = "delta-bad" if worse else "delta-good"
            detail = (
                f'corrupted <span class="{span} mono">{cur:.4f} {arrow}{abs(delta):.4f}</span>'
            )
            if rep is not None:
                back = abs(rep - base) < 1e-9
                cls = "good" if back else cls
                detail += (
                    f' · repaired <span class="{"delta-good" if back else "delta-bad"} mono">'
                    f'{rep:.4f}{" (khôi phục)" if back else ""}</span>'
                )
        cards.append(
            f'<div class="card {cls}"><span class="k">{escape(label)}</span>'
            f'<span class="v">{base:.4f}</span><span class="d">baseline · {detail}</span></div>'
        )
    return f'<div class="cards">{"".join(cards)}</div>'


def diff_table(diffs, has_corrupted: bool) -> str:
    if not has_corrupted:
        return (
            '<p class="missing">Chưa có <span class="mono">papers_clean_corrupted.json</span>. '
            "Chạy <span class=\"mono\">script/run_corruption_flow.py</span> sau khi "
            "<span class=\"mono\">corrupt_clean_dataframe</span> được implement.</p>"
        )
    if not diffs:
        return '<p class="missing">Corrupted dataset không khác baseline dòng nào — corruption chưa có tác dụng.</p>'
    body = []
    for item in diffs:
        first = True
        for issue in item["issues"]:
            cells = []
            if first:
                span = len(item["issues"])
                status = (
                    '<span class="chip chip-repair">đã khôi phục</span>'
                    if item["restored"]
                    else ('<span class="chip chip-corrupt">chưa khôi phục</span>'
                          if item["restored"] is False else '<span class="chip chip-miss">chưa repair</span>')
                )
                cells.append(
                    f'<td rowspan="{span}"><div class="mono">{escape(item["paper_id"])}</div>'
                    f'<div class="d">{escape(shorten(item["title"], 70))}</div></td>'
                )
                cells.append(f'<td rowspan="{span}">{status}</td>')
                first = False
            cells.append(f'<td class="mono">{escape(issue["field"])}</td>')
            cells.append(f'<td class="before">{escape(shorten(issue["before"]))}</td>')
            cells.append(f'<td class="after">{escape(shorten(issue["after"]))}</td>')
            body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="panel"><table><thead><tr><th>Paper</th><th>Repair</th><th>Trường</th>'
        "<th>Baseline</th><th>Sau corruption</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def signal_table(sets: list[tuple[str, dict | None, dict | None]]) -> str:
    keys = ["row_count", "paper_id_duplicates", "summary_nulls", "short_summaries", "stale_rows"]
    labels = {
        "row_count": "Số dòng",
        "paper_id_duplicates": "paper_id trùng",
        "summary_nulls": "Summary thiếu/rỗng",
        "short_summaries": "Summary quá ngắn",
        "stale_rows": "Dòng quá hạn",
    }
    head = "".join(f"<th>{escape(name)}</th>" for name, _, _ in sets)
    rows = []
    for key in keys:
        cells = []
        for _, quality, _ in sets:
            cells.append(f'<td class="num">{quality.get(key, "—") if quality else "—"}</td>')
        rows.append(f'<tr><td>{labels[key]}</td>{"".join(cells)}</tr>')
    fresh = []
    for _, _, freshness in sets:
        if not freshness:
            fresh.append('<td class="num">—</td>')
            continue
        ok = freshness.get("is_fresh")
        chip = "chip-repair" if ok else "chip-corrupt"
        fresh.append(f'<td class="num"><span class="chip {chip}">{"fresh" if ok else "stale"}</span></td>')
    rows.append(f'<tr><td>Trạng thái freshness</td>{"".join(fresh)}</tr>')
    latest = []
    for _, _, freshness in sets:
        latest.append(f'<td class="num mono">{escape(str((freshness or {}).get("latest_published", "—")))}</td>')
    rows.append(f'<tr><td>Ngày mới nhất</td>{"".join(latest)}</tr>')
    return (
        f'<div class="panel"><table><thead><tr><th>Tín hiệu</th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def log_list(log) -> str:
    """Doc corruption log. Ho tro ca list phang lan dang co key `events`."""
    if not log:
        return '<p class="missing">Chưa có corruption_log.json.</p>'
    if isinstance(log, list):
        entries = log
        head = ""
    else:
        entries = log.get("events") or log.get("corruptions") or []
        bits = []
        if log.get("deterministic"):
            bits.append('<span class="chip chip-repair">deterministic</span>')
        guard = (log.get("raw_source_guard") or {}).get("status")
        if guard:
            chip = "chip-repair" if guard == "verified" else "chip-corrupt"
            bits.append(f'<span class="chip {chip}">raw source: {escape(str(guard))}</span>')
        result = log.get("result") or {}
        if result.get("different_from_baseline") is not None:
            ok = result["different_from_baseline"]
            bits.append(
                f'<span class="chip {"chip-corrupt" if ok else "chip-miss"}">'
                f'{"khác baseline" if ok else "KHÔNG khác baseline"}</span>'
            )
        head = f'<p class="note">{" ".join(bits)}</p>' if bits else ""

    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            items.append(f"<li>{escape(str(entry))}</li>")
            continue
        kind = entry.get("type", entry.get("name", "?"))
        params = entry.get("parameters") or {}
        ids = entry.get("paper_ids") or []
        count = entry.get("count", params.get("count", len(ids)))
        skip = {"type", "name", "count", "paper_ids", "parameters", "sequence"}
        extra = {**{k: v for k, v in entry.items() if k not in skip}, **params}
        extra.pop("count", None)
        detail = (
            f' · <span class="mono">{escape(json.dumps(extra, ensure_ascii=False))}</span>'
            if extra
            else ""
        )
        ids_text = (
            f'<div class="d mono">{escape(", ".join(str(i) for i in ids[:4]))}'
            f'{" …" if len(ids) > 4 else ""}</div>'
            if ids
            else ""
        )
        items.append(
            f'<li><span class="mono">{escape(str(kind))}</span> — {count} bản ghi{detail}{ids_text}</li>'
        )
    return f'{head}<ul class="log">{"".join(items)}</ul>'


def main() -> int:
    settings = load_settings()
    paths = settings.paths

    baseline_clean = load(paths.clean_json)
    corrupted_clean = load(paths.corrupted_clean_json)
    repaired_clean = load(paths.repaired_clean_json)
    diffs = diff_rows(rows_by_id(baseline_clean), corrupted_clean, repaired_clean)

    quality_dir = paths.quality_dir
    sets = [
        ("Baseline", load(quality_dir / "baseline.json"), load(paths.freshness_report)),
        ("Corrupted", load(quality_dir / "corrupted.json"), load(quality_dir / "freshness_corrupted.json")),
        ("Repaired", load(quality_dir / "repaired.json"), load(quality_dir / "freshness_repaired.json")),
    ]

    affected = len(diffs)
    total = len(baseline_clean or [])
    restored = sum(1 for item in diffs if item["restored"])

    html = f"""<meta charset="utf-8">
<title>Data corruption demo — Day 10</title>
<style>{CSS}</style>
<div class="wrap">
<header>
  <div>
    <h1>Corruption &amp; recovery — bằng chứng từ artifact thật</h1>
    <p class="sub">Mọi số trên trang đều đọc trực tiếp từ <span class="mono">data/</span>. Không có giá trị nào được nhập tay.</p>
  </div>
  <div class="stamp">baseline {total} dòng<br>bị tác động {affected}<br>khôi phục {restored}</div>
</header>

<section>
  <h2><span class="n">01</span>Chất lượng trả lời của agent</h2>
  <p class="note">Ba trạng thái dùng chung một test set, cùng top-k và cùng evaluator, nên chênh lệch chỉ còn quy về chất lượng dữ liệu.</p>
  {metric_cards(load(paths.baseline_metrics), load(paths.corrupted_metrics), load(paths.repaired_metrics))}
</section>

<section>
  <h2><span class="n">02</span>Dòng nào bị hỏng, hỏng ở đâu</h2>
  <p class="note">So sánh từng <span class="mono">paper_id</span> giữa clean baseline và clean corrupted. Gạch ngang là giá trị gốc, chữ màu là giá trị sau khi corrupt.</p>
  {diff_table(diffs, corrupted_clean is not None)}
</section>

<section>
  <h2><span class="n">03</span>Corruption log</h2>
  <p class="note">Do <span class="mono">corrupt_clean_dataframe</span> ghi ra — đối chiếu với bảng trên để chắc corruption đúng như mô tả.</p>
  {log_list(load(paths.corruption_log))}
</section>

<section>
  <h2><span class="n">04</span>Tín hiệu data quality</h2>
  <p class="note">Nếu corruption có thật mà cột Corrupted không đổi, nghĩa là checker hỏng chứ không phải pipeline không phát hiện được.</p>
  {signal_table(sets)}
</section>

<footer>
  Sinh bởi <span class="mono">script/build_demo.py</span> · nguồn: <span class="mono">data/clean/</span>,
  <span class="mono">data/results/</span>, <span class="mono">data/quality/</span> ·
  Thiếu artifact nào thì trang ghi rõ là thiếu, không bịa số.
</footer>
</div>
"""
    out = paths.project_dir / "data" / "reports" / "demo.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[demo] {out}")
    print(f"[demo] baseline {total} dong · bi tac dong {affected} · khoi phuc {restored}")
    if corrupted_clean is None:
        print("[demo] CANH BAO: chua co corrupted dataset, trang chi hien phan baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
