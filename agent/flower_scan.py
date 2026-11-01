import difflib
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

# 花名列表区域（720x1280 坐标）
DEFAULT_ROI = [27, 266, 663, 712]
DEFAULT_SCROLL = {
    "begin": [360, 900],
    "end": [360, 560],
    "steps": 8,
    "duration": 600,
    "end_hold": 500,
    "delay": 700,
}
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


def drag_scroll(controller, scroll: dict) -> None:
    """按住 → 分步移动 → 在终点停住 end_hold 毫秒 → 抬手。

    游戏列表的惯性是按「抬手瞬间的速度」算的：post_swipe 抬手时手指还在动，
    所以会带着残余速度继续滑。这里拆成 touch_down/move/up 手动控制，
    在终点静止 end_hold 毫秒让速度归零，再抬手就不会有惯性。
    """
    x1, y1 = scroll["begin"]
    x2, y2 = scroll["end"]
    steps = max(2, int(scroll.get("steps", 8)))
    duration = max(100, int(scroll.get("duration", 600)))
    end_hold = max(0, int(scroll.get("end_hold", 500)))

    controller.post_touch_down(x1, y1, 0, 1).wait()
    time.sleep(0.05)
    for index in range(1, steps + 1):
        ratio = index / steps
        x = int(x1 + (x2 - x1) * ratio)
        y = int(y1 + (y2 - y1) * ratio)
        controller.post_touch_move(x, y, 0, 1).wait()
        time.sleep(duration / 1000 / steps)
    time.sleep(end_hold / 1000)
    controller.post_touch_up(0).wait()


OPTION_BEGIN = "// >>> 种植花朵候选"
OPTION_END = "// <<< 种植花朵候选"


def flower_option_block(owned: list[str]) -> str:
    """生成 interface.json 中「种植花朵」选项的 JSON 文本（缩进对齐 option 一级）。"""
    names = [name for name in owned if name]
    option = {
        "种植花朵": {
            "type": "select",
            "default_case": names[0],
            "cases": [
                {
                    "name": name,
                    "pipeline_override": {"Plant": {"custom_action_param": {"flower": name}}},
                }
                for name in names
            ],
        }
    }
    dumped = json.dumps(option, ensure_ascii=False, indent=4).splitlines()[1:-1]
    return "\n".join("        " + line[4:] if line.strip() else line for line in dumped)


def write_flower_option(base: Path, owned: list[str]) -> bool:
    """把已获得的花写回 interface.json 的「种植花朵」候选项。

    返回 True 表示候选确实变了（需要重启界面才能看到）。
    """
    names = [name for name in owned if name]
    if not names:
        print("[scan_flowers] 没有已获得的花，保留现有的种植花朵下拉框")
        return False

    interface_path = base / "interface.json"
    if not interface_path.is_file():
        print(f"[scan_flowers] 找不到 {interface_path}，跳过刷新种植花朵候选")
        return False

    text = interface_path.read_text(encoding="utf-8")
    begin = text.find(OPTION_BEGIN)
    end = text.find(OPTION_END)
    if begin < 0 or end < begin:
        print("[scan_flowers] interface.json 里找不到种植花朵候选的标记，跳过刷新")
        return False

    head_line_end = text.find("\n", begin)
    if head_line_end < 0:
        print("[scan_flowers] interface.json 标记行不完整，跳过刷新")
        return False

    new_text = text[: head_line_end + 1] + flower_option_block(names) + "\n        " + text[end:]
    if new_text == text:
        print("[scan_flowers] 种植花朵候选没有变化，不用重启界面")
        return False

    interface_path.write_text(new_text, encoding="utf-8")
    print(f"[scan_flowers] 已把种植花朵候选刷新为 {names} -> {interface_path}")
    return True


def client_process() -> tuple[int, Path] | None:
    """找到启动本 agent 的界面进程（MFAAvalonia.exe），拿不到就返回 None。"""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # PROCESS_QUERY_LIMITED_INFORMATION：普通权限就能拿到进程路径
        handle = kernel32.OpenProcess(0x1000, False, os.getppid())
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return None
            path = Path(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
    except Exception as error:
        print(f"[scan_flowers] 读取父进程失败：{error}")
        return None

    if "mfa" not in path.stem.lower():
        print(f"[scan_flowers] 不是由 MFAAvalonia 启动的（父进程 {path.name}），跳过自动重启")
        return None
    return os.getppid(), path


def restart_client(delay: float = 8.0) -> bool:
    """资源改完后让 MFAAvalonia 自己重启一次，新的「种植花朵」候选立刻生效。

    MFA 只在启动时读一次 interface.json，运行中关窗还会弹「确认退出」，
    所以只能用 taskkill /F 结束进程再 start 起来；这段命令丢给一个 detached
    的 cmd 执行，这样 agent 跟着被结束时它仍然会跑完。
    """
    found = client_process()
    if found is None:
        return False

    pid, exe = found
    seconds = max(3, int(delay))
    command = (
        f'ping -n {seconds + 1} 127.0.0.1 >nul & '
        f'taskkill /F /PID {pid} & '
        f'start "" "{exe}"'
    )
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    flags = 0x00000008 | 0x00000200
    try:
        subprocess.Popen(
            ["cmd", "/c", command],
            cwd=str(exe.parent),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as error:
        print(f"[scan_flowers] 启动重启脚本失败：{error}")
        return False

    print(f"[scan_flowers] {seconds} 秒后自动重启 MFAAvalonia，让新的「种植花朵」候选生效")
    return True


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

            drag_scroll(controller, scroll)
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
        if write_flower_option(base, owned):
            restart_client()

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
