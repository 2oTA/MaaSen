import difflib
import json
import re
from datetime import datetime
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition

# 花房列表区域（720x1280 坐标）
DEFAULT_ROI = [27, 266, 663, 712]
UNOWNED_KEYWORDS = ("未获得", "末获得")
PUNCTUATION = re.compile(r"[\s\·・．.。,，、:：;；'\"“”‘’()（）\[\]【】<>《》_\-—~!！?？|/\\]+")


def normalize(text: str) -> str:
    return PUNCTUATION.sub("", text or "")


def base_dir() -> Path:
    """agent 的 CWD 通常是 interface.json 所在目录；调试时可能是项目根目录。"""
    cwd = Path.cwd()
    for candidate in (cwd, cwd / "assets"):
        if (candidate / "resource").is_dir():
            return candidate
    return cwd


def load_library(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        raw = line.strip()
        if not raw:
            continue
        pairs.append((normalize(raw), raw))
    return pairs


def match_name(text: str, pairs: list[tuple[str, str]]) -> str | None:
    for normalized, raw in pairs:
        if text == normalized:
            return raw
    for normalized, raw in pairs:
        if text.startswith(normalized) or text.endswith(normalized):
            return raw

    best_raw = None
    best_ratio = 0.0
    for normalized, raw in pairs:
        ratio = difflib.SequenceMatcher(None, text, normalized).ratio()
        if ratio > best_ratio:
            best_raw, best_ratio = raw, ratio
    return best_raw if best_ratio >= 0.8 else None


def sort_row_major(results) -> list[tuple[int, int, int, int, str]]:
    """把 OCR 结果按「从上到下、从左到右」排序。"""
    items = [
        (int(r.box.x), int(r.box.y), int(r.box.w), int(r.box.h), r.text)
        for r in results
        if getattr(r, "text", None)
    ]
    if not items:
        return []

    heights = sorted(item[3] for item in items)
    tolerance = max(8.0, heights[len(heights) // 2] * 0.6)

    items.sort(key=lambda item: item[1] + item[3] / 2)
    rows: list[list] = []
    for item in items:
        center_y = item[1] + item[3] / 2
        if rows and abs(center_y - rows[-1][0]) <= tolerance:
            rows[-1][1].append(item)
        else:
            rows.append([center_y, [item]])

    ordered: list[tuple[int, int, int, int, str]] = []
    for _, row in rows:
        row.sort(key=lambda item: item[0])
        ordered.extend(row)
    return ordered


@AgentServer.custom_recognition("scan_flowers")
class ScanFlowers(CustomRecognition):
    """识别花房列表，记录已拥有的花，写入 config/flowers.json。"""

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        param = json.loads(argv.custom_recognition_param or "{}") or {}
        roi = param.get("roi") or DEFAULT_ROI
        base = base_dir()
        library_path = base / param.get("library", "resource/花朵库.txt")
        output_path = base / param.get("output", "config/flowers.json")

        if not library_path.exists():
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"error": f"花名库不存在: {library_path}"},
            )

        pairs = load_library(library_path)

        detail = context.run_recognition(
            "FlowerListOCR",
            argv.image,
            pipeline_override={"FlowerListOCR": {"roi": list(roi)}},
        )
        if detail is None or not detail.hit:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"error": "花名 OCR 未识别到内容"},
            )

        ordered = sort_row_major(detail.all_results or [])

        owned: list[str] = []
        unknown: list[str] = []
        stopped = False
        for _, _, _, _, text in ordered:
            normalized = normalize(text)
            if not normalized:
                continue
            if any(keyword in normalized for keyword in UNOWNED_KEYWORDS) or (
                "未" in normalized and "获得" in normalized
            ):
                stopped = True
                break

            matched = match_name(normalized, pairs)
            if matched is None:
                unknown.append(text)
            elif matched not in owned:
                owned.append(matched)

        if not owned and not stopped:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"error": "没有识别到任何花名，可能不在花房页面"},
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "owned": owned,
            "unknown_texts": unknown,
            "stopped_at_unowned": stopped,
            "library_count": len(pairs),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")

        debug_path = base / "debug" / "flowers_scan.json"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(
            json.dumps(
                {
                    "roi": list(roi),
                    "ocr": [
                        {"text": text, "box": [x, y, w, h]}
                        for x, y, w, h, text in ordered
                    ],
                },
                ensure_ascii=False,
                indent=4,
            ),
            encoding="utf-8",
        )

        print(
            f"[scan_flowers] owned={owned} unknown={unknown} "
            f"stopped={stopped} output={output_path}"
        )

        return CustomRecognition.AnalyzeResult(
            box=list(roi),
            detail={
                "owned": owned,
                "unknown": unknown,
                "stopped": stopped,
                "output": str(output_path),
            },
        )
