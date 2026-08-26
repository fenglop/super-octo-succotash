"""TB6612 四轮电机驱动。

统一使用 BCM 编号。模块导入时不碰 GPIO，必须显式调用 initialize()。
"""

import gc


# ===== 实物位置与 BCM GPIO 映射 =====
# LB = 左前轮，驱动板通道3，物理针脚 11 / 13 / 22
IN1_LB, IN2_LB, PWM_LB = 17, 27, 25
# RF = 左后轮，驱动板通道4，物理针脚 15 / 16 / 18
IN1_RF, IN2_RF, PWM_RF = 22, 23, 24
# LF = 右后轮，驱动板通道2，物理针脚 29 / 31 / 32
IN1_LF, IN2_LF, PWM_LF = 5, 6, 12
# RB = 右前轮，驱动板通道1，物理针脚 33 / 35 / 37
IN1_RB, IN2_RB, PWM_RB = 13, 19, 26

WHEELS = {
    "left_front": (IN1_LB, IN2_LB, PWM_LB),
    "left_rear": (IN1_RF, IN2_RF, PWM_RF),
    "right_front": (IN1_RB, IN2_RB, PWM_RB),
    "right_rear": (IN1_LF, IN2_LF, PWM_LF),
}

# 现场曾观察到同一方向电平下左侧前进、右侧后退，因此先反转右侧。
# 如果后续逐轮验证结果不同，只修改这里的布尔值，不交换GPIO常量。
DIRECTION_INVERTED = {
    PWM_LB: False,
    PWM_RF: False,
    PWM_RB: True,
    PWM_LF: True,
}

PINS = [pin for in1, in2, _pwm in WHEELS.values() for pin in (in1, in2)]
PWM_PINS = [PWM_LB, PWM_RF, PWM_RB, PWM_LF]
ALL_PINS = PINS + PWM_PINS

GPIO = None
pwm = {}
_initialized = False
_last_direction = {pin: "stop" for pin in PWM_PINS}


def initialize(frequency=1000):
    """初始化GPIO和四个软件PWM对象；重复调用不会重复创建资源。"""
    global GPIO, _initialized

    if _initialized:
        return
    if not 1 <= int(frequency) <= 20000:
        raise ValueError("PWM frequency must be between 1 and 20000 Hz")

    import RPi.GPIO as gpio_module

    GPIO = gpio_module
    controllers = []
    try:
        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ALL_PINS, GPIO.OUT, initial=GPIO.LOW)

        for pin in PWM_PINS:
            controller = GPIO.PWM(pin, int(frequency))
            controller.start(0)
            controllers.append(controller)
            pwm[pin] = controller
        del controller
        _initialized = True
    except Exception:
        for controller in controllers:
            try:
                controller.stop()
            except Exception:
                pass
        if controllers:
            del controller
        controllers.clear()
        pwm.clear()
        gc.collect()
        try:
            GPIO.cleanup()
        except Exception:
            pass
        GPIO = None
        raise


def is_initialized():
    return _initialized


def _require_initialized():
    if not _initialized:
        raise RuntimeError("motor GPIO is not initialized; call initialize() first")


def _clamp_speed(speed):
    return max(0.0, min(100.0, float(speed)))


def _electrical_direction(pwm_pin, direction):
    if direction not in {"forward", "backward", "stop"}:
        raise ValueError(f"unsupported direction: {direction}")
    if direction == "stop" or not DIRECTION_INVERTED[pwm_pin]:
        return direction
    return "backward" if direction == "forward" else "forward"


def set_wheel(in1, in2, pwm_pin, speed, direction):
    """设置单轮；direction表示车体方向，内部负责每轮电气极性。"""
    _require_initialized()
    if pwm_pin not in pwm:
        raise ValueError(f"unknown PWM pin: GPIO{pwm_pin}")

    speed = _clamp_speed(speed)
    electrical = _electrical_direction(pwm_pin, direction)

    # 方向发生变化时先撤销PWM，避免带占空比直接反向。
    if _last_direction[pwm_pin] != electrical:
        pwm[pwm_pin].ChangeDutyCycle(0)

    if electrical == "forward":
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)
    elif electrical == "backward":
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)
    else:
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.LOW)
        speed = 0.0

    pwm[pwm_pin].ChangeDutyCycle(speed)
    _last_direction[pwm_pin] = electrical


def set_left_right(left_speed, right_speed, direction="forward"):
    """按车体左右侧设置差速。"""
    set_wheel(IN1_LB, IN2_LB, PWM_LB, left_speed, direction)
    set_wheel(IN1_RF, IN2_RF, PWM_RF, left_speed, direction)
    set_wheel(IN1_RB, IN2_RB, PWM_RB, right_speed, direction)
    set_wheel(IN1_LF, IN2_LF, PWM_LF, right_speed, direction)


def forward(speed=60):
    set_left_right(speed, speed, "forward")


def backward(speed=60):
    set_left_right(speed, speed, "backward")


def turn_left(speed=50):
    set_wheel(IN1_LB, IN2_LB, PWM_LB, speed, "backward")
    set_wheel(IN1_RF, IN2_RF, PWM_RF, speed, "backward")
    set_wheel(IN1_RB, IN2_RB, PWM_RB, speed, "forward")
    set_wheel(IN1_LF, IN2_LF, PWM_LF, speed, "forward")


def turn_right(speed=50):
    set_wheel(IN1_LB, IN2_LB, PWM_LB, speed, "forward")
    set_wheel(IN1_RF, IN2_RF, PWM_RF, speed, "forward")
    set_wheel(IN1_RB, IN2_RB, PWM_RB, speed, "backward")
    set_wheel(IN1_LF, IN2_LF, PWM_LF, speed, "backward")


def stop():
    if not _initialized:
        return
    for controller in pwm.values():
        controller.ChangeDutyCycle(0)
    for pin in PINS:
        GPIO.output(pin, GPIO.LOW)
    for pin in PWM_PINS:
        _last_direction[pin] = "stop"


def cleanup():
    """先释放PWM对象，再清理GPIO，避免PWM.__del__访问已关闭句柄。"""
    global GPIO, _initialized

    if not _initialized:
        return

    controllers = list(pwm.values())
    try:
        stop()
        for controller in controllers:
            controller.stop()
        if controllers:
            del controller

        pwm.clear()
        controllers.clear()
        gc.collect()
        GPIO.cleanup(ALL_PINS)
    finally:
        pwm.clear()
        _initialized = False
        GPIO = None

