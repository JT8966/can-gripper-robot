# MOTION:BIT Pro | ปรับมุมให้ตรงกับแขนจริงก่อนติดกระป๋อง
RACK_UP = 85
RACK_DOWN = 55
# ค่าตั้งต้นสำหรับสองฝั่งที่ติดตั้งหันเข้าหากัน ปรับแต่ละฝั่งตามกลไกจริง
ROTATE_LEFT_READY = 90
ROTATE_RIGHT_READY = 90
ROTATE_LEFT_AFTER_GRIP = 90
ROTATE_RIGHT_AFTER_GRIP = 90
GRIP_LEFT_OPEN = 65
GRIP_RIGHT_OPEN = 115
GRIP_LEFT_CLOSED = 95
GRIP_RIGHT_CLOSED = 85
SPEED = 255
# กำลังขับเต็มของ MOTION:BIT
LEFT = MotionBitMotorDirection.FORWARD
# เดินหน้าฝั่งซ้าย: M1A และ M2A
RIGHT = MotionBitMotorDirection.FORWARD
# เดินหน้าฝั่งขวา: M3A และ M4A
PICKUP_DISTANCE_CM = 10
# ค่า X ชั่วคราว วัดจากหน้าหัวอัลตราโซนิก
REVERSE_3CM_MS = 50
# ค่าเริ่มทดลอง ต้องวัดระยะถอยบนพื้นจริงที่กำลังเต็ม
NB142_DETECTED_LEVEL = 1
# หัวอ่าน NB142 เรียงจากซ้ายไปขวาตามทิศเดินหน้าของรถ
NB142_PINS = [DigitalPin.P12, DigitalPin.P13, DigitalPin.P14, DigitalPin.P15, DigitalPin.P16]
TURN_TOLERANCE_DEG = 4
address = 0x29
busy = True
stopped = False


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)

def on_button_pressed_b():
    global stopped
    stopped = True
    stop_wheels()
input.on_button_pressed(Button.B, on_button_pressed_b)

def write_register(reg: number, value: number):
    data = bytearray(2)
    data[0] = 0x80 | reg
    data[1] = value
    pins.i2c_write_buffer(address, data)


def sensor_ready():
    global address
    for addr in [0x29, 0x39]:
        address = addr
        pins.i2c_write_number(address, 0x92, NumberFormat.UINT8_LE, True)
        chip_id = pins.i2c_read_number(address, NumberFormat.UINT8_LE)
        if chip_id == 0x44 or chip_id == 0x4d:
            write_register(0x01, 0xeb)
            # 50 ms integration
            write_register(0x0f, 1)
            # 4x gain
            write_register(0x00, 1)
            basic.pause(5)
            write_register(0x00, 3)
            basic.pause(60)
            return True
    return False
# 0 = พื้นทั่วไป, 1 = แดง, 2 = น้ำเงิน


def floor_color():
    pins.i2c_write_number(address, 0xb4, NumberFormat.UINT8_LE, True)
    data = pins.i2c_read_buffer(address, 8)
    clear = data.get_number(NumberFormat.UINT16_LE, 0)
    red = data.get_number(NumberFormat.UINT16_LE, 2)
    green = data.get_number(NumberFormat.UINT16_LE, 4)
    blue = data.get_number(NumberFormat.UINT16_LE, 6)
    if clear < 30:
        return 0
    if red > green * 1.35 and red > blue * 1.35:
        return 1
    if blue > green * 1.2 and blue > red * 1.35:
        return 2
    return 0


def drive_sides(left: MotionBitMotorDirection, right: MotionBitMotorDirection):
    if left == right:
        motionbit.run_motor(MotionBitMotorChannel.ALL, left, SPEED)
        return
    motionbit.run_motor(MotionBitMotorChannel.M1, left, SPEED)
    motionbit.run_motor(MotionBitMotorChannel.M2, left, SPEED)
    motionbit.run_motor(MotionBitMotorChannel.M3, right, SPEED)
    motionbit.run_motor(MotionBitMotorChannel.M4, right, SPEED)


def opposite(direction: MotionBitMotorDirection):
    if direction == MotionBitMotorDirection.FORWARD:
        return MotionBitMotorDirection.BACKWARD
    return MotionBitMotorDirection.FORWARD


def nb142_detected():
    for i in range(len(NB142_PINS)):
        if pins.digital_read_pin(NB142_PINS[i]) == NB142_DETECTED_LEVEL:
            return True
    return False


def heading_error(target: number, heading: number):
    return (target - heading + 540) % 360 - 180


