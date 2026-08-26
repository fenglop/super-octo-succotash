"""GPIO 最小测试：不导入OpenCV，不创建PWM对象，不控制完整电机程序。"""

import argparse
import time


def parse_args():
    parser = argparse.ArgumentParser(description="GPIO isolation test without PWM")
    parser.add_argument(
        "--mode",
        choices=("import-only", "setup-only", "toggle"),
        default="import-only",
        help="依次测试：只导入、配置输出、切换高低电平",
    )
    parser.add_argument("--pin", type=int, default=26, help="BCM编号，默认GPIO26")
    parser.add_argument("--duration", type=float, default=30.0, help="setup-only保持时间")
    parser.add_argument("--cycles", type=int, default=10, help="toggle循环次数")
    parser.add_argument("--interval", type=float, default=0.5, help="高/低电平持续时间")
    parser.add_argument(
        "--run",
        action="store_true",
        help="确认接线安全后允许配置或切换GPIO",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    import RPi.GPIO as GPIO

    print("GPIO库导入成功")
    print(f"module={getattr(GPIO, '__file__', 'unknown')}")
    print(f"version={getattr(GPIO, 'VERSION', 'unknown')}")

    if args.mode == "import-only":
        print("import-only完成：没有配置或输出任何GPIO")
        return

    if not args.run:
        raise SystemExit(
            "安全保护：setup-only或toggle必须添加 --run。"
            "先确认使用的是BCM编号，且该线没有接到5V、12V或驱动板输出端。"
        )

    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(args.pin, GPIO.OUT, initial=GPIO.LOW)

    try:
        if args.mode == "setup-only":
            print(
                f"GPIO{args.pin}已配置为输出并保持低电平，"
                f"持续{args.duration}s"
            )
            time.sleep(args.duration)
        else:
            print(
                f"开始切换BCM GPIO{args.pin}：cycles={args.cycles}, "
                f"interval={args.interval}s"
            )
            for index in range(1, args.cycles + 1):
                GPIO.output(args.pin, GPIO.HIGH)
                print(f"cycle={index}: HIGH")
                time.sleep(args.interval)

                GPIO.output(args.pin, GPIO.LOW)
                print(f"cycle={index}: LOW")
                time.sleep(args.interval)

    except KeyboardInterrupt:
        print("收到Ctrl+C，结束测试")
    finally:
        GPIO.output(args.pin, GPIO.LOW)
        GPIO.cleanup(args.pin)

    print("GPIO测试结束")


if __name__ == "__main__":
    main()

