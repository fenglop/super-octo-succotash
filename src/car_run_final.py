"""红色目标视觉跟随主程序（GPIO/PWM生命周期修正版）。"""

import argparse
import os
import time

import cv2

import coolspot_motor as motor
from keyboard_control import handle_key
from vision import process_frame, reset_tracking_state


FORWARD_SPEED = 40.0
RAMP_STEP = 10.0
KP = 0.045
KI = 0.0
KD = 0.003
ALPHA_TURN = 0.6


def parse_args():
    parser = argparse.ArgumentParser(description="Red-object following car controller")
    parser.add_argument("--device", type=int, default=0, help="USB摄像头设备号")
    parser.add_argument(
        "--mode",
        choices=("auto", "manual"),
        default="auto",
        help="auto红色目标跟随；manual需要--show并用WASD控制",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="手动窗口模式快捷方式，等价于 --mode manual --show",
    )
    parser.add_argument(
        "--enable-motors",
        dest="enable_motors",
        action="store_true",
        help="启用电机（默认已启用，保留该参数兼容旧命令）",
    )
    parser.add_argument(
        "--vision-only",
        dest="enable_motors",
        action="store_false",
        help="只运行视觉，不初始化GPIO/PWM",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="显示frame/mask窗口；默认关闭以降低VNC和Wi-Fi负载",
    )
    parser.add_argument("--duration", type=float, default=0.0, help="0表示持续运行")
    parser.add_argument("--log-hz", type=float, default=2.0, help="状态日志频率")
    parser.add_argument("--arm-delay", type=float, default=2.0, help="电机启用前等待秒数")
    parser.set_defaults(enable_motors=True)
    return parser.parse_args()


def validate_args(args):
    if args.manual:
        args.mode = "manual"
        args.show = True
    if args.mode == "manual" and not args.show:
        raise SystemExit("manual模式依赖OpenCV窗口键盘事件，必须同时添加 --show")
    if args.show and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise SystemExit("当前会话没有图形显示环境；请去掉 --show 或在本地桌面终端运行")
    if args.duration < 0:
        raise SystemExit("duration不能小于0")
    if not 0 < args.log_hz <= 10:
        raise SystemExit("log-hz必须在0~10Hz之间")
    if not 0 <= args.arm_delay <= 10:
        raise SystemExit("arm-delay必须在0~10秒之间")


def ramp(current, target):
    if current < target:
        return min(current + RAMP_STEP, target)
    if current > target:
        return max(current - RAMP_STEP, target)
    return current


class ControlState:
    def __init__(self, manual_mode):
        self.manual_mode = manual_mode
        self.manual_action = "stop"
        self.current_left_speed = 0.0
        self.current_right_speed = 0.0
        self.in_place_mode = False
        self.cached_turn_speed = 0.0
        self.error_sum = 0.0
        self.last_error = 0.0
        self.smooth_turn = None

    def reset_pid(self):
        self.error_sum = 0.0
        self.last_error = 0.0
        self.smooth_turn = None

    def reset_motion(self):
        self.current_left_speed = 0.0
        self.current_right_speed = 0.0
        self.in_place_mode = False
        self.cached_turn_speed = 0.0
        self.reset_pid()


def pid_control(cx, frame_center, state):
    # 暂时保留原参数含义，后续标定时再统一引入dt。
    error = cx - frame_center
    state.error_sum += error
    derivative = error - state.last_error
    state.last_error = error

    turn_raw = KP * error + KI * state.error_sum + KD * derivative
    if state.smooth_turn is None:
        state.smooth_turn = turn_raw
    else:
        state.smooth_turn = (
            ALPHA_TURN * state.smooth_turn + (1 - ALPHA_TURN) * turn_raw
        )

    left_speed = max(0.0, min(100.0, FORWARD_SPEED + state.smooth_turn))
    right_speed = max(0.0, min(100.0, FORWARD_SPEED - state.smooth_turn))
    return left_speed, right_speed, state.smooth_turn, error


def apply_manual_control(state, motor_enabled):
    if not motor_enabled:
        motor.stop()
        state.reset_motion()
        return "motors disabled"

    if state.manual_action in {"forward", "backward"}:
        target_speed = FORWARD_SPEED
    elif state.manual_action in {"left", "right"}:
        target_speed = 30.0
    else:
        target_speed = 0.0

    state.current_left_speed = ramp(state.current_left_speed, target_speed)
    state.current_right_speed = ramp(state.current_right_speed, target_speed)
    speed = state.current_left_speed

    if state.manual_action == "forward":
        motor.forward(speed)
    elif state.manual_action == "backward":
        motor.backward(speed)
    elif state.manual_action == "left":
        motor.turn_left(speed)
    elif state.manual_action == "right":
        motor.turn_right(speed)
    else:
        motor.stop()
        state.current_left_speed = 0.0
        state.current_right_speed = 0.0

    return f"manual={state.manual_action} speed={speed:.0f}"


