# หุ่นคีบกระป๋อง · MOTION:BIT Pro
# เริ่มอ่านที่ run_route() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

# S1 หมุนต่อเนื่อง ตั้งให้หมุนซ้ายเพื่อยก ถ้าทดสอบแล้วทิศกลับ ให้สลับ 75 กับ 105
RACK_UP_COMMAND = 75
RACK_UP_MS = 500
RACK_DOWN_COMMAND = 105
RACK_DOWN_MS = 500
# S2 กางไปทางซ้าย S3 กางไปทางขวา มุมของแต่ละท่าอ้างอิงจากเพลาของตัวนั้น
# มุมกางและหุบที่ระบุเท่ากัน วงคีบจึงค้างที่ 45° จนกว่าจะปรับมุมหุบ
GRIP_LEFT_OPEN = 45
GRIP_LEFT_CLOSED = 45
GRIP_RIGHT_OPEN = 45
GRIP_RIGHT_CLOSED = 45
SPEED = 255  # กำลังล้อพื้นฐาน 0–255 ค่า 255 ใช้ตอนออกตัว ถอย และหมุน
LEFT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อซ้าย M1/M2 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
RIGHT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อขวา M3/M4 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
PICKUP_DISTANCE_CM = 10  # ระยะเริ่มคีบ วัดจากหน้าหัว HC-SR04 เป็นซม. เช่น 8 คือรอให้ใกล้ขึ้น
REVERSE_3CM_MS = 50  # เวลาถอยเป็นมิลลิวินาที ถ้าถอยเกิน 3 ซม. ให้ลดค่านี้แล้ววัดซ้ำ
NB142_DETECTED_LEVEL = 1  # ระดับสัญญาณเมื่อ NB142 ตรวจเจอ ใช้ 0 ถ้าโมดูลให้ LOW ตอนตรวจเจอ
NB142_PINS = [DigitalPin.P12, DigitalPin.P13, DigitalPin.P14, DigitalPin.P15, DigitalPin.P16]  # พินของหัวอ่าน NB142 เรียงซ้ายไปขวาตามทิศเดินหน้าของรถ
TURN_DEG = 90  # มุมหมุนขวาเมื่อ NB142 หลุดกรอบ
TURN_TOLERANCE_DEG = 4  # เผื่อมุมรถไหล 4° สั่งเบรกที่ 86° สำหรับเป้าหมาย 90° เพิ่มค่านี้เพื่อเบรกเร็วขึ้น
COLOR_ADDRESS = 0x29  # TCS34725 เซ็นเซอร์สีข้างขวา (ต่อตรง I2C ไม่ผ่าน PCA9548A)
busy = False  # เริ่มด้วย False เพื่อให้ปุ่ม A ใช้ได้เสมอ แม้โปรแกรมตายช่วงบูตก่อนถึงท้ายไฟล์
stopped = False
right_can_color = 0  # อ่านกระป๋องในวงขวา S3
arm_cycle_incomplete = False  # ถ้าหยุดกลางลำดับแขน ต้องจัดกลไกกลับท่าเริ่มแล้วรีเซ็ต
color_sensor_ready = False


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)

# กด B เพื่อเบรกล้อและหยุดราง S1 ส่วน S2/S3 ค้างมุมล่าสุดเพื่อประคองกระป๋อง
def on_button_pressed_b():
    global stopped
    stopped = True
    stop_wheels()
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
input.on_button_pressed(Button.B, on_button_pressed_b)


def write_register(reg: number, value: number):
    data = bytearray(2)
    data[0] = 0x80 | reg
    data[1] = value
    pins.i2c_write_buffer(COLOR_ADDRESS, data)


def sensor_ready():
    pins.i2c_write_number(COLOR_ADDRESS, 0x92, NumberFormat.UINT8_LE, True)
    chip_id = pins.i2c_read_number(COLOR_ADDRESS, NumberFormat.UINT8_LE)
    if chip_id != 0x44 and chip_id != 0x4d:
        serial.write_line("TCS unexpected ID " + str(chip_id))
        return False
    write_register(0x01, 0xeb)  # สะสมแสงประมาณ 50 มิลลิวินาที
    write_register(0x0f, 1)  # ขยายสัญญาณ 4 เท่า
    write_register(0x00, 1)
    basic.pause(5)
    write_register(0x00, 3)
    basic.pause(60)
    return True


def check_color_sensor():
    ready = sensor_ready()
    serial.write_line("TCS " + ("OK" if ready else "ERROR"))
    return ready


RED = 1
BLUE = 2
GREEN = 3
YELLOW = 4


