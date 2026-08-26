import time, coolspot_motor as m
W={1:("计划右前",m.IN1_RB,m.IN2_RB,m.PWM_RB),2:("计划右后",m.IN1_LF,m.IN2_LF,m.PWM_LF),3:("计划左前",m.IN1_LB,m.IN2_LB,m.PWM_LB),4:("计划左后",m.IN1_RF,m.IN2_RF,m.PWM_RF)}
c=int(input("选择单轮通道1~4：")); n,a,b,p=W[c]
input(f"抬起四轮，按Enter测试通道{c}/{n}：")
m.initialize()
try:
    print(n,"逻辑前进"); m.set_wheel(a,b,p,45,"forward"); time.sleep(1); m.stop()
    print(n,"逻辑后退"); m.set_wheel(a,b,p,45,"backward"); time.sleep(1); m.stop()
finally:
    m.cleanup()
