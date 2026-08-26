"""红色目标检测：返回位置、中心点、掩膜、标注帧和有效面积。"""

import argparse
import time

import cv2
import numpy as np


LOWER_RED_1 = np.array([0, 100, 80])
UPPER_RED_1 = np.array([10, 255, 255])
LOWER_RED_2 = np.array([160, 100, 80])
UPPER_RED_2 = np.array([180, 255, 255])

MIN_AREA = 800
CENTER_TOLERANCE = 50
KERNEL_OPEN = np.ones((5, 5), np.uint8)
KERNEL_CLOSE = np.ones((9, 9), np.uint8)
BLUR_KERNEL_SIZE = (9, 9)
SMOOTH_ALPHA = 0.7


def reset_tracking_state():
    """清除目标中心平滑缓存。"""
    for attribute in ("smooth_cx", "smooth_cy"):
        if hasattr(process_frame, attribute):
            delattr(process_frame, attribute)


def process_frame(frame):
    """处理一帧BGR图像。

    返回：position, cx, cy, mask, frame_annotated, total_area
    """
    if frame is None or frame.size == 0:
        raise ValueError("frame is empty")

    height, width = frame.shape[:2]
    frame_center = width // 2
    position = "No Object"
    cx, cy = -1, -1
    valid_contours = []

    frame_blurred = cv2.GaussianBlur(frame, BLUR_KERNEL_SIZE, 0)
    hsv = cv2.cvtColor(frame_blurred, cv2.COLOR_BGR2HSV)
    mask_1 = cv2.inRange(hsv, LOWER_RED_1, UPPER_RED_1)
    mask_2 = cv2.inRange(hsv, LOWER_RED_2, UPPER_RED_2)
    mask = cv2.bitwise_or(mask_1, mask_2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, KERNEL_OPEN)
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, KERNEL_CLOSE, iterations=3
    )

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    total_area = 0.0
    weighted_cx = 0.0
    weighted_cy = 0.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area <= MIN_AREA:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue

        contour_cx = moments["m10"] / moments["m00"]
        contour_cy = moments["m01"] / moments["m00"]
        weighted_cx += contour_cx * area
        weighted_cy += contour_cy * area
        total_area += area
        valid_contours.append(contour)

    if total_area > 0:
        measured_cx = int(weighted_cx / total_area)
        measured_cy = int(weighted_cy / total_area)

        if not hasattr(process_frame, "smooth_cx"):
            process_frame.smooth_cx = measured_cx
            process_frame.smooth_cy = measured_cy
        else:
            process_frame.smooth_cx = int(
                SMOOTH_ALPHA * process_frame.smooth_cx
                + (1 - SMOOTH_ALPHA) * measured_cx
            )
            process_frame.smooth_cy = int(
                SMOOTH_ALPHA * process_frame.smooth_cy
                + (1 - SMOOTH_ALPHA) * measured_cy
            )

        cx = process_frame.smooth_cx
        cy = process_frame.smooth_cy
        if cx < frame_center - CENTER_TOLERANCE:
            position = "Left"
        elif cx > frame_center + CENTER_TOLERANCE:
            position = "Right"
        else:
            position = "Center"
    else:
        # 目标丢失后不保留旧中心，避免再次识别时被历史位置拖慢。
        reset_tracking_state()

    frame_annotated = frame.copy()
    if valid_contours:
        all_points = np.concatenate(valid_contours)
        hull = cv2.convexHull(all_points)
        cv2.drawContours(frame_annotated, [hull], -1, (0, 255, 0), 2)

    left_boundary = frame_center - CENTER_TOLERANCE
    right_boundary = frame_center + CENTER_TOLERANCE
    cv2.line(
        frame_annotated,
        (frame_center, 0),
        (frame_center, height),
        (255, 255, 255),
        1,
    )
    cv2.line(
        frame_annotated,
        (left_boundary, 0),
        (left_boundary, height),
        (128, 128, 128),
        1,
    )
    cv2.line(
        frame_annotated,
        (right_boundary, 0),
        (right_boundary, height),
        (128, 128, 128),
        1,
    )

    if cx != -1:
        cv2.circle(frame_annotated, (cx, cy), 5, (255, 0, 0), -1)
        cv2.putText(
            frame_annotated,
            f"({cx}, {cy})",
            (cx + 10, cy - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )

    cv2.putText(
        frame_annotated,
        f"Position: {position}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 0, 255),
        2,
    )

    return position, cx, cy, mask, frame_annotated, total_area


def parse_args():
    parser = argparse.ArgumentParser(description="Standalone red-object vision test")
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--duration", type=float, default=0.0)
    return parser.parse_args()


def main():
    args = parse_args()
    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit(f"无法打开USB摄像头device={args.device}")

    started_at = time.monotonic()
    frames = 0
    next_report = started_at + 1.0
    try:
        while args.duration <= 0 or time.monotonic() - started_at < args.duration:
            ok, frame = cap.read()
            if not ok:
                print("读取摄像头失败")
                break

            position, cx, cy, mask, annotated, area = process_frame(frame)
            frames += 1
            now = time.monotonic()
            if now >= next_report:
                print(
                    f"frames={frames} position={position} center=({cx},{cy}) "
                    f"area={area:.0f}"
                )
                next_report = now + 1.0

            if not args.headless:
                cv2.imshow("frame", annotated)
                cv2.imshow("mask", mask)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("收到Ctrl+C，结束视觉测试")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