def apply_auto_control(state, frame, cx, total_area, motor_enabled):
    if not motor_enabled:
        motor.stop()
        state.reset_motion()
        return "motors disabled"

    if cx == -1:
        state.current_left_speed = ramp(state.current_left_speed, 0.0)
        state.current_right_speed = ramp(state.current_right_speed, 0.0)
        if state.current_left_speed > 0 or state.current_right_speed > 0:
            motor.set_left_right(
                state.current_left_speed,
                state.current_right_speed,
                "forward",
            )
        else:
            motor.stop()
            state.in_place_mode = False
            state.cached_turn_speed = 0.0
        state.reset_pid()
        reset_tracking_state()
        return "auto: no red target -> stop"

    frame_center = frame.shape[1] // 2
    left_speed, right_speed, turn, error = pid_control(cx, frame_center, state)

    if not state.in_place_mode and abs(error) > 100 and 500 < total_area < 2000:
        state.in_place_mode = True
    elif state.in_place_mode and abs(error) < 50:
        state.in_place_mode = False

    if state.in_place_mode:
        state.cached_turn_speed = 0.7 * state.cached_turn_speed + 0.3 * 30.0
        if error > 0:
            motor.turn_right(state.cached_turn_speed)
            direction = "right"
        else:
            motor.turn_left(state.cached_turn_speed)
            direction = "left"
        return (
            f"auto: in-place {direction} error={error} "
            f"speed={state.cached_turn_speed:.0f}"
        )

    state.current_left_speed = ramp(state.current_left_speed, left_speed)
    state.current_right_speed = ramp(state.current_right_speed, right_speed)
    motor.set_left_right(
        state.current_left_speed,
        state.current_right_speed,
        "forward",
    )
    return (
        f"auto: error={error} turn={turn:.2f} "
        f"L={state.current_left_speed:.0f} R={state.current_right_speed:.0f}"
    )


def main():
    args = parse_args()
    validate_args(args)

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise SystemExit(f"无法打开USB摄像头device={args.device}")

    motors_available = False
    motor_enabled = False
    state = ControlState(manual_mode=args.mode == "manual")
    started_at = time.monotonic()
    next_log = started_at
    frames = 0
    failed_frames = 0
    consecutive_failed = 0
    status = "starting"

    try:
        if args.enable_motors:
            motor.initialize(frequency=1000)
            motors_available = True
            print(
                "电机GPIO已按BCM模式初始化；"
                f"{args.arm_delay:.1f}秒后允许输出。按Ctrl+C可停止。"
            )
            time.sleep(args.arm_delay)
            motor_enabled = True
        else:
            print("已启用 --vision-only：只运行视觉，不初始化GPIO/PWM")

        print(
            f"主程序启动：mode={args.mode}, show={args.show}, "
            f"motors={motors_available}, device={args.device}"
        )
        if args.show:
            print("窗口按键：WASD手动，空格保持停止，R返回自动，H动力开关，Q退出")

        while args.duration <= 0 or time.monotonic() - started_at < args.duration:
            ok, frame = cap.read()
            if not ok:
                failed_frames += 1
                consecutive_failed += 1
                if motors_available:
                    motor.stop()
                if consecutive_failed >= 10:
                    raise RuntimeError("摄像头连续10帧读取失败，已停止电机")
                time.sleep(0.05)
                continue

            consecutive_failed = 0
            frames += 1
            position, cx, cy, mask, annotated, total_area = process_frame(frame)

            key = 255
            if args.show:
                # 只显示缩小后的标注画面，每5帧刷新一次，减少VNC负载。
                if frames % 5 == 0:
                    small_frame = cv2.resize(annotated, (320, 240))
                    cv2.imshow("frame", small_frame)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q") or key == ord("Q"):
                    break
                if key != 255:
                    result = handle_key(key, motor_enabled)
                    if result["action"] is not None:
                        state.manual_action = result["action"]
                    if result["manual_mode"] is not None:
                        state.manual_mode = result["manual_mode"]
                    if motors_available:
                        motor_enabled = result["motor_enabled"]
                    else:
                        motor_enabled = False

            if motors_available:
                if state.manual_mode:
                    status = apply_manual_control(state, motor_enabled)
                else:
                    status = apply_auto_control(
                        state,
                        frame,
                        cx,
                        total_area,
                        motor_enabled,
                    )
            else:
                status = f"vision-only position={position} center=({cx},{cy})"

            now = time.monotonic()
            if now >= next_log:
                elapsed = now - started_at
                fps = frames / elapsed if elapsed > 0 else 0.0
                print(
                    f"elapsed={elapsed:.1f}s fps={fps:.1f} frames={frames} "
                    f"failed={failed_frames} area={total_area:.0f} {status}"
                )
                next_log = now + 1.0 / args.log_hz

    except KeyboardInterrupt:
        print("收到Ctrl+C，准备安全退出")
    finally:
        if motors_available:
            motor.cleanup()
        cap.release()
        cv2.destroyAllWindows()
        print(
            f"程序结束：frames={frames} failed={failed_frames}，"
            "摄像头、PWM和GPIO已清理"
        )


if __name__ == "__main__":
    main()
