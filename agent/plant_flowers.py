"""种植：把「更新数据」里已拥有的花种到指定地块。

流程（每块地）：
1. 在地块包围盒内识别「空地」（vacant land.png，绿幕掩码）
2. 点击空地中心 → 弹出种植列表
3. 在列表区域内 OCR 找到目标花名 → 在花名文字上方 -50px 处的花朵图片上按下手指
4. 手指全程不松手：按住的这一下就已经「拿起」了花，随后缓慢移动着过剩下的空地，
   每经过一块空地都要重新识别，直到该地块内识别不到空地才抬手
"""

import json
import time
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from flower_scan import base_dir, box_of, drag_scroll, match_name, normalize

# 6 块地块的包围盒 [x, y, w, h]（720x1280 下直接量取，不再做任何缩放；
# 四角坐标与换算过程见 docs/zh_cn/farm/plots.md）
PLOTS = {
    1: [210, 572, 248, 128],
    2: [349, 636, 243, 126],
    3: [459, 695, 210, 113],
    4: [52, 645, 268, 128],
    5: [208, 703, 252, 130],
    6: [330, 769, 202, 106],
}

# 同一批地块的四个角（左上、右上、右下、左下）。地块是斜着的菱形，
# 外接矩形在斜对角方向会和邻居重叠（比如 1 和 2 重叠 109x64），所以识别到空地后
# 还要用「点是否落在本块地的四边形内」再过滤一次，避免点到邻居的地里
PLOT_QUADS = {
    1: [(210, 644), (340, 572), (458, 630), (316, 700)],
    2: [(349, 706), (481, 636), (592, 694), (458, 762)],
    3: [(459, 765), (596, 695), (669, 737), (532, 808)],
    4: [(52, 711), (198, 645), (320, 703), (168, 773)],
    5: [(208, 774), (340, 703), (460, 766), (322, 833)],
    6: [(330, 835), (462, 769), (532, 809), (398, 875)],
}

# 四边形过滤向外放宽的比例（以地块中心为基准缩放），抵消手工量取的一点点误差。
# 1.10 在竖直方向约放宽 5px、水平方向约 12px，仍远小于相邻地块格子的间距（约 40px）
QUAD_MARGIN = 1.10

# 种植列表区域（720x1280）：用户给的原始 35:920 ~ 855:1395，按 ×0.8 换算
DEFAULT_LIST_ROI = [28, 736, 656, 380]

# 列表里的花找不到时，上滑翻页用（与花房扫描同一套参数，抬手前停顿避免惯性）
DEFAULT_LIST_SCROLL = {
    "begin": [360, 1000],
    "end": [360, 700],
    "steps": 8,
    "duration": 600,
    "end_hold": 500,
    "delay": 700,
}

# 「种植地块」复选框：勾上的地块号由 plot_select 收集到这里，Plant 节点取走后清空
SELECTED_PLOTS: list[int] = []

# 还没跑过「更新数据」时，「种植花朵」下拉框里只有这一条提示
NEED_UPDATE_HINT = "⚠"


def expand(box: list[int], pad: int = 12) -> list[int]:
    x, y, w, h = box
    return [max(0, x - pad), max(0, y - pad), w + 2 * pad, h + 2 * pad]


def center_of(box: list[int]) -> tuple[int, int]:
    x, y, w, h = box
    return x + w // 2, y + h // 2


