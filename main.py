# หุ่นคีบกระป๋อง · MOTION:BIT Pro
# เริ่มอ่านที่ run_route() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

RACK_DOWN_COMMAND = 75
RACK_DOWN_MS = 0
ROTATE_RIGHT_COMMAND = 105
ROTATE_RIGHT_MS = 0
GRIP_RIGHT_OPEN = 10
GRIP_LEFT_OPEN = 20
GRIP_RIGHT_CLOSED = GRIP_RIGHT_OPEN
GRIP_LEFT_CLOSED = GRIP_LEFT_OPEN
SPEED = 255  # กำลังล้อพื้นฐาน 0–255 ค่า 255 ใช้ตอนออกตัว ถอย และหมุน
LEFT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อซ้าย M1/M2 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
RIGHT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อขวา M3/M4 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
PICKUP_DISTANCE_CM = 10  # ระยะเริ่มคีบ วัดจากหน้าหัว HC-SR04 เป็นซม. เช่น 8 คือรอให้ใกล้ขึ้น
REVERSE_3CM_MS = 50  # เวลาถอยเป็นมิลลิวินาที ถ้าถอยเกิน 3 ซม. ให้ลดค่านี้แล้ววัดซ้ำ
NB142_DETECTED_LEVEL = 1  # ระดับสัญญาณเมื่อ NB142 ตรวจเจอ ใช้ 0 ถ้าโมดูลให้ LOW ตอนตรวจเจอ
NB142_PINS = [DigitalPin.P12, DigitalPin.P13, DigitalPin.P14, DigitalPin.P15, DigitalPin.P16]  # พินของหัวอ่าน NB142 เรียงซ้ายไปขวาตามทิศเดินหน้าของรถ
TURN_DEG = 90  # มุมหมุนขวาเมื่อ NB142 หลุดกรอบ
TURN_TOLERANCE_DEG = 4  # เผื่อมุมรถไหล 4° สั่งเบรกที่ 86° สำหรับเป้าหมาย 90° เพิ่มค่านี้เพื่อเบรกเร็วขึ้น
address = 0x29
busy = True
stopped = False


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)

def on_button_pressed_b():
    global stopped
    stopped = True
    stop_wheels()
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
    motionbit.set_servo_position(MotionBitServoChannel.S2, 90)
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
            write_register(0x01, 0xeb)  # ตั้งช่วงสะสมแสงประมาณ 50 มิลลิวินาทีต่อการวัด
            write_register(0x0f, 1)  # ตั้งอัตราขยายสัญญาณแสงเป็น 4 เท่า
            write_register(0x00, 1)  # เปิดไฟเลี้ยงวงจรวัดภายในชิป
            basic.pause(5)
            write_register(0x00, 3)  # เริ่มแปลงแสงเป็นค่าดิจิทัล
            basic.pause(60)
            return True
    return False


def floor_color():  # จำแนกพื้นเป็น 0 พื้นทั่วไป 1 แดง หรือ 2 น้ำเงิน
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


def drive_sides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, trim: number = 0):  # ขับล้อแยกทิศซ้าย–ขวา โดย trim คือกำลังที่ผ่อนด้านหนึ่ง
    if left == right and trim == 0:
        motionbit.run_motor(MotionBitMotorChannel.ALL, left, SPEED)
        return
    left_speed = SPEED + min(0, trim)
    right_speed = SPEED - max(0, trim)
    motionbit.run_motor(MotionBitMotorChannel.M1, left, left_speed)
    motionbit.run_motor(MotionBitMotorChannel.M2, left, left_speed)
    motionbit.run_motor(MotionBitMotorChannel.M3, right, right_speed)
    motionbit.run_motor(MotionBitMotorChannel.M4, right, right_speed)


def opposite(direction: MotionBitMotorDirection):
    if direction == MotionBitMotorDirection.FORWARD:
        return MotionBitMotorDirection.BACKWARD
    return MotionBitMotorDirection.FORWARD


def nb142_mask():
    mask = 0
    for i in range(len(NB142_PINS)):
        if pins.digital_read_pin(NB142_PINS[i]) == NB142_DETECTED_LEVEL:
            mask |= 1 << i
    return mask


