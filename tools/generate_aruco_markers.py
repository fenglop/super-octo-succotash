from pathlib import Path

import cv2
import numpy as np


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "aruco_markers_0_9"
MARKER_SIZE = 500
QUIET_ZONE = 80
SHEET_CELL_W = 760
SHEET_CELL_H = 760


def make_marker(dictionary: cv2.aruco.Dictionary, marker_id: int) -> np.ndarray:
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_SIZE)
    canvas = np.full(
        (MARKER_SIZE + 2 * QUIET_ZONE, MARKER_SIZE + 2 * QUIET_ZONE),
        255,
        dtype=np.uint8,
    )
    canvas[QUIET_ZONE : QUIET_ZONE + MARKER_SIZE, QUIET_ZONE : QUIET_ZONE + MARKER_SIZE] = marker
    return canvas


def make_print_sheet(markers: list[np.ndarray]) -> np.ndarray:
    sheet = np.full((2 * SHEET_CELL_H, 5 * SHEET_CELL_W, 3), 255, dtype=np.uint8)
    for index, marker in enumerate(markers):
        row, col = divmod(index, 5)
        cell_x = col * SHEET_CELL_W
        cell_y = row * SHEET_CELL_H
        marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        x = cell_x + (SHEET_CELL_W - marker.shape[1]) // 2
        y = cell_y + 20
        sheet[y : y + marker.shape[0], x : x + marker.shape[1]] = marker_bgr
        cv2.putText(
            sheet,
            f"ArUco ID {index}",
            (cell_x + 205, cell_y + 710),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
    return sheet


def save_png(path: Path, image: np.ndarray) -> None:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError(f"Could not encode PNG: {path}")
    encoded.tofile(str(path))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    markers = []
    for marker_id in range(10):
        marker = make_marker(dictionary, marker_id)
        markers.append(marker)
        save_png(OUTPUT_DIR / f"aruco_4x4_50_id_{marker_id}.png", marker)

    sheet = make_print_sheet(markers)
    save_png(OUTPUT_DIR / "aruco_4x4_50_ids_0_to_9_print_sheet.png", sheet)

    (OUTPUT_DIR / "README.txt").write_text(
        "ArUco markers ID 0-9\n"
        "Dictionary: DICT_4X4_50\n"
        "Individual PNGs include an 80 px white quiet zone around a 500 px marker.\n"
        "Use the same DICT_4X4_50 dictionary during detection.\n",
        encoding="utf-8",
    )
    print(f"Generated 10 markers and 1 print sheet in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