def load_library(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        raw = line.strip()
        if raw:
            pairs.append((normalize(raw), raw))
    return pairs


def load_owned(path: Path) -> list[str]:
    """读取「更新数据」的结果，仅用于提示用户这个花其实还没获得。"""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [str(name) for name in payload.get("owned", [])]


def inside_quad(point: tuple[int, int], quad: list[tuple[int, int]], margin: float = 1.0) -> bool:
    """射线法判断点是否在四边形内；margin>1 时把四边形以中心为基准向外放大。"""
    x, y = point
    cx = sum(p[0] for p in quad) / len(quad)
    cy = sum(p[1] for p in quad) / len(quad)
    xs = [cx + (px - cx) * margin for px, _ in quad]
    ys = [cy + (py - cy) * margin for _, py in quad]

    inside = False
    count = len(quad)
    for index in range(count):
        x1, y1 = xs[index], ys[index]
        x2, y2 = xs[(index + 1) % count], ys[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cross:
                inside = not inside
    return inside


def find_vacant(
    context: Context,
    image,
    roi: list[int],
    threshold: float,
    quad: list[tuple[int, int]] | None = None,
) -> list[list[int]]:
    """在指定区域内找空地，按匹配分数从高到低返回包围盒。

    给了 quad 就只保留「格子中心落在该四边形内」的匹配：外接矩形在斜对角方向
    会和邻居重叠，不过滤的话会把邻居的地也当成自己的。
    """
    detail = context.run_recognition(
        "VacantLand",
        image,
        pipeline_override={"VacantLand": {"roi": list(roi), "threshold": threshold}},
    )
    if detail is None or not detail.hit:
        return []
    results = getattr(detail, "filtered_results", None) or detail.all_results or []
    scored = [(box_of(result), float(getattr(result, "score", 0.0))) for result in results]
    if quad is not None:
        scored = [
            (box, score)
            for box, score in scored
            if inside_quad((box[0] + box[2] // 2, box[1] + box[3] // 2), quad, QUAD_MARGIN)
        ]
    scored.sort(key=lambda item: -item[1])
    return [box for box, _ in scored]


def ocr_texts(context: Context, image, roi: list[int]) -> list[tuple[int, int, int, int, str]]:
    detail = context.run_recognition(
        "PlantListOCR",
        image,
        pipeline_override={"PlantListOCR": {"roi": list(roi)}},
    )
    if detail is None or not detail.hit:
        return []
    return [
        (box_of(result) + [result.text])
        for result in (detail.all_results or [])
        if getattr(result, "text", None)
    ]


def find_name_box(
    texts: list[tuple[int, int, int, int, str]], target: str
) -> list[int] | None:
    """在 OCR 结果里找目标花名，返回文字框 [x, y, w, h]。"""
    normalized_target = normalize(target)
    for x, y, w, h, text in texts:
        normalized = normalize(text)
        if normalized == normalized_target:
            return [x, y, w, h]
    for x, y, w, h, text in texts:
        normalized = normalize(text)
        if normalized_target in normalized or normalized in normalized_target:
            return [x, y, w, h]
    return None


def move_slowly(controller, begin: tuple[int, int], end: tuple[int, int], steps: int, duration: int) -> None:
    """按住的状态下慢慢移动到目标点（每步之间留时间，让游戏能跟上手指）。"""
    x1, y1 = begin
    x2, y2 = end
    for index in range(1, max(2, steps) + 1):
        ratio = index / steps
        x = int(x1 + (x2 - x1) * ratio)
        y = int(y1 + (y2 - y1) * ratio)
        controller.post_touch_move(x, y, 0, 1).wait()
        time.sleep(duration / 1000 / steps)


def drag_over_vacant(
    context: Context,
    controller,
    start: tuple[int, int],
    roi: list[int],
    quad: list[tuple[int, int]],
    threshold: float,
    max_passes: int,
    move_steps: int,
    move_duration: int,
    first_move_steps: int,
    first_move_duration: int,
    hold: float,
    press_hold: float,
) -> bool:
    """从 start 点按下手指，全程不松手地拖过地块里的空地。

    start 就是花朵图片（花名文字中心 Y-50），按下这一下同时完成「拿起花」，
    之后只移动不抬手，直到该地块内识别不到空地。返回 True 表示已种满。

    第一步（从花朵到第一个空地）用 first_move_steps / first_move_duration 走，
    比后续移动快得多：拖得慢的话，手指经过的其他空地会被一起种上。
    """
    position = start
    pressed = False
    first = True
    try:
        controller.post_touch_down(start[0], start[1], 0, 1).wait()
        pressed = True
        time.sleep(press_hold)  # 按住不动一下，让游戏确认「拿起」了这朵花

        for _ in range(max_passes):
            image = controller.post_screencap().wait().get()
            vacant = find_vacant(context, image, roi, threshold, quad)
            if not vacant:
                return True
            target = center_of(vacant[0])
            steps = first_move_steps if first else move_steps
            duration = first_move_duration if first else move_duration
            move_slowly(controller, position, target, steps, duration)
            first = False
            position = target
            time.sleep(hold)
    finally:
        if pressed:
            controller.post_touch_up(0).wait()

    image = controller.post_screencap().wait().get()
    return not find_vacant(context, image, roi, threshold, quad)


@AgentServer.custom_action("plot_select")
class PlotSelect(CustomAction):
    """收集复选框勾选的地块号；plot 为 0 表示这块地没勾选，直接跳过。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        try:
            plot = int(param.get("plot", 0))
        except (TypeError, ValueError):
            plot = 0
        if 0 < plot <= len(PLOTS) and plot not in SELECTED_PLOTS:
            SELECTED_PLOTS.append(plot)
        return True


@AgentServer.custom_action("plant_flowers")
class PlantFlowers(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        flower = str(param.get("flower") or "").strip()
        list_roi = [int(v) for v in (param.get("list_roi") or DEFAULT_LIST_ROI)]
        name_offset_y = int(param.get("name_offset_y", -50))
        max_list_scrolls = int(param.get("max_list_scrolls", 6))
        max_attempts = int(param.get("max_attempts", 3))
        max_passes = int(param.get("max_passes", 8))
        threshold = float(param.get("vacant_threshold", 0.7))
        move_steps = int(param.get("move_steps", 6))
        move_duration = int(param.get("move_duration", 500))
        first_move_steps = int(param.get("first_move_steps", 3))
        first_move_duration = int(param.get("first_move_duration", 150))
        hold = float(param.get("hold", 0.35))
        press_hold = float(param.get("press_hold", 0.5))
        list_scroll = {**DEFAULT_LIST_SCROLL, **(param.get("list_scroll") or {})}

        if not flower:
            print("[plant_flowers] 没有指定花名")
            return False

        if flower.startswith(NEED_UPDATE_HINT):
            print(
                "[plant_flowers] 还没更新过花朵数据。请先在任务列表里把「更新数据」勾上跑一次"
                "（跑完会自动重启 MFAAvalonia），再回来这里选要种的花。"
            )
            return False

        base = base_dir()
        library_path = base / "resource/花朵库.txt"
        if not library_path.exists():
            print(f"[plant_flowers] 花名库不存在: {library_path}")
            return False

        pairs = load_library(library_path)
        target = match_name(normalize(flower), pairs)
        if target is None:
            print(f"[plant_flowers] 花名库里没有「{flower}」，请检查花朵库.txt")
            return False

        owned = load_owned(base / "config/flowers.json")
        if not owned:
            print(
                "[plant_flowers] 还没更新过花朵数据（config/flowers.json 不存在或没有已获得的花）。"
                "请先跑一次「更新数据」（跑完会自动重启 MFAAvalonia），再回来种植。"
            )
            return False
        if target not in owned:
            print(
                f"[plant_flowers] 「{target}」还没获得，游戏里的种植列表不会有它。"
                f"已获得：{'、'.join(owned)}。"
                "请在「种植花朵」里改选一朵已获得的，或先跑一次「更新数据」。"
            )
            return False

        plots = sorted(SELECTED_PLOTS)
        SELECTED_PLOTS.clear()
        if not plots:
            print("[plant_flowers] 没有勾选任何地块，请在「种植地块」里至少勾选一块")
            return False

        print(f"[plant_flowers] 目标花={target} 地块={plots}")

        controller = context.tasker.controller
        planted: list[int] = []
        failed: list[int] = []

        for index in plots:
            roi = expand(PLOTS[index])
            result = self.plant_one(
                context,
                controller,
                index,
                roi,
                PLOT_QUADS[index],
                target,
                list_roi,
                name_offset_y,
                max_list_scrolls,
                max_attempts,
                max_passes,
                threshold,
                move_steps,
                move_duration,
                first_move_steps,
                first_move_duration,
                hold,
                press_hold,
                list_scroll,
            )
            if result:
                planted.append(index)
            else:
                failed.append(index)

        print(f"[plant_flowers] 已种植地块={planted} 失败地块={failed}")
        return not failed

    def plant_one(
        self,
        context: Context,
        controller,
        index: int,
        roi: list[int],
        quad: list[tuple[int, int]],
        target: str,
        list_roi: list[int],
        name_offset_y: int,
        max_list_scrolls: int,
        max_attempts: int,
        max_passes: int,
        threshold: float,
        move_steps: int,
        move_duration: int,
        first_move_steps: int,
        first_move_duration: int,
        hold: float,
        press_hold: float,
        list_scroll: dict,
    ) -> bool:
        for attempt in range(1, max_attempts + 1):
            image = controller.post_screencap().wait().get()
            vacant = find_vacant(context, image, roi, threshold, quad)
            if not vacant:
                print(f"[plant_flowers] 地块{index} 没有识别到空地（第 {attempt} 次）")
                return False

            x, y = center_of(vacant[0])
            controller.post_click(x, y).wait()  # 点空地弹出种植列表
            time.sleep(1.0)

            point = self.find_flower_point(
                context, controller, list_roi, target, name_offset_y, max_list_scrolls, list_scroll
            )
            if point is None:
                print(f"[plant_flowers] 地块{index} 的种植列表里没找到「{target}」")
                return False

            print(f"[plant_flowers] 地块{index} 在花朵图片 {point} 按下，按住不放拖过空地")
            if drag_over_vacant(
                context,
                controller,
                point,
                roi,
                quad,
                threshold,
                max_passes,
                move_steps,
                move_duration,
                first_move_steps,
                first_move_duration,
                hold,
                press_hold,
            ):
                print(f"[plant_flowers] 地块{index} 种植完成")
                return True

            print(f"[plant_flowers] 地块{index} 还有空地残留，重试（第 {attempt} 次）")
            time.sleep(0.5)

        return False

    def find_flower_point(
        self,
        context: Context,
        controller,
        list_roi: list[int],
        target: str,
        name_offset_y: int,
        max_list_scrolls: int,
        list_scroll: dict,
    ) -> tuple[int, int] | None:
        """在种植列表里翻页找目标花名，返回要按下的点（花名文字中心 Y+offset）。"""
        for scroll_index in range(max_list_scrolls + 1):
            image = controller.post_screencap().wait().get()
            texts = ocr_texts(context, image, list_roi)
            box = find_name_box(texts, target)
            if box is not None:
                x, y, w, h = box
                point = (x + w // 2, y + h // 2 + name_offset_y)
                print(f"[plant_flowers] 找到「{target}」文字框={box}，按下点={point}")
                return point

            if scroll_index == max_list_scrolls:
                break
            print(f"[plant_flowers] 列表里没看到「{target}」，上滑翻页（{scroll_index + 1}/{max_list_scrolls}）")
            drag_scroll(controller, list_scroll)
            time.sleep(int(list_scroll["delay"]) / 1000)

        return None
