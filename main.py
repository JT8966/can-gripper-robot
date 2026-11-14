# หุ่นคีบกระป๋อง · MOTION:BIT Pro
# เริ่มอ่านที่ run_route() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

# S1 ยก–ลดราง และ S2 หมุนที่คีบขวา เป็นเซอร์โว 360° ค่า 90 คือหยุด ค่าที่ต่างจาก 90 กำหนดทิศและความเร็ว
RACK_DOWN_COMMAND = 75
# เวลาลดรางเป็นมิลลิวินาที ตั้งเป็น 0 เพื่อข้ามการลดจนกว่าจะจูนระยะจริง
RACK_DOWN_MS = 0
RACK_UP_COMMAND = 105
RACK_UP_MS = 0  # จูนเวลายกกระป๋องขึ้นก่อนออกเดิน และยกรางกลับหลังวาง
ROTATE_RIGHT_COMMAND = 105
# เวลาหมุน S2 หลังหนีบ ตั้งเป็น 0 เพื่อค้างท่าเดิม
ROTATE_RIGHT_MS = 0
# S2 คืนท่าหลังปล่อย ใช้ความเร็วตรงข้ามรอบค่าหยุด 90 และจูนเวลาคืนแยกได้
ROTATE_RETURN_COMMAND = 180 - ROTATE_RIGHT_COMMAND
ROTATE_RETURN_MS = ROTATE_RIGHT_MS
# S4 ขวาและ S5 ซ้ายเป็นเซอร์โว 180° ตัวเลขด้านล่างคือมุมปากคีบแต่ละข้าง
GRIP_RIGHT_OPEN = 10
GRIP_LEFT_OPEN = 20
# ใส่มุมหนีบที่วัดได้ของแต่ละข้างตรงนี้ ตอนนี้ตั้งเท่ามุมเปิดจึงยังไม่หุบ
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
carrying_color = 0  # เก็บสีไว้จนกว่าจะปล่อย แม้หยุดด้วย B ระหว่างขน
left_pickup = False
transport_ready = False  # ถ้ายกหรือลดค้างเมื่อกด B ให้จัดรางด้วยมือก่อนรีเซ็ต


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)

# กด B ระหว่างทำงานเพื่อยกเลิกรอบ เบรกล้อ และหยุด S1/S2 ส่วน S4/S5 ค้างมุมล่าสุด
def on_button_pressed_b():
    global stopped
    stopped = True
    stop_wheels()
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
    motionbit.set_servo_position(MotionBitServoChannel.S2, 90)
input.on_button_pressed(Button.B, on_button_pressed_b)

# ส่งคำสั่งตั้งค่า TCS3472 ผ่าน I²C โดยส่งหมายเลขรีจิสเตอร์และค่าที่จะเขียนเป็นคู่
def write_register(reg: number, value: number):
    data = bytearray(2)
    data[0] = 0x80 | reg
    data[1] = value
    pins.i2c_write_buffer(address, data)


# ต้องพบ TCS3472 เพื่อจำสีพื้นตอนรับและตรวจสีตอนวาง
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


RED = 1
BLUE = 2
GREEN = 3
YELLOW = 4


def floor_color():
    pins.i2c_write_number(address, 0xb4, NumberFormat.UINT8_LE, True)
    data = pins.i2c_read_buffer(address, 8)
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


# เมื่อขนกระป๋อง ให้ใช้สีพื้นตัดสินจุดหยุด เพราะกระป๋องในคีบอาจบัง HC-SR04
def drive_to_station(delivering: bool):
    global left_pickup
    target = input.compass_heading()
    if target < 0 or target >= 360:
        return 0
    turning = False
    turn_started = 0
    turn_entry = 0
    next_ping = 0
    candidate = 0
    off_since = -1
    previous_color = 0
    trim = 0
    wheels_moving = False
    aligning = False
    direction = 1
    while not stopped:
        mask = nb142_mask()
        near = False
        # วัดระยะเมื่อหัวอ่านติดครบ เว้นการยิงเสียงอย่างน้อย 65 มิลลิวินาที แล้วอ่านกรอบซ้ำก่อนสั่งล้อ
        if not delivering and mask == 31 and input.running_time() >= next_ping:
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
            candidate = 0
            off_since = -1
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
            candidate = 0
            off_since = -1
            continue
        color = floor_color() if mask == 31 else -1
        if delivering and not left_pickup:
            if color >= 0 and color != carrying_color:
                if off_since < 0:
                    off_since = input.running_time()
                elif input.running_time() - off_since >= 65:
                    left_pickup = True
            else:
                off_since = -1
        if color != previous_color:
            if color == RED:
                serial.write_line("RED")
            elif color == BLUE:
                serial.write_line("BLUE")
            elif color == YELLOW:
                serial.write_line("YELLOW")
            elif color == GREEN:
                serial.write_line("GREEN")
            previous_color = color
        pickup = not delivering and near and mask == 31
        drop = delivering and left_pickup and color == carrying_color
        if pickup or drop:
            stop_wheels()
            wheels_moving = False
            # ยืนยันสีเดียวกันสองครั้งห่างอย่างน้อยหนึ่งรอบวัดแสง ก่อนอนุญาตให้ขยับแขน
            if color != RED and color != BLUE and color != YELLOW and color != GREEN:
                return 0
            if candidate == color and not stopped and nb142_mask() == 31:
                return color
            candidate = color
            basic.pause(65)
            continue
        candidate = 0
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