def read_color():
    pins.i2c_write_number(COLOR_ADDRESS, 0xb4, NumberFormat.UINT8_LE, True)
    data = pins.i2c_read_buffer(COLOR_ADDRESS, 8)
    clear = data.get_number(NumberFormat.UINT16_LE, 0)
    red = data.get_number(NumberFormat.UINT16_LE, 2)
    green = data.get_number(NumberFormat.UINT16_LE, 4)
    blue = data.get_number(NumberFormat.UINT16_LE, 6)
    if clear < 30:
        return -1  # มืดเกินไป ยังใช้ยืนยันการพ้นแถบต้นทางไม่ได้
    # เหลืองมีทั้งแดงและเขียวสูงกว่าน้ำเงิน เกณฑ์เหล่านี้ต้องลองกับเทปและแสงจริง
    if min(red, green) > blue * 1.45 and max(red, green) <= min(red, green) * 1.35:
        return YELLOW
    if red > green * 1.35 and red > blue * 1.35:
        return RED
    if green > red * 1.35 and green > blue * 1.35:
        return GREEN
    if blue > green * 1.2 and blue > red * 1.35:
        return BLUE
    return 0


def color_name(color: number):
    if color == RED:
        return "RED"
    if color == BLUE:
        return "BLUE"
    if color == GREEN:
        return "GREEN"
    if color == YELLOW:
        return "YELLOW"
    return "?"


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


# กลับทิศจากท่าเดินหน้าของล้อแต่ละฝั่ง ใช้ตอนถอยและหมุนอยู่กับที่
def opposite(direction: MotionBitMotorDirection):
    if direction == MotionBitMotorDirection.FORWARD:
        return MotionBitMotorDirection.BACKWARD
    return MotionBitMotorDirection.FORWARD


# เก็บหัวอ่าน NB142 ทั้ง 5 ช่องในเลขเดียว บิต 0 คือซ้ายสุด บิต 4 คือขวาสุด ค่า 31 คือติดครบ และ 0 คือดับหมด
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


# หามุมต่างทางสั้นที่สุด เช่น จากทิศ 359° ไป 1° ต้องหมุนขวาเพียง 2°
def heading_error(target: number, heading: number):
    return (target - heading + 540) % 360 - 180


# ส่งพัลส์ 10 ไมโครวินาทีที่ TRIG (P0) แล้วจับเวลา ECHO (P1) เสียงไป–กลับประมาณ 58 ไมโครวินาทีต่อระยะ 1 ซม.
def object_in_reach():
    pins.digital_write_pin(DigitalPin.P0, 0)
    control.wait_micros(2)
    pins.digital_write_pin(DigitalPin.P0, 1)
    control.wait_micros(10)
    pins.digital_write_pin(DigitalPin.P0, 0)
    echo_us = pins.pulse_in(DigitalPin.P1, PulseValue.HIGH, 25000)
    return echo_us > 0 and echo_us <= PICKUP_DISTANCE_CM * 58


# หยุดรอวัดระยะซ้ำก่อนอ่านสีจากกระป๋องข้างขวา
def find_cans():
    start_time = input.running_time()
    target = input.compass_heading()
    if target < 0 or target >= 360:
        return 0
    turning = False
    turn_started = 0
    turn_entry = 0
    next_ping = 0
    candidate = False
    trim = 0
    wheels_moving = False
    aligning = False
    direction = 1
    while not stopped:
        if input.running_time() - start_time > 30000:
            stop_wheels()
            serial.write_line("FIND TIMEOUT")
            return 0
        mask = nb142_mask()
        near = False
        # วัดระยะเมื่อหัวอ่านติดครบ เว้นการยิงเสียงอย่างน้อย 65 มิลลิวินาที แล้วอ่านกรอบซ้ำก่อนสั่งล้อ
        if mask == 31 and input.running_time() >= next_ping:
            near = object_in_reach()
            next_ping = input.running_time() + 65
            mask = nb142_mask()
        if stopped:
            return 0
        # ดับ 1–4 ช่อง ให้หยุดเดินหน้าหรือเลิกเลี้ยว 90° แล้วหมุนกลับเข้าหาฝั่งที่ยังติด จำกัดเวลาแก้แนว 5 วินาที
        if mask != 0 and mask != 31:
            if not aligning:
                stop_wheels()
                turn_started = input.running_time()
                turning = False
                aligning = True
                wheels_moving = False
            if input.running_time() - turn_started >= 5000:
                return 0
            next_direction = alignment_direction(mask, direction)
            if not wheels_moving or next_direction != direction:
                if next_direction > 0:
                    drive_sides(LEFT, opposite(RIGHT))
                else:
                    drive_sides(opposite(LEFT), RIGHT)
                direction = next_direction
                wheels_moving = True
            candidate = False
            basic.pause(10)
            continue
        # เมื่อพ้นช่วงแก้แนวให้เบรก ถ้าติดครบแล้วให้จำทิศปัจจุบันเป็นแนวเดินหน้าใหม่
        if aligning:
            stop_wheels()
            aligning = False
            wheels_moving = False
            if mask == 31:
                target = input.compass_heading()
                if target < 0 or target >= 360 or stopped:
                    return 0
        # ดับทั้ง 5 ช่อง ให้ถอยตามเวลาที่จูนไว้ แล้วตั้งเป้าเลี้ยวขวาจากทิศก่อนถอย
        if mask == 0 and not turning:
            stop_wheels()
            turn_entry = input.compass_heading()
            if turn_entry < 0 or turn_entry >= 360 or stopped:
                return 0
            drive_sides(opposite(LEFT), opposite(RIGHT))
            basic.pause(REVERSE_3CM_MS)
            stop_wheels()
            if stopped:
                return 0
            target = (turn_entry + TURN_DEG) % 360
            turning = True
            direction = 1
            wheels_moving = False
            turn_started = input.running_time()
            candidate = False
            continue
        if near and mask == 31:
            stop_wheels()
            wheels_moving = False
            if candidate:
                return 1
            candidate = True
            basic.pause(65)
            continue
        candidate = False
        heading = input.compass_heading()
        if heading < 0 or heading >= 360 or stopped:
            return 0
        if turning and input.running_time() - turn_started >= 5000:
            return 0
        if not turning:
            # ยอมให้รถเบน 2° ก่อนผ่อนล้อ ค่อย ๆ เปลี่ยนส่วนต่างกำลังครั้งละไม่เกิน 16 เพื่อลดการส่าย
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
            # หมุนขวาอยู่กับที่โดยให้ล้อซ้ายเดินหน้าและล้อขวาถอย ตรวจมุมซ้ำระหว่างหมุน
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
    return 0


