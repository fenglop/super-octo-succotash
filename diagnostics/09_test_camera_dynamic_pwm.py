"""USB摄像头与四路动态PWM组合测试，不进行视觉识别或PID计算。"""

import argparse
import gc
import time

import cv2


WHEELS = {
    "left_front": {"side": "left", "in1": 17, "in2": 27, "pwm": 25, "invert": False},
    "left_rear": {"side": "left", "in1": 22, "in2": 23, "pwm": 24, "invert": False},
    "right_front": {"side": "right", "in1": 13, "in2": 19, "pwm": 26, "invert": True},
    "right_rear": {"side": "right", "in1": 5, "in2": 6, "pwm": 12, "invert": True},
}


def parse_args():
    parser = argparse.ArgumentParser(description="Camera + dynamic four-PWM test")
    parser.add_argument("--device", type=int, default=0, help="USB摄像头设备号")
    parser.add_argument("--duration", type=float, default=20.0, help="运行时间，最多60秒")
    parser.add_argument("--frequency", type=int, default=1000, help="PWM载波频率")
    parser.add_argument("--update-hz", type=float, default=20.0, help="占空比更新频率")
    parser.add_argument("--min-duty", type=float, default=40.0, help="最低占空比")
    parser.add_argument("--max-duty", type=float, default=65.0, help="最高占空比")
    parser.add_argument("--step", type=float, default=1.0, help="每次占空比变化量")
    parser.add_argument("--run", action="store_true", help="确认四轮悬空后允许启动")
    return parser.parse_args()


def validate(args):
    if not args.run:
        raise SystemExit("安全保护：必须将四个车轮悬空并添加 --run")
    if not 0 < args.duration <= 60:
        raise SystemExit("duration必须大于0且不超过60秒")
    if not 0 < args.frequency <= 20000:
        raise SystemExit("frequency必须在1~20000Hz之间")
    if not 0 < args.update_hz <= 100:
        raise SystemExit("update-hz必须在0~100Hz之间")
    if not 0 <= args.min_duty < args.max_duty <= 70:
        raise SystemExit("占空比必须满足0 <= min-duty < max-duty <= 70")
    if not 0 < args.step <= args.max_duty - args.min_duty:
        raise SystemExit("step必须大于0且不超过占空比范围")


def main():
    args = parse_args()
    validate(args)

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        cap.release()
        raise SystemExit(f"无法打开USB摄像头device={args.device}，电机未启动")

    for _ in range(10):
        ok, _frame = cap.read()
        if not ok:
            cap.release()
            raise SystemExit("摄像头预热读帧失败，电机未启动")

    import RPi.GPIO as GPIO

    all_pins = []
    pwm_objects = {}
    for config in WHEELS.values():
        all_pins.extend((config["in1"], config["in2"], config["pwm"]))

    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(all_pins, GPIO.OUT, initial=GPIO.LOW)

    frames = 0
    failed = 0
    consecutive_failed = 0
    updates = 0
    duty = args.min_duty
    delta = args.step
    update_period = 1.0 / args.update_hz
    started_at = time.monotonic()
    next_update = started_at
    next_report = started_at + 1.0

    try:
        for name, config in WHEELS.items():
            if config["invert"]:
                GPIO.output(config["in1"], GPIO.LOW)
                GPIO.output(config["in2"], GPIO.HIGH)
            else:
                GPIO.output(config["in1"], GPIO.HIGH)
                GPIO.output(config["in2"], GPIO.LOW)
            controller = GPIO.PWM(config["pwm"], args.frequency)
            controller.start(0)
            pwm_objects[name] = controller
        del controller

        print(
            f"组合测试开始：camera={args.device}, 640x480, pwm={args.frequency}Hz, "
            f"update_hz={args.update_hz}, duty={args.min_duty}~{args.max_duty}%, "
            f"duration={args.duration}s"
        )

        while time.monotonic() - started_at < args.duration:
            ok, _frame = cap.read()
            if ok:
                frames += 1
                consecutive_failed = 0
            else:
                failed += 1
                consecutive_failed += 1
                if consecutive_failed >= 10:
                    raise RuntimeError("摄像头连续10帧读取失败")

            now = time.monotonic()
            if now >= next_update:
                right_duty = args.min_duty + args.max_duty - duty
                for name, controller in pwm_objects.items():
                    side_duty = duty if WHEELS[name]["side"] == "left" else right_duty
                    controller.ChangeDutyCycle(side_duty)
                del controller
                updates += 1

                duty += delta
                if duty >= args.max_duty:
                    duty = args.max_duty
                    delta = -args.step
                elif duty <= args.min_duty:
                    duty = args.min_duty
                    delta = args.step
                next_update += update_period
                if next_update < now:
                    next_update = now + update_period

            if now >= next_report:
                elapsed = now - started_at
                print(
                    f"elapsed={elapsed:5.1f}s fps={frames / elapsed:5.1f} "
                    f"frames={frames} failed={failed} updates={updates} duty={duty:4.1f}%"
                )
                next_report = now + 1.0

    except KeyboardInterrupt:
        print("收到Ctrl+C，立即停止")
    finally:
        for controller in pwm_objects.values():
            controller.ChangeDutyCycle(0)
        if pwm_objects:
            del controller
        time.sleep(0.1)
        for controller in pwm_objects.values():
            controller.stop()
        if pwm_objects:
            del controller
        pwm_objects.clear()
        gc.collect()

        GPIO.output(all_pins, GPIO.LOW)
        GPIO.cleanup(all_pins)
        cap.release()

    elapsed = time.monotonic() - started_at
    print(
        f"组合测试结束：elapsed={elapsed:.1f}s frames={frames} failed={failed} "
        f"updates={updates}，资源已清理"
    )


if __name__ == "__main__":
    main()
