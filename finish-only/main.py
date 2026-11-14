# แผนสำรองสำหรับสนามตัวอย่างหน้า 1 ตั้งรถกลาง START หันขึ้นตามภาพ
SPEED = 255  # กำลังล้อ 0–255
TILE_MS = 500  # เวลาเดินหน้า 1 ช่อง (30 ซม.) ค่าเริ่มสำหรับจูนบนพื้นจริง
RIGHT_90_MS = 300  # เวลาหมุนขวา 90° (ms)
LEFT_90_MS = 300  # เวลาหมุนซ้าย 90° (ms)
BRAKE_MS = 120  # เวลารอให้รถหยุดไหลก่อนเริ่มช่วงถัดไป

# จำนวนบวกคือจำนวนช่องที่เดินตรง ระหว่างตัวเลขให้ใส่คำสั่งหมุนด้านที่ต้องการ
TURN_RIGHT = -1
TURN_LEFT = -2
ROUTE = [3, TURN_RIGHT, 2, TURN_RIGHT, 1, TURN_RIGHT, 1,
         TURN_LEFT, 1, TURN_LEFT, 5, TURN_RIGHT, 1]

running = False
stopped = False


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)


def stop_route():
    global stopped
    stopped = True
    stop_wheels()


def run_route():
    global running, stopped
    if running:
        return
    running = True
    stopped = False
    basic.clear_screen()
    for step in ROUTE:
        if stopped:
            break
        if step > 0:
            # M1/M2 ซ้าย และ M3/M4 ขวา เดินหน้าพร้อมกัน
            motionbit.run_motor(MotionBitMotorChannel.ALL, MotionBitMotorDirection.FORWARD, SPEED)
            duration = step * TILE_MS
        elif step == TURN_RIGHT or step == TURN_LEFT:
            left = MotionBitMotorDirection.FORWARD
            right = MotionBitMotorDirection.BACKWARD
            duration = RIGHT_90_MS
            if step == TURN_LEFT:
                left = MotionBitMotorDirection.BACKWARD
                right = MotionBitMotorDirection.FORWARD
                duration = LEFT_90_MS
            motionbit.run_motor(MotionBitMotorChannel.M1, left, SPEED)
            motionbit.run_motor(MotionBitMotorChannel.M2, left, SPEED)
            motionbit.run_motor(MotionBitMotorChannel.M3, right, SPEED)
            motionbit.run_motor(MotionBitMotorChannel.M4, right, SPEED)
        else:
            break
        basic.pause(duration)
        stop_wheels()
        basic.pause(BRAKE_MS)
    stop_wheels()
    basic.show_string("A")
    running = False


stop_wheels()
input.on_button_pressed(Button.B, stop_route)
input.on_button_pressed(Button.A, run_route)
basic.show_string("A")
