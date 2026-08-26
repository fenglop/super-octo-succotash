"""逐通道短转电机，用于确认四个驱动通道对应的实际车轮位置。"""

import argparse
import time

import coolspot_motor as motor


CHANNELS = {
    1: ("通道1 / 当前计划右前RB", motor.IN1_RB, motor.IN2_RB, motor.PWM_RB),
    2: ("通道2 / 当前计划右后LF", motor.IN1_LF, motor.IN2_LF, motor.PWM_LF),
    3: ("通道3 / 当前计划左前LB", motor.IN1_LB, motor.IN2_LB, motor.PWM_LB),
    4: ("通道4 / 当前计划左后RF", motor.IN1_RF, motor.IN2_RF, motor.PWM_RF),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Test wheel positions one channel at a time")
    parser.add_argument(
        "--channel",
        choices=("all", "1", "2", "3", "4"),
        default="all",
        help="默认依次测试全部通道，也可只测1~4中的一个",
    )
    parser.add_argument("--speed", type=float, default=45.0, help="占空比，默认45%%")
    parser.add_argument("--duration", type=float, default=1.0, help="每次转动时间，最多3秒")
    parser.add_argument("--yes", action="store_true", help="跳过START安全确认")
    return parser.parse_args()


def validate(args):
    if not 0 < args.speed <= 70:
        raise SystemExit("speed必须大于0且不超过70")
    if not 0 < args.duration <= 3:
        raise SystemExit("duration必须大于0且不超过3秒")


def main():
    args = parse_args()
    validate(args)

    selected = list(CHANNELS) if args.channel == "all" else [int(args.channel)]
    print("本程序只用于确认车轮位置，不判断最终前进方向。")
    print("测试前必须：关闭其他小车程序、连接好电机、抬起四轮、禁止带电换线。")
    print("当前控制通道：")
    for channel in selected:
        label, in1, in2, pwm_pin = CHANNELS[channel]
        print(f"  {label}: IN1=GPIO{in1}, IN2=GPIO{in2}, PWM=GPIO{pwm_pin}")

    if not args.yes:
        confirmation = input("确认四轮悬空且接线固定后，输入 START：").strip()
        if confirmation != "START":
            raise SystemExit("未输入START，测试取消")

    motor.initialize(frequency=1000)
    observations = []
    try:
        for channel in selected:
            label, in1, in2, pwm_pin = CHANNELS[channel]
            command = input(
                f"\n准备测试{label}。按Enter短转，输入q结束："
            ).strip().lower()
            if command == "q":
                break

            print(f"{label}开始转动 {args.duration:.1f}s")
            motor.set_wheel(in1, in2, pwm_pin, args.speed, "forward")
            time.sleep(args.duration)
            motor.stop()
            actual = input(
                "刚才实际转动的位置（左前/左后/右前/右后/未知）："
            ).strip()
            observations.append((channel, label, actual or "未记录"))

    except KeyboardInterrupt:
        print("\n收到Ctrl+C，立即停止")
    finally:
        motor.cleanup()

    print("\n测试记录：")
    for channel, label, actual in observations:
        print(f"  通道{channel}: {label} -> 实际{actual}")
    print("GPIO和PWM已清理。调整电机线前必须先关闭驱动板电源。")


if __name__ == "__main__":
    main()

