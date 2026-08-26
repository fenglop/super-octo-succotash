# 智能小车掉网隔离测试

这三个脚本用于判断掉网从哪一层开始出现，测试时不要同时运行 `car_run_final.py`。

## 1. USB摄像头

有显示器时：

```bash
python3 01_test_usb_camera.py --device 0 --duration 60
```

通过SSH只读帧、不显示窗口：

```bash
python3 01_test_usb_camera.py --device 0 --duration 60 --headless
```

## 2. 普通Python加减数字

```bash
python3 02_test_python_counter.py --duration 60
```

## 3. GPIO分级测试

先关闭驱动板电源，并从驱动板一端拔掉GPIO26对应的控制线。

只导入GPIO库：

```bash
python3 03_test_gpio_basic.py --mode import-only
```

将BCM GPIO26配置为低电平输出：

```bash
sudo python3 03_test_gpio_basic.py --mode setup-only --pin 26 --duration 30 --run
```

切换GPIO26高低电平：

```bash
sudo python3 03_test_gpio_basic.py --mode toggle --pin 26 --cycles 10 --interval 0.5 --run
```

GPIO26是BCM编号，对应树莓派物理针脚37，不是物理针脚26。

## 4. TB6612单通道固定高电平测试

默认按当前待验证接线：`1IN1=BCM GPIO13`、`1IN2=BCM GPIO19`、`1P=BCM GPIO26`。
该脚本不调用摄像头，也不创建 `GPIO.PWM`，只把P脚置为固定高电平1秒。

运行前必须抬起车轮，并逐一核对驱动板端子：

```bash
sudo python3 04_test_tb6612_one_channel.py --run
```

反方向短测：

```bash
sudo python3 04_test_tb6612_one_channel.py --direction backward --run
```

若现场接线不是上述GPIO，必须通过 `--in1`、`--in2`、`--enable` 指定真实BCM编号。

## 5. TB6612单通道软件PWM测试

单通道固定高电平测试通过后，再测试 `GPIO.PWM`。默认使用GPIO26、1000Hz、50%占空比、运行2秒：

```bash
sudo python3 05_test_tb6612_pwm.py --run
```

如果50%占空比只听到声音但不能起转，可在车轮悬空条件下短测70%：

```bash
sudo python3 05_test_tb6612_pwm.py --duty 70 --run
```

脚本按“占空比归零 → `stop()` → 删除PWM对象 → `GPIO.cleanup()`”的顺序退出，用于规避PWM对象在GPIO资源释放后再次清理造成的报错。

## 6. TB6612四通道软件PWM测试

当前测试映射：

| 实物位置 | 旧缩写/通道 | IN1 | IN2 | PWM | 车体前进方向电平 |
|---|---|---:|---:|---:|---|
| 左前 | LB/3 | GPIO17 | GPIO27 | GPIO25 | IN1高、IN2低 |
| 左后 | RF/4 | GPIO22 | GPIO23 | GPIO24 | IN1高、IN2低 |
| 右前 | RB/1 | GPIO13 | GPIO19 | GPIO26 | IN1低、IN2高 |
| 右后 | LF/2 | GPIO5 | GPIO6 | GPIO12 | IN1低、IN2高 |

必须先抬起四个车轮并核对实物接线。第一步逐轮运行，每个车轮1秒：

```bash
sudo python3 06_test_tb6612_four_channel_pwm.py --mode sequential --run
```

逐轮映射全部正确后，第二步才允许四轮同时运行1秒：

```bash
sudo python3 06_test_tb6612_four_channel_pwm.py --mode all --run
```

首次逐轮测试确认四个轮子都能起转，但相同方向电平下左侧两轮前进、右侧两轮后退。脚本现已按照电机镜像安装关系反转右侧方向电平。再次逐轮测试时，四个程序名称对应的车轮都应朝车体前进方向旋转；确认后才能运行 `all`。

## 7. USB摄像头与四路PWM组合稳定性

四通道PWM已经确认能使四个轮子起转且SSH稳定，但方向极性仍未最终解决。该组合测试只判断摄像头、四路PWM和网络能否同时稳定运行，不评价车轮方向。必须将四个车轮悬空：

```bash
sudo python3 07_test_camera_four_pwm.py --run
```

默认使用USB摄像头0、640×480、四路1000Hz/40%占空比，运行10秒。记录摄像头帧数、失败帧、SSH/VNC状态和程序退出错误。方向问题暂停期间，不把该脚本中的 `invert` 配置同步到生产代码。

## 8. 四路动态PWM压力测试

摄像头与四路固定PWM组合已经通过后，暂时移除摄像头，只测试频繁调用 `ChangeDutyCycle()`。必须保持四轮悬空：

```bash
sudo python3 08_test_dynamic_four_pwm.py --run
```

默认运行20秒，以20Hz更新四路PWM；左右两侧占空比在40%～65%之间反向渐变。该脚本只测试动态PWM调用、负载变化、网络与退出清理，不评价车轮方向。

## 9. USB摄像头与四路动态PWM组合测试

固定PWM与摄像头组合、动态PWM单独运行都通过后，再合并摄像头读取与动态PWM更新。该阶段仍不执行颜色识别和PID。四轮必须悬空：

```bash
sudo python3 09_test_camera_dynamic_pwm.py --run
```

默认运行20秒，摄像头640×480，四路PWM以20Hz在40%～65%之间变化。记录帧数、失败帧、PWM更新次数、SSH/VNC状态和退出错误。

## 10. 实际视觉算法与四路动态PWM组合

第9项通过后，增加现有 `vision.py` 的 `process_frame()`，执行高斯模糊、HSV红色阈值、形态学、轮廓和中心点计算；仍不执行PID、窗口显示或逐帧打印。脚本必须与树莓派上的 `vision.py` 放在同一目录，四轮保持悬空：

```bash
sudo python3 10_test_vision_dynamic_pwm.py --run
```

测试时可让摄像头画面中出现红色物体，以覆盖轮廓和中心点分支。记录FPS、识别帧数、失败帧、PWM更新次数、SSH/VNC状态和退出错误。

## 结果判断

| 测试结果 | 说明 |
|---|---|
| 摄像头、数字、GPIO均不掉网 | 需要继续测试“GPIO接回驱动板”或完整电机程序 |
| 普通数字程序也掉网 | 与摄像头和GPIO无关，检查Wi-Fi/系统 |
| GPIO只导入就掉网 | GPIO库或系统环境异常 |
| GPIO配置/切换时掉网 | 检查库、GPIO占用和树莓派端引脚 |
| GPIO线断开时正常、接回驱动板后掉网 | 接线错位、电气冲突、共地或驱动板干扰 |
| 摄像头测试掉网 | 继续检查USB摄像头、USB复位和Wi-Fi/SDIO |

每次测试同时在另一个本地终端观察：

```bash
sudo journalctl -k -f
```

记录测试名称、开始时间、是否掉网，以及是否出现 `brcmfmac`、`CMD53` 或USB reset日志。
