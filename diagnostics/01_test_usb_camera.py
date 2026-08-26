"""USB 摄像头最小测试：只使用 OpenCV，不导入 GPIO 或电机模块。"""

import argparse
import time

import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="USB camera isolation test")
    parser.add_argument("--device", type=int, default=0, help="摄像头编号，默认0")
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="测试秒数；0表示一直运行到Ctrl+C或q",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="不显示窗口，只持续读取帧，适合SSH测试",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cap = cv2.VideoCapture(args.device)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        raise RuntimeError(f"无法打开USB摄像头设备 {args.device}")

    print("USB摄像头测试开始：不导入GPIO，不控制电机")
    print(f"device={args.device}, headless={args.headless}, duration={args.duration}s")

    start = time.monotonic()
    report_start = start
    frames_in_period = 0
    total_frames = 0
    failed_reads = 0

    try:
        while True:
            ok, frame = cap.read()
            now = time.monotonic()

            if not ok:
                failed_reads += 1
                print(f"读取失败，累计次数={failed_reads}")
                time.sleep(0.05)
                continue

            total_frames += 1
            frames_in_period += 1

            if not args.headless:
                cv2.imshow("USB camera test - press q to quit", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

            if now - report_start >= 1.0:
                fps = frames_in_period / (now - report_start)
                height, width = frame.shape[:2]
                print(
                    f"elapsed={now - start:6.1f}s "
                    f"fps={fps:5.1f} resolution={width}x{height} "
                    f"frames={total_frames} failed={failed_reads}"
                )
                report_start = now
                frames_in_period = 0

            if args.duration > 0 and now - start >= args.duration:
                break

    except KeyboardInterrupt:
        print("收到Ctrl+C，结束测试")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"USB摄像头测试结束：frames={total_frames}, failed={failed_reads}")


if __name__ == "__main__":
    main()

