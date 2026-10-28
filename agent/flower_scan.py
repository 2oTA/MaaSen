import difflib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

# 花名列表区域（720x1280 坐标）
DEFAULT_ROI = [27, 266, 663, 712]
DEFAULT_SCROLL = {"begin": [360, 900], "end": [360, 560], "duration": 700, "delay": 700}
PUNCTUATION = re.compile(r"[\s\·・．.。,，、:：;；'\"“”‘’()（）\[\]【】<>《》_\-—~!！?？|/\\]+")


def normalize(text: str) -> str:
    return PUNCTUATION.sub("", text or "")


def is_unowned(text: str) -> bool:
    """识别「未获得」分隔行；容忍 OCR 把「获」认成别的字时只剩部分特征。"""
    normalized = normalize(text)
    if not normalized:
        return False
    if "未获得" in normalized or "末获得" in normalized:
        return True
    return "获" in normalized and ("未" in normalized or "末" in normalized)


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


def box_of(result) -> list[int]:
    box = result.box
    if hasattr(box, "x"):
        return [int(box.x), int(box.y), int(box.w), int(box.h)]
    return [int(v) for v in box]


def sort_row_major(results) -> list[tuple[int, int, int, int, str]]:
    """把 OCR 结果按「从上到下、从左到右」排序。"""
    items = [
        (*box_of(r), r.text)
        for r in results
        if getattr(r, "text", None) and getattr(r, "box", None)
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


def ocr_frame(context: Context, image, roi: list[int]) -> list[tuple[int, int, int, int, str]]:
    detail = context.run_recognition(
        "FlowerListOCR",
        image,
        pipeline_override={"FlowerListOCR": {"roi": list(roi)}},
    )
    if detail is None or not detail.hit:
        return []
    return sort_row_major(detail.all_results or [])


@AgentServer.custom_action("scan_flowers")
class ScanFlowers(CustomAction):
    """逐屏 OCR 花房列表，收集已拥有的花，直到遇到「未获得」分隔行。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        roi = param.get("roi") or DEFAULT_ROI
        scroll = {**DEFAULT_SCROLL, **(param.get("scroll") or {})}
        max_scrolls = int(param.get("max_scrolls", 30))

        base = base_dir()
        library_path = base / param.get("library", "resource/花朵库.txt")
        output_path = base / param.get("output", "config/flowers.json")
        if not library_path.exists():
            print(f"[scan_flowers] 花名库不存在: {library_path}")
            return False

        pairs = load_library(library_path)
        controller = context.tasker.controller

        owned: list[str] = []
        unknown: list[str] = []
        frames: list[dict] = []
        stopped = False
        empty_streak = 0
        no_new_streak = 0

        for attempt in range(max_scrolls + 1):
            image = controller.post_screencap().wait().get()
            ordered = ocr_frame(context, image, roi)

            names_in_frame = 0
            for x, y, w, h, text in ordered:
                normalized = normalize(text)
                if not normalized:
                    continue
                if is_unowned(normalized):
                    stopped = True
                    break
                if normalized.isdigit():
                    continue
                matched = match_name(normalized, pairs)
                if matched is None:
                    if text not in unknown:
                        unknown.append(text)
                    continue
                names_in_frame += 1
                if matched not in owned:
                    owned.append(matched)

            frames.append(
                {
                    "frame": len(frames) + 1,
                    "stopped": stopped,
                    "texts": [text for _, _, _, _, text in ordered],
                }
            )

            if stopped:
                break
            if not ordered:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            empty_streak = 0

            if names_in_frame == 0:
                no_new_streak += 1
                if no_new_streak >= 2:
                    break
            else:
                no_new_streak = 0

            if attempt == max_scrolls:
                break

            controller.post_swipe(*scroll["begin"], *scroll["end"], int(scroll["duration"])).wait()
            time.sleep(int(scroll["delay"]) / 1000)

        if not owned and not stopped:
            print("[scan_flowers] 没有识别到任何花名，可能不在花房页面")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "owned": owned,
            "unknown_texts": unknown,
            "stopped_at_unowned": stopped,
            "frames": len(frames),
            "library_count": len(pairs),
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")

        debug_path = base / "debug" / "flowers_scan.json"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(
            json.dumps({"roi": list(roi), "scroll": scroll, "frames": frames}, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        print(
            f"[scan_flowers] owned={owned} unknown={unknown} "
            f"stopped={stopped} frames={len(frames)} output={output_path}"
        )
        return True
