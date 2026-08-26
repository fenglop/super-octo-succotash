"""USB摄像头与四路软件PWM组合稳定性测试，不评价车轮运动方向。"""

import argparse
import gc
import time

import cv2


# 这里只用于产生四路电机负载；方向极性尚未完成实车确认。
WHEELS = {
    "left_front": {"in1": 17, "in2": 27, "pwm": 25, "invert": False},
    "left_rear": {"in1": 22, "in2": 23, "pwm": 24, "invert": False},
    "right_front": {"in1": 13, "in2": 19, "pwm": 26, "invert": True},
    "right_rear": {"in1": 5, "in2": 6, "pwm": 12, "invert": True},
}


def parse_args():
    parser = argparse.ArgumentParser(description="USB camera + four PWM isolation test")
    parser.add_argument("--device", type=int, default=0, help="USB摄像头设备号")
    parser.add_argument("--duration", type=float, default=10.0, help="组合运行时间，最多30秒")
    parser.add_argument("--frequency", type=int, default=1000, help="PWM频率")
    parser.add_argument("--duty", type=float, default=40.0, help="四路占空比，默认40%%")
    parser.add_argument("--run", action="store_true", help="确认车轮悬空后允许启动")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.run:
        raise SystemExit("安全保护：必须将四个车轮悬空并添加 --run")
    if not 0 < args.duration <= 30:
        raise SystemExit("duration必须大于0且不超过30秒")
    if not 0 < args.frequency <= 20000:
        raise SystemExit("frequency必须在1~20000Hz之间")
    if not 0 <= args.duty <= 70:
        raise SystemExit("本测试将duty限制在0~70之间")

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        cap.release()
        raise SystemExit(f"无法打开USB摄像头device={args.device}，电机未启动")

    # 先确认摄像头能读帧，成功后才配置并启动电机。
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
    started_at = time.monotonic()
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

        for controller in pwm_objects.values():
            controller.ChangeDutyCycle(args.duty)
        del controller
        print(
            f"组合测试开始：camera={args.device}, 640x480, four_pwm={args.frequency}Hz, "
            f"duty={args.duty}%, duration={args.duration}s"
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
            if now >= next_report:
                elapsed = now - started_at
                print(
                    f"elapsed={elapsed:5.1f}s fps={frames / elapsed:5.1f} "
                    f"frames={frames} failed={failed}"
                )
                next_report = now + 1.0

    except KeyboardInterrupt:
        print("收到Ctrl+C，立即停止")
    finally:
        # 先停止并释放全部PWM对象，再清理GPIO和摄像头。
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
        f"组合测试结束：elapsed={elapsed:.1f}s frames={frames} failed={failed}，"
        "PWM和GPIO已清理"
    )


if __name__ == "__main__":
    main()
