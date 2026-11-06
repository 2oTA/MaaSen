"""浇水：把农田里缺水的土地全部浇一遍。

流程（一轮）：
1. 在农田区域内识别「缺水的地」（只用水滴模板 water drop.png，绿幕掩码）
2. 点一下其中一块，游戏会弹出浇水用的洒水壶
3. 在洒水壶上按下手指，全程不松手
4. 按住不放，逐块移动到缺水格子中心，每到一处停一下等浇水动画
5. 农田里再也识别不到缺水的地就抬手

一轮下来还有没浇到的（比如扫漏了角落），会自动再来一轮，最多 max_rounds 轮。
"""

import json
import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from flower_scan import box_of
from plant_flowers import (
    PLOT_QUADS,
    QUAD_MARGIN,
    center_of,
    inside_quad,
    move_slowly,
)

# 农田整体区域（720x1280）：比 6 块地的并集再宽松一些，镜头稍微缩放/平移也能扫到
DEFAULT_FARM_ROI = [30, 500, 660, 420]


def inside_any_plot(point: tuple[int, int], margin: float = QUAD_MARGIN) -> bool:
    return any(inside_quad(point, quad, margin) for quad in PLOT_QUADS.values())


def find_water_scarce(
    context: Context,
    image,
    roi: list[int],
    threshold: float,
    only_in_plots: bool = True,
) -> list[list[int]]:
    """在农田区域里找缺水的格子，按匹配分数从高到低返回包围盒。

    外接矩形在斜对角方向会和邻居重叠，所以再用四边形过滤一道，
    避免把隔壁地块（甚至地块外的装饰）当成要浇水的目标。
    """
    detail = context.run_recognition(
        "WaterScarceLand",
        image,
        pipeline_override={"WaterScarceLand": {"roi": list(roi), "threshold": threshold}},
    )
    if detail is None or not detail.hit:
        return []
    results = getattr(detail, "filtered_results", None) or detail.all_results or []
    scored = [(box_of(result), float(getattr(result, "score", 0.0))) for result in results]
    if only_in_plots:
        scored = [
            (box, score)
            for box, score in scored
            if inside_any_plot((box[0] + box[2] // 2, box[1] + box[3] // 2))
        ]
    scored.sort(key=lambda item: -item[1])
    return [box for box, _ in scored]


def find_watering_can(
    context: Context,
    image,
    roi: list[int] | None,
    threshold: float,
) -> list[int] | None:
    """找浇水用的洒水壶（默认全屏找，找到分数最高的那个）。"""
    override: dict = {"threshold": threshold}
    if roi:
        override["roi"] = list(roi)
    detail = context.run_recognition(
        "WateringCan",
        image,
        pipeline_override={"WateringCan": override},
    )
    if detail is None or not detail.hit:
        return None
    results = getattr(detail, "filtered_results", None) or detail.all_results or []
    if not results:
        return None
    best = max(results, key=lambda result: float(getattr(result, "score", 0.0)))
    return box_of(best)


def near(a: tuple[int, int], b: tuple[int, int], tolerance: int = 25) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def drag_over_scarce(
    context: Context,
    controller,
    start: tuple[int, int],
    farm_roi: list[int],
    threshold: float,
    only_in_plots: bool,
    max_passes: int,
    move_steps: int,
    move_duration: int,
    press_hold: float,
    hold: float,
) -> tuple[bool, int]:
    """从洒水壶上按下手指，全程不松手地拖过缺水的地。

    返回 (是否浇完, 本轮经过的格子数)。
    """
    position = start
    pressed = False
    watered = 0
    visited: list[tuple[int, int]] = []
    try:
        controller.post_touch_down(start[0], start[1], 0, 1).wait()
        pressed = True
        time.sleep(press_hold)  # 按住不动一下，让游戏确认「拿起」了洒水壶

        for _ in range(max_passes):
            image = controller.post_screencap().wait().get()
            tiles = find_water_scarce(context, image, farm_roi, threshold, only_in_plots)
            # 已经去过、但还没消失的格子不再去（否则会一直在同一块上打转）
            fresh = [box for box in tiles if not any(near(center_of(box), point) for point in visited)]
            if not fresh:
                return True, watered
            target = center_of(fresh[0])
            move_slowly(controller, position, target, move_steps, move_duration)
            position = target
            visited.append(target)
            watered += 1
            time.sleep(hold)
    finally:
        if pressed:
            controller.post_touch_up(0).wait()

    image = controller.post_screencap().wait().get()
    left = find_water_scarce(context, image, farm_roi, threshold, only_in_plots)
    return (not left), watered


@AgentServer.custom_action("water_plots")
class WaterPlots(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = json.loads(argv.custom_action_param or "{}") or {}
        farm_roi = [int(v) for v in (param.get("farm_roi") or DEFAULT_FARM_ROI)]
        water_threshold = float(param.get("water_threshold", 0.65))
        can_threshold = float(param.get("can_threshold", 0.7))
        can_roi = param.get("can_roi")
        only_in_plots = bool(param.get("only_in_plots", True))
        press_hold = float(param.get("press_hold", 0.5))
        hold = float(param.get("hold", 0.35))
        move_steps = int(param.get("move_steps", 6))
        move_duration = int(param.get("move_duration", 500))
        max_passes = int(param.get("max_passes", 16))
        max_rounds = int(param.get("max_rounds", 3))
        click_wait = float(param.get("click_wait", 1.0))

        controller = context.tasker.controller
        total_watered = 0

        for round_index in range(1, max_rounds + 1):
            image = controller.post_screencap().wait().get()
            tiles = find_water_scarce(context, image, farm_roi, water_threshold, only_in_plots)
            if not tiles:
                if round_index == 1:
                    print("[watering] 没有识别到缺水的地，不需要浇水")
                return True

            print(f"[watering] 第 {round_index} 轮：识别到 {len(tiles)} 块缺水的地，点第一块拿洒水壶")
            x, y = center_of(tiles[0])
            controller.post_click(x, y).wait()
            time.sleep(click_wait)

            image = controller.post_screencap().wait().get()
            can = find_watering_can(context, image, can_roi, can_threshold)
            if can is None:
                print("[watering] 点完缺水的地之后没找到洒水壶，停止")
                return False

            cx, cy = center_of(can)
            print(f"[watering] 洒水壶在 {can}，按在 ({cx}, {cy}) 上不松手，开始拖过缺水的地")
            done, watered = drag_over_scarce(
                context,
                controller,
                (cx, cy),
                farm_roi,
                water_threshold,
                only_in_plots,
                max_passes,
                move_steps,
                move_duration,
                press_hold,
                hold,
            )
            total_watered += watered
            print(f"[watering] 第 {round_index} 轮：浇了 {watered} 块，是否浇完={done}")
            if done:
                print(f"[watering] 浇水完成，共处理 {total_watered} 块")
                return True

        image = controller.post_screencap().wait().get()
        left = find_water_scarce(context, image, farm_roi, water_threshold, only_in_plots)
        print(f"[watering] 达到最大轮数，仍有 {len(left)} 块缺水的地没浇到")
        return not left
