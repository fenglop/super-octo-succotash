"""TB6612 单通道软件PWM测试：不导入摄像头，不运行完整小车程序。"""

import argparse
import gc
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Test one TB6612 channel with GPIO.PWM")
    parser.add_argument("--in1", type=int, default=13, help="BCM方向引脚IN1")
    parser.add_argument("--in2", type=int, default=19, help="BCM方向引脚IN2")
    parser.add_argument("--pwm", type=int, default=26, help="BCM PWM引脚")
    parser.add_argument("--frequency", type=int, default=1000, help="PWM频率，默认1000Hz")
    parser.add_argument("--duty", type=float, default=50.0, help="占空比0~100，默认50%%")
    parser.add_argument("--duration", type=float, default=2.0, help="运行时间，最多5秒")
    parser.add_argument(
        "--direction",
        choices=("forward", "backward"),
        default="forward",
        help="测试方向；实际车轮方向由电机接线决定",
    )
    parser.add_argument("--run", action="store_true", help="确认安全后允许启动")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.run:
        raise SystemExit("安全保护：抬起车轮并核对接线后，添加 --run")
    if len({args.in1, args.in2, args.pwm}) != 3:
        raise SystemExit("IN1、IN2和PWM必须使用三个不同GPIO")
    if not 0 < args.frequency <= 20000:
        raise SystemExit("frequency必须在1~20000Hz之间")
    if not 0 <= args.duty <= 100:
        raise SystemExit("duty必须在0~100之间")
    if not 0 < args.duration <= 5:
        raise SystemExit("duration必须大于0且不超过5秒")

    import RPi.GPIO as GPIO

    pins = (args.in1, args.in2, args.pwm)
    pwm = None
    GPIO.setwarnings(True)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pins, GPIO.OUT, initial=GPIO.LOW)

    try:
        if args.direction == "forward":
            GPIO.output(args.in1, GPIO.HIGH)
            GPIO.output(args.in2, GPIO.LOW)
        else:
            GPIO.output(args.in1, GPIO.LOW)
            GPIO.output(args.in2, GPIO.HIGH)

        pwm = GPIO.PWM(args.pwm, args.frequency)
        pwm.start(0)
        print(
            f"PWM开始：IN1=GPIO{args.in1}, IN2=GPIO{args.in2}, "
            f"PWM=GPIO{args.pwm}, frequency={args.frequency}Hz, "
            f"duty={args.duty}%, duration={args.duration}s"
        )
        pwm.ChangeDutyCycle(args.duty)
        time.sleep(args.duration)

    except KeyboardInterrupt:
        print("收到Ctrl+C，立即停止")
    finally:
        # 先将占空比归零并停止PWM，再删除对象，最后清理GPIO。
        # 这样可避免GPIO资源先释放后，PWM析构函数再次访问已关闭句柄。
        if pwm is not None:
            pwm.ChangeDutyCycle(0)
            time.sleep(0.1)
            pwm.stop()
            del pwm
            pwm = None
            gc.collect()

        GPIO.output(args.in1, GPIO.LOW)
        GPIO.output(args.in2, GPIO.LOW)
        GPIO.cleanup(pins)

    print("PWM测试结束，PWM对象已停止并在GPIO清理前释放")


if __name__ == "__main__":
    main()