# S1 หมุนตามเวลาที่ตั้งแล้วรับค่า 90 เพื่อหยุด
def move_rack(command: number, duration: number):
    if stopped or duration <= 0:
        return
    duration = min(duration, 3000)  # กัน pause นานผิดปกติ
    motionbit.set_servo_position(MotionBitServoChannel.S1, command)
    basic.pause(duration)
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)


def set_grip(left: number, right: number):
    motionbit.set_servo_position(MotionBitServoChannel.S2, left)
    motionbit.set_servo_position(MotionBitServoChannel.S3, right)


def pick_cans():
    global right_can_color, arm_cycle_incomplete, color_sensor_ready
    found = find_cans()
    stop_wheels()
    if not found or stopped:
        return False
    # ใช้สีเฉพาะตอนรับกระป๋อง ถ้าตอนเปิดเครื่องยังไม่พบหัวอ่าน ให้ลองอีกครั้งขณะล้อหยุด
    if not color_sensor_ready:
        try:
            color_sensor_ready = check_color_sensor()
        except:
            color_sensor_ready = False
    if not color_sensor_ready or stopped or nb142_mask() != 31:
        return False
    right = read_color()
    serial.write_line("S3 " + color_name(right))
    basic.pause(65)
    if stopped or nb142_mask() != 31:
        return False
    if right <= 0 or read_color() != right:
        return False
    if stopped:
        return False
    arm_cycle_incomplete = True
    right_can_color = right
    set_grip(GRIP_LEFT_CLOSED, GRIP_RIGHT_CLOSED)
    basic.pause(550)
    move_rack(RACK_UP_COMMAND, RACK_UP_MS)
    if stopped:
        return False
    arm_cycle_incomplete = False
    return True


# เมื่อคีบแล้ว จอแสดงสีกระป๋องขวา รถจอดถือไว้จนกว่าจะมีเส้นทางไปสถานี
def run_route():
    if arm_cycle_incomplete:
        return False
    if stopped:
        return False
    if not right_can_color and not pick_cans():
        return False
    basic.show_string("R " + color_name(right_can_color))
    return not stopped


# กด A เพื่อเริ่มหนึ่งรอบ ตัวแปร busy กันการกดซ้ำ จอ ✓ เมื่อจบลำดับ หรือ ✗ เมื่อหยุดก่อนจบ
def on_button_pressed_a():
    global busy, stopped
    if busy:
        return
    stopped = False
    busy = True
    try:
        basic.clear_screen()
        done = run_route()
        if done:
            basic.show_icon(IconNames.YES)
        else:
            basic.show_icon(IconNames.NO)
    finally:
        busy = False  # คืนค่าแม้เกิด exception เพื่อไม่ให้ปุ่ม A ล็อกถาวร
input.on_button_pressed(Button.A, on_button_pressed_a)

# เริ่มโดยให้รางอยู่ระดับรับกระป๋อง เปิดเครื่องแล้วสั่งเฉพาะวงคีบ
basic.show_icon(IconNames.YES, 0)
stop_wheels()
set_grip(GRIP_LEFT_OPEN, GRIP_RIGHT_OPEN)
basic.pause(1000)
color_sensor_ready = False  # ตรวจ TCS34725 ตอน pick_cans แทน กันช่วงบูตค้างถ้าเซ็นเซอร์หลุด
basic.show_leds("""
    . # # # .
    . # . # .
    . # # # .
    . # . # .
    . # . # .
""", 0)
busy = False
