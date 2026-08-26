"""TB6612四通道软件PWM测试：先逐轮验证，再测试四轮并发。"""

import argparse
import gc
import time


# BCM编号。名称沿用当前实物位置，不沿用旧代码中容易混淆的LB/RF/LF/RB缩写。
WHEELS = {
    # 左侧电机：车体前进时IN1=HIGH、IN2=LOW。
    "left_front": {"label": "LB/通道3", "in1": 17, "in2": 27, "pwm": 25, "invert": False},
    "left_rear": {"label": "RF/通道4", "in1": 22, "in2": 23, "pwm": 24, "invert": False},
    # 右侧电机镜像安装：车体前进时需要反转方向电平。
    "right_front": {"label": "RB/通道1", "in1": 13, "in2": 19, "pwm": 26, "invert": True},
    "right_rear": {"label": "LF/通道2", "in1": 5, "in2": 6, "pwm": 12, "invert": True},
}


def parse_args():
    parser = argparse.ArgumentParser(description="Test four TB6612 motor channels")
    parser.add_argument(
        "--mode",
        choices=("sequential", "all"),
        default="sequential",
        help="sequential逐轮测试；all四轮同时测试",
    )
    parser.add_argument("--frequency", type=int, default=1000, help="PWM频率")
    parser.add_argument("--duty", type=float, default=50.0, help="占空比0~100")
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="逐轮时为每轮时间，并发时为总时间；最多3秒",
    )
    parser.add_argument("--run", action="store_true", help="确认安全后允许启动")
    return parser.parse_args()


def validate(args):
    if not args.run:
        raise SystemExit("安全保护：抬起四个车轮并核对全部接线后，添加 --run")
    if not 0 < args.frequency <= 20000:
        raise SystemExit("frequency必须在1~20000Hz之间")
    if not 0 <= args.duty <= 100:
        raise SystemExit("duty必须在0~100之间")
    if not 0 < args.duration <= 3:
        raise SystemExit("duration必须大于0且不超过3秒")

    used_pins = []
    for config in WHEELS.values():
        used_pins.extend((config["in1"], config["in2"], config["pwm"]))
    if len(used_pins) != len(set(used_pins)):
        raise SystemExit("四通道配置中存在重复GPIO，请先检查WHEELS映射")


def main():
    args = parse_args()
    validate(args)

    import RPi.GPIO as GPIO

    all_pins = []
    pwm_objects = {}
    for config in WHEELS.values():
        all_pins.extend((config["in1"], config["in2"], config["pwm"]))

    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(all_pins, GPIO.OUT, initial=GPIO.LOW)

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
            f"四通道PWM已建立：mode={args.mode}, frequency={args.frequency}Hz, "
            f"duty={args.duty}%, duration={args.duration}s"
        )

        if args.mode == "sequential":
            for name, config in WHEELS.items():
                print(
                    f"测试{name} ({config['label']}): IN1=GPIO{config['in1']}, "
                    f"IN2=GPIO{config['in2']}, PWM=GPIO{config['pwm']}, "
                    f"invert={config['invert']}"
                )
                pwm_objects[name].ChangeDutyCycle(args.duty)
                time.sleep(args.duration)
                pwm_objects[name].ChangeDutyCycle(0)
                time.sleep(0.5)
        else:
            print("四轮同时启动")
            for controller in pwm_objects.values():
                controller.ChangeDutyCycle(args.duty)
            del controller
            time.sleep(args.duration)
            for controller in pwm_objects.values():
                controller.ChangeDutyCycle(0)
            del controller

    except KeyboardInterrupt:
        print("收到Ctrl+C，立即停止")
    finally:
        # PWM对象必须在GPIO.cleanup之前全部停止并释放。
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

    print("四通道PWM测试结束，PWM对象已在GPIO清理前释放")


if __name__ == "__main__":
    main()