# หันเข้าหาฝั่งที่ยังติด ถ้าสองฝั่งสมดุลให้คงทิศแก้ล่าสุด
def alignment_direction(mask: number, previous: number):
    balance = 0
    for i in range(len(NB142_PINS)):
        if (mask & (1 << i)) != 0:
            balance += i - 2
    if balance == 0:
        return previous
    return 1 if balance > 0 else -1


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
    turn_entry = 0
    next_ping = 0
    previous_color = 0
    near_last_sample = False
    trim = 0
    wheels_moving = False
    aligning = False
    direction = 1
    while not stopped:
        mask = nb142_mask()
        near = False
        if mask == 31 and input.running_time() >= next_ping:
            near = object_in_reach()
            next_ping = input.running_time() + 65
            mask = nb142_mask()
        if stopped:
            return False
        if mask != 0 and mask != 31:
            if not aligning:
                stop_wheels()
                turn_started = input.running_time()
                turning = False
                aligning = True
                wheels_moving = False
            if input.running_time() - turn_started >= 5000:
                return False
            next_direction = alignment_direction(mask, direction)
            if not wheels_moving or next_direction != direction:
                if next_direction > 0:
                    drive_sides(LEFT, opposite(RIGHT))
                else:
                    drive_sides(opposite(LEFT), RIGHT)
                direction = next_direction
                wheels_moving = True
            near_last_sample = False
            basic.pause(10)
            continue
        if aligning:
            stop_wheels()
            aligning = False
            wheels_moving = False
            if mask == 31:
                target = input.compass_heading()
                if target < 0 or target >= 360 or stopped:
                    return False
        if mask == 0 and not turning:
            stop_wheels()
            turn_entry = input.compass_heading()
            if turn_entry < 0 or turn_entry >= 360 or stopped:
                return False
            drive_sides(opposite(LEFT), opposite(RIGHT))
            basic.pause(REVERSE_3CM_MS)
            stop_wheels()
            if stopped:
                return False
            target = (turn_entry + TURN_DEG) % 360
            turning = True
            direction = 1
            wheels_moving = False
            turn_started = input.running_time()
            near_last_sample = False
            continue
        if mask == 31 and near:
            stop_wheels()
            wheels_moving = False
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
        if turning and input.running_time() - turn_started >= 5000:
            return False
        if not turning:
            if wheels_moving:
                error = heading_error(target, heading)
                amount = min(80, 3 * max(0, abs(error) - 2))
                desired = amount if error > 0 else -amount
                trim += max(-16, min(16, desired - trim))
            else:
                trim = 0  # ออกตัวเต็มกำลังพร้อมกันทั้งสี่ล้อ
                wheels_moving = True
            drive_sides(LEFT, RIGHT, trim)
        elif heading_error(heading, turn_entry) < TURN_DEG - TURN_TOLERANCE_DEG:
            if not wheels_moving:
                drive_sides(LEFT, opposite(RIGHT))
                wheels_moving = True
            basic.pause(10)
            continue
        else:
            stop_wheels()
            turning = False
            wheels_moving = False
        basic.pause(65)
    return False


def run_timed_servo(channel: MotionBitServoChannel, command: number, duration: number):
    if stopped or duration <= 0:
        return
    motionbit.set_servo_position(channel, command)
    basic.pause(duration)
    motionbit.set_servo_position(channel, 90)


def set_grip(right: number, left: number):
    motionbit.set_servo_position(MotionBitServoChannel.S4, right)
    motionbit.set_servo_position(MotionBitServoChannel.S5, left)


def run_route():
    set_grip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
    found = search_for_can(sensor_ready())
    stop_wheels()
    if not found or stopped:
        return False
    run_timed_servo(MotionBitServoChannel.S1, RACK_DOWN_COMMAND, RACK_DOWN_MS)
    if stopped:
        return False
    set_grip(GRIP_RIGHT_CLOSED, GRIP_LEFT_CLOSED)
    basic.pause(550)
    run_timed_servo(MotionBitServoChannel.S2, ROTATE_RIGHT_COMMAND, ROTATE_RIGHT_MS)
    return not stopped


def on_button_pressed_a():
    global busy, stopped
    if busy:
        return
    busy = True
    stopped = False
    basic.clear_screen()
    done = run_route()
    if done:
        basic.show_icon(IconNames.YES)
    else:
        basic.show_icon(IconNames.NO)
    busy = False
input.on_button_pressed(Button.A, on_button_pressed_a)

stop_wheels()
basic.show_icon(IconNames.YES)
motionbit.set_servo_position(MotionBitServoChannel.S2, 90)
set_grip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
basic.pause(1000)
input.compass_heading()  # เรียกเข็มทิศขณะรถจอด เพื่อให้ปรับเทียบก่อนเริ่มถ้าบอร์ดร้องขอ
busy = False
basic.show_string("A")