# ขับเซอร์โว 360° ตามเวลาที่กำหนดแล้วส่งค่า 90 เพื่อหยุด ถ้าเวลาเป็น 0 ให้ข้ามขั้นตอนนี้
def run_timed_servo(channel: MotionBitServoChannel, command: number, duration: number):
    if stopped or duration <= 0:
        return
    motionbit.set_servo_position(channel, command)
    basic.pause(duration)
    motionbit.set_servo_position(channel, 90)


# วงคีบขวา S4 และวงคีบซ้าย S5 โอบกระป๋องคนละใบ ใช้มุมของแต่ละวงในขั้นตอนเดียวกัน
def set_grip(right: number, left: number):
    motionbit.set_servo_position(MotionBitServoChannel.S4, right)
    motionbit.set_servo_position(MotionBitServoChannel.S5, left)


# งานหนึ่งรอบ รับจากพื้นสีใด นำไปวางบนแถบสีเดียวกันอีกจุด
def run_route():
    global carrying_color, left_pickup, transport_ready
    if carrying_color and not transport_ready:
        return False
    if not color_sensor_ready or stopped:
        return False
    if carrying_color == 0:
        set_grip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
        picked = drive_to_station(False)
        stop_wheels()
        if not picked or stopped:
            return False
        run_timed_servo(MotionBitServoChannel.S1, RACK_DOWN_COMMAND, RACK_DOWN_MS)
        if stopped:
            return False
        set_grip(GRIP_RIGHT_CLOSED, GRIP_LEFT_CLOSED)
        carrying_color = picked
        left_pickup = False
        basic.pause(550)
        run_timed_servo(MotionBitServoChannel.S2, ROTATE_RIGHT_COMMAND, ROTATE_RIGHT_MS)
        run_timed_servo(MotionBitServoChannel.S1, RACK_UP_COMMAND, RACK_UP_MS)
        transport_ready = not stopped
    if stopped:
        return False
    arrived = drive_to_station(True)
    stop_wheels()
    if not arrived or stopped:
        return False
    transport_ready = False
    run_timed_servo(MotionBitServoChannel.S1, RACK_DOWN_COMMAND, RACK_DOWN_MS)
    if stopped:
        return False
    set_grip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
    basic.pause(550)
    if ROTATE_RIGHT_MS > 0 and ROTATE_RIGHT_COMMAND != 90:
        run_timed_servo(MotionBitServoChannel.S2, ROTATE_RETURN_COMMAND, ROTATE_RETURN_MS)
    run_timed_servo(MotionBitServoChannel.S1, RACK_UP_COMMAND, RACK_UP_MS)
    if stopped:
        return False
    # ปิดรอบเมื่อคืนชุดคีบเสร็จ ถ้ากด B กลางทางให้จัดท่าจริงก่อนรีเซ็ต
    carrying_color = 0
    return True


# กด A เพื่อเริ่มหนึ่งรอบ ตัวแปร busy กันการกดซ้ำ จอ ✓ เมื่อจบลำดับ หรือ ✗ เมื่อหยุดก่อนจบ
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

# เปิดเครื่องแล้วเบรกล้อ หยุด S1/S2 และตั้งวงคีบขวา 10° ซ้าย 20°
stop_wheels()
motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
motionbit.set_servo_position(MotionBitServoChannel.S2, 90)
basic.show_icon(IconNames.YES)
set_grip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
basic.pause(1000)
color_sensor_ready = sensor_ready()
input.compass_heading()  # เรียกเข็มทิศขณะรถจอด เพื่อให้ปรับเทียบก่อนเริ่มถ้าบอร์ดร้องขอ
busy = False
basic.show_string("A" if color_sensor_ready else "I2C")