def object_in_reach():
    pins.digital_write_pin(DigitalPin.P0, 0)
    control.wait_micros(2)
    pins.digital_write_pin(DigitalPin.P0, 1)
    control.wait_micros(10)
    pins.digital_write_pin(DigitalPin.P0, 0)
    echo_us = pins.pulse_in(DigitalPin.P1, PulseValue.HIGH, 25000)
    return echo_us > 0 and echo_us <= PICKUP_DISTANCE_CM * 58


def search_for_can(read_colors: bool):
    target = input.compass_heading()
    if target < 0 or target >= 360:
        return False
    turning = False
    turn_started = 0
    settled = 0
    previous_color = 0
    near_last_sample = False
    while not stopped:
        detected = nb142_detected()
        near = False
        if detected:
            near = object_in_reach()
            detected = nb142_detected()
        if stopped:
            return False
        if not detected and not turning:
            stop_wheels()
            entry = input.compass_heading()
            if entry < 0 or entry >= 360 or stopped:
                return False
            drive_sides(opposite(LEFT), opposite(RIGHT))
            basic.pause(REVERSE_3CM_MS)
            stop_wheels()
            if stopped:
                return False
            target = (entry + 90) % 360
            turning = True
            turn_started = input.running_time()
            settled = 0
            near_last_sample = False
            continue
        if detected and near:
            stop_wheels()
            if near_last_sample:
                return True
            near_last_sample = True
            basic.pause(65)
            continue
        near_last_sample = False
        if read_colors:
            color = floor_color()
            if color != previous_color:
                if color == 1:
                    serial.write_line("RED")
                if color == 2:
                    serial.write_line("BLUE")
                previous_color = color
        heading = input.compass_heading()
        if heading < 0 or heading >= 360 or stopped:
            return False
        error = heading_error(target, heading)
        if turning and input.running_time() - turn_started >= 5000:
            return False
        if abs(error) > TURN_TOLERANCE_DEG:
            settled = 0
            if error > 0:
                drive_sides(LEFT, opposite(RIGHT))
            else:
                drive_sides(opposite(LEFT), RIGHT)
            # ใกล้มุมเป้าหมายให้หมุนสั้นลง แล้วเบรกก่อนอ่านเข็มทิศซ้ำ
            basic.pause(min(45, abs(error)))
            stop_wheels()
        elif turning:
            stop_wheels()
            settled += 1
            turning = settled < 3
        else:
            drive_sides(LEFT, RIGHT)
        basic.pause(65)
    return False


def move_rack(angle: number):
    if stopped:
        return
    motionbit.set_servo_position(MotionBitServoChannel.S1, angle)
    basic.pause(550)


def rotate_grip(after_grip: bool):
    if stopped:
        return
    motionbit.set_servo_position(MotionBitServoChannel.S4,
        ROTATE_LEFT_AFTER_GRIP if after_grip else ROTATE_LEFT_READY)
    motionbit.set_servo_position(MotionBitServoChannel.S5,
        ROTATE_RIGHT_AFTER_GRIP if after_grip else ROTATE_RIGHT_READY)
    basic.pause(550)


def move_grip(close: bool):
    if stopped:
        return
    motionbit.set_servo_position(MotionBitServoChannel.S2,
        GRIP_LEFT_CLOSED if close else GRIP_LEFT_OPEN)
    motionbit.set_servo_position(MotionBitServoChannel.S3,
        GRIP_RIGHT_CLOSED if close else GRIP_RIGHT_OPEN)
    basic.pause(550)


def run_route():
    read_colors = sensor_ready()
    move_rack(RACK_UP)
    rotate_grip(False)
    move_grip(False)
    found = search_for_can(read_colors)
    stop_wheels()
    if not found or stopped:
        return False
    move_rack(RACK_DOWN)
    move_grip(True)
    rotate_grip(True)
    return not stopped

def on_button_pressed_a():
    global busy, stopped
    if busy:
        return
    busy = True
    stopped = False
    basic.clear_screen()
    done = run_route()
    stop_wheels()
    if done:
        basic.show_icon(IconNames.YES)
    else:
        basic.show_icon(IconNames.NO)
    busy = False
input.on_button_pressed(Button.A, on_button_pressed_a)

stop_wheels()
# ให้ micro:bit ขอปรับเทียบครั้งแรกตอนล้อยังหยุด ก่อนผู้ใช้จัดรถเข้าจุดเริ่ม
input.compass_heading()
busy = False
basic.show_string("A")
