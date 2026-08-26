"""TB6612 单通道最小测试：不用摄像头、不创建软件PWM对象。"""

import argparse
import time


def parse_args():
    parser = argparse.ArgumentParser(
        description="Drive one TB6612 channel with a fixed HIGH enable signal"
    )
    parser.add_argument("--in1", type=int, default=13, help="BCM方向引脚IN1")
    parser.add_argument("--in2", type=int, default=19, help="BCM方向引脚IN2")
    parser.add_argument("--enable", type=int, default=26, help="BCM使能/PWM引脚")
    parser.add_argument(
        "--direction",
        choices=("forward", "backward"),
        default="forward",
        help="测试方向；实际车轮方向由电机接线决定",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="电机通电时间，默认1秒，安全限制不超过3秒",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="确认车轮悬空且接线无误后，允许启动测试",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.run:
        raise SystemExit(
            "安全保护：必须添加 --run。运行前抬起车轮，并确认使用BCM编号。"
        )
    if not 0 < args.duration <= 3.0:
        raise SystemExit("duration必须大于0且不超过3秒")
    if len({args.in1, args.in2, args.enable}) != 3:
        raise SystemExit("IN1、IN2和P/PWM不能使用同一个GPIO")

    import RPi.GPIO as GPIO

    pins = (args.in1, args.in2, args.enable)
    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pins, GPIO.OUT, initial=GPIO.LOW)

    try:
        print(
            f"单通道测试：IN1=GPIO{args.in1}, IN2=GPIO{args.in2}, "
            f"P=GPIO{args.enable}, direction={args.direction}"
        )
        print("全部引脚先保持LOW 2秒；此时电机不应转动")
        time.sleep(2.0)

        if args.direction == "forward":
            GPIO.output(args.in1, GPIO.HIGH)
            GPIO.output(args.in2, GPIO.LOW)
        else:
            GPIO.output(args.in1, GPIO.LOW)
            GPIO.output(args.in2, GPIO.HIGH)

        print(f"方向已设置，P置HIGH，运行{args.duration}秒")
        GPIO.output(args.enable, GPIO.HIGH)
        time.sleep(args.duration)

    except KeyboardInterrupt:
        print("收到Ctrl+C，立即停止")
    finally:
        # 先关使能，再撤销方向信号。
        GPIO.output(args.enable, GPIO.LOW)
        GPIO.output(args.in1, GPIO.LOW)
        GPIO.output(args.in2, GPIO.LOW)
        time.sleep(0.1)
        GPIO.cleanup(pins)

    print("单通道测试结束，三个控制引脚均已释放")


if __name__ == "__main__":
    main()
