# 智能小车四模块修正版

本目录统一使用 **BCM GPIO编号**。不要把物理针脚号11、13、22等再次写入GPIO常量。

## 环境确认

VS Code解释器选择 `/usr/bin/python3`，然后执行：

```bash
/usr/bin/python3 -c "import sys, cv2, numpy, RPi.GPIO as GPIO; print(sys.executable); print(cv2.__file__); print(numpy.__file__); print(GPIO.__file__, GPIO.VERSION)"
```

不要使用快速修复重复安装 `RPi.GPIO`。

## 替换方法

先在树莓派备份当前文件：

```bash
cd /home/htsb
mkdir -p backup_before_fix
cp car_run_final.py coolspot_motor.py vision.py keyboard_control.py backup_before_fix/
```

然后把本目录四个Python文件复制到 `/home/htsb/`。

## 运行顺序

`car_run_final.py` 现在采用便捷默认值：启用电机、自动跟随、无窗口、2Hz日志。因此普通运行只需要：

```bash
cd /home/htsb
python3 car_run_final.py
```

只运行视觉、不初始化GPIO时：

```bash
python3 car_run_final.py --vision-only --duration 20
```

需要外接显示器或VNC窗口并使用WASD手动控制时，使用快捷参数：

```bash
python3 car_run_final.py --manual
```

手动模式必须让OpenCV窗口获得焦点。按空格保持停止，按R返回自动模式，按H切换动力，按Q退出。

旧命令中的 `--enable-motors` 仍然兼容，但现在已经是默认值；`--manual` 等价于 `--mode manual --show`。默认无窗口是为了避免重新增加VNC和板载Wi-Fi负载。

如果系统没有 `python` 命令、希望继续使用 `python car_run_final.py`，在树莓派终端执行一次：

```bash
grep -qxF "alias python='/usr/bin/python3'" ~/.bashrc || echo "alias python='/usr/bin/python3'" >> ~/.bashrc
source ~/.bashrc
```

之后可以运行：

```bash
python car_run_final.py
```

## 单独确认四轮位置

先关闭其他小车程序、连接好四个电机并抬起四轮。不要带电换线。默认依次短转通道1～4：

```bash
python3 wheel_position_test.py
```

脚本会在每个通道开始前等待Enter，并要求输入实际转动位置，最后打印映射记录。只测试某一个通道：

```bash
python3 wheel_position_test.py --channel 1
```

当前计划映射为：通道1右前、通道2右后、通道3左前、通道4左后。测试方向只用于让轮子转动，不作为最终前进方向结论。

如果只需要最短的现场观察程序，使用严格10行的版本：

```bash
python3 wheel_quick_test.py
```

启动后输入通道1～4，每次只测试一个轮子，并执行“逻辑前进1秒、逻辑后退1秒”。只负责让你观察实际位置和方向，不自动保存记录。运行期间禁止换线；换线前先退出程序并关闭驱动板电源。

## 当前未完成项

- `DIRECTION_INVERTED` 根据“左侧前进、右侧后退”的现场现象暂设为右侧反转，仍需最终逐轮确认。
- PID参数沿用旧版本，尚未重新标定。
- 编码器尚未接入速度闭环。
- 板载Wi-Fi的 `brcmfmac/CMD53/SDIO` 问题与代码修复分开处理。
