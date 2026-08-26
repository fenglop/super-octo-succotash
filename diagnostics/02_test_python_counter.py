"""普通 Python 运行测试：只做数字加减，不访问摄像头和 GPIO。"""

import argparse
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Pure Python counter isolation test")
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="测试秒数；0表示一直运行到Ctrl+C",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="每次加减后的等待秒数，默认0.1",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    number = 0
    direction = 1
    operations = 0
    start = time.monotonic()
    last_report = start

    print("普通Python测试开始：不导入OpenCV，不导入GPIO")
    print(f"duration={args.duration}s, interval={args.interval}s")

    try:
        while True:
            number += direction
            operations += 1

            if number >= 100:
                direction = -1
            elif number <= 0:
                direction = 1

            now = time.monotonic()
            if now - last_report >= 1.0:
                print(
                    f"elapsed={now - start:6.1f}s "
                    f"number={number:3d} operations={operations}"
                )
                last_report = now

            if args.duration > 0 and now - start >= args.duration:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("收到Ctrl+C，结束测试")

    print(f"普通Python测试结束：number={number}, operations={operations}")


if __name__ == "__main__":
    main()

