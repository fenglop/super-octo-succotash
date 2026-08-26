"""OpenCV窗口键盘控制映射。"""


def handle_key(key, motor_enabled):
    # 同时支持大小写WASD/H/R。
    if key in (ord("w"), ord("W")):
        return {
            "action": "forward",
            "manual_mode": True,
            "motor_enabled": motor_enabled,
        }
    if key in (ord("s"), ord("S")):
        return {
            "action": "backward",
            "manual_mode": True,
            "motor_enabled": motor_enabled,
        }
    if key in (ord("a"), ord("A")):
        return {
            "action": "left",
            "manual_mode": True,
            "motor_enabled": motor_enabled,
        }
    if key in (ord("d"), ord("D")):
        return {
            "action": "right",
            "manual_mode": True,
            "motor_enabled": motor_enabled,
        }
    if key == ord(" "):
        # 空格保持在手动停止，避免自动模式立即重新启动电机。
        return {
            "action": "stop",
            "manual_mode": True,
            "motor_enabled": motor_enabled,
        }
    if key in (ord("r"), ord("R")):
        # R显式返回红色目标自动跟随。
        return {
            "action": "stop",
            "manual_mode": False,
            "motor_enabled": motor_enabled,
        }
    if key in (ord("h"), ord("H")):
        return {
            "action": "stop",
            "manual_mode": True,
            "motor_enabled": not motor_enabled,
        }
    return {
        "action": None,
        "manual_mode": None,
        "motor_enabled": motor_enabled,
    }

