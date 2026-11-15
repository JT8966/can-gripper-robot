RACK_UP_COMMAND = 75
RACK_DOWN_COMMAND = 105
RACK_UP_MS = 500
RACK_DOWN_MS = 500
GRIP_OPEN = 40
GRIP_CLOSED = 10
GRIP_MS = 550
RELEASE_MS = 400
SPEED = 255
PICKUP_DISTANCE_CM = 10
FIELD_TILE_MS = 500
DROP_APPROACH_MS = 400
TURN_TOLERANCE_DEG = 4
NB142_DETECTED_LEVEL = 1
NB142_PINS = [DigitalPin.P12, DigitalPin.P13, DigitalPin.P14, DigitalPin.P15, DigitalPin.P16]
MUX_ADDRESS = 0x70
RIGHT_CHANNEL = 0
COLOR_ADDRESS = 0x29
COLOR_LOCK_READS = 5
COLOR_LOCK_GAP_MS = 65
RED = 1
BLUE = 2
GREEN = 3
YELLOW = 4
# เริ่มกลาง START หันขวา รับใบขวาที่จุดรับแรกตามผังเดิม
START_PATH = "EEEN"
PICKUP_PATH = "NE"
PICKUP_FACE = 1
busy = False
stopped = False
cycle_started = False
can_color = 0
field_north = 0
dock_travel_ms = 0


def stop_wheels():
    motionbit.brake_motor(MotionBitMotorChannel.ALL)


def stop_all():
    global stopped
    stopped = True
    stop_wheels()
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)


def nb142_mask():
    mask = 0
    for i in range(len(NB142_PINS)):
        if pins.digital_read_pin(NB142_PINS[i]) == NB142_DETECTED_LEVEL:
            mask |= 1 << i
    return mask


def heading_error(target: number, heading: number):
    return (target - heading + 540) % 360 - 180


def drive_sides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, trim: number = 0):
    motionbit.run_motor(MotionBitMotorChannel.M1, left, SPEED + min(0, trim))
    motionbit.run_motor(MotionBitMotorChannel.M2, left, SPEED + min(0, trim))
    motionbit.run_motor(MotionBitMotorChannel.M3, right, SPEED - max(0, trim))
    motionbit.run_motor(MotionBitMotorChannel.M4, right, SPEED - max(0, trim))


def drive_straight(milliseconds: number, reverse: bool = False):
    target = input.compass_heading()
    if stopped or target < 0 or target >= 360:
        stop_wheels()
        return False
    deadline = input.running_time() + milliseconds
    trim = 0
    while not stopped and input.running_time() < deadline:
        heading = input.compass_heading()
        if stopped or heading < 0 or heading >= 360 or nb142_mask() != 31:
            stop_wheels()
            return False
        error = heading_error(target, heading)
        amount = min(80, 3 * max(0, abs(error) - 2))
        desired = amount if error > 0 else -amount
        trim += max(-16, min(16, desired - trim))
        direction = MotionBitMotorDirection.BACKWARD if reverse else MotionBitMotorDirection.FORWARD
        drive_sides(direction, direction, -trim if reverse else trim)
        basic.pause(min(30, max(1, deadline - input.running_time())))
    stop_wheels()
    return not stopped and nb142_mask() == 31


def face_field(direction: number):
    target = (field_north + 90 * direction) % 360
    deadline = input.running_time() + 5000
    while not stopped and input.running_time() < deadline:
        heading = input.compass_heading()
        if stopped or heading < 0 or heading >= 360 or nb142_mask() != 31:
            break
        error = heading_error(target, heading)
        if abs(error) <= TURN_TOLERANCE_DEG:
            stop_wheels()
            return True
        if error > 0:
            drive_sides(MotionBitMotorDirection.FORWARD, MotionBitMotorDirection.BACKWARD)
        else:
            drive_sides(MotionBitMotorDirection.BACKWARD, MotionBitMotorDirection.FORWARD)
        basic.pause(10)
    stop_wheels()
    return False


def walk_path(path: str, returning: bool = False):
    i = 0
    while i < len(path):
        index = len(path) - 1 - i if returning else i
        direction = "NESW".index(path[index])
        if returning:
            direction = (direction + 2) % 4
        tiles = 1
        while i + tiles < len(path) and path[index - tiles if returning else index + tiles] == path[index]:
            tiles += 1
        if not face_field(direction) or not drive_straight(tiles * FIELD_TILE_MS):
            return False
        i += tiles
    return not stopped


def select_color_channel():
    mask = 1 << RIGHT_CHANNEL
    pins.i2c_write_number(MUX_ADDRESS, mask, NumberFormat.UINT8_LE, False)
    return pins.i2c_read_number(MUX_ADDRESS, NumberFormat.UINT8_LE) == mask


def write_register(reg: number, value: number):
    data = bytearray(2)
    data[0] = 0x80 | reg
    data[1] = value
    pins.i2c_write_buffer(COLOR_ADDRESS, data)


def sensor_ready():
    if not select_color_channel():
        return False
    pins.i2c_write_number(COLOR_ADDRESS, 0x92, NumberFormat.UINT8_LE, True)
    chip_id = pins.i2c_read_number(COLOR_ADDRESS, NumberFormat.UINT8_LE)
    if chip_id != 0x44 and chip_id != 0x4d:
        return False
    write_register(0x01, 0xeb)
    write_register(0x0f, 1)
    write_register(0x00, 1)
    basic.pause(5)
    write_register(0x00, 3)
    basic.pause(60)
    return True


def read_color():
    if not select_color_channel():
        return 0
    pins.i2c_write_number(COLOR_ADDRESS, 0xb4, NumberFormat.UINT8_LE, True)
    data = pins.i2c_read_buffer(COLOR_ADDRESS, 8)
    clear = data.get_number(NumberFormat.UINT16_LE, 0)
    red = data.get_number(NumberFormat.UINT16_LE, 2)
    green = data.get_number(NumberFormat.UINT16_LE, 4)
    blue = data.get_number(NumberFormat.UINT16_LE, 6)
    if clear < 30:
        return 0
    if min(red, green) > blue * 1.45 and max(red, green) <= min(red, green) * 1.35:
        return YELLOW
    if red > green * 1.35 and red > blue * 1.35:
        return RED
    if green > red * 1.35 and green > blue * 1.35:
        return GREEN
    if blue > green * 1.2 and blue > red * 1.35:
        return BLUE
    return 0


def object_in_reach():
    pins.digital_write_pin(DigitalPin.P0, 0)
    control.wait_micros(2)
    pins.digital_write_pin(DigitalPin.P0, 1)
    control.wait_micros(10)
    pins.digital_write_pin(DigitalPin.P0, 0)
    echo_us = pins.pulse_in(DigitalPin.P1, PulseValue.HIGH, 25000)
    return echo_us > 0 and echo_us <= PICKUP_DISTANCE_CM * 58


def approach_can():
    global dock_travel_ms
    dock_travel_ms = 0
    deadline = input.running_time() + 5000
    while not stopped and input.running_time() < deadline:
        if nb142_mask() != 31:
            return False
        near = object_in_reach()
        if stopped or nb142_mask() != 31:
            return False
        if near:
            basic.pause(65)
            near = object_in_reach()
            if stopped or nb142_mask() != 31:
                return False
            if near:
                return True
        else:
            if dock_travel_ms >= FIELD_TILE_MS:
                return False
            start = input.running_time()
            if not drive_straight(min(65, FIELD_TILE_MS - dock_travel_ms)):
                return False
            dock_travel_ms += input.running_time() - start
        basic.pause(65)
    return False


def place_raise_ms(color: number):
    if color == GREEN:
        return 500
    if color == YELLOW:
        return 650
    if color == RED:
        return 800
    return 0


def station_path(color: number):
    if color == GREEN:
        return "WWWW"
    if color == YELLOW:
        return "NEN"
    return "EE"


def move_rack(command: number, duration: number):
    if stopped:
        return False
    motionbit.set_servo_position(MotionBitServoChannel.S1, command)
    basic.pause(duration)
    motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
    return not stopped


def pick_can():
    global can_color
    if stopped or can_color:
        return False
    if not approach_can():
        return False
    stop_wheels()
    if not sensor_ready() or stopped or nb142_mask() != 31:
        return False
    color = read_color()
    if place_raise_ms(color) == 0:
        return False
    for i in range(1, COLOR_LOCK_READS):
        basic.pause(COLOR_LOCK_GAP_MS)
        if stopped or nb142_mask() != 31 or read_color() != color:
            return False
    if stopped or nb142_mask() != 31:
        return False
    can_color = color
    serial.write_line("COLOR LOCK " + str(color))
    if stopped:
        return False
    motionbit.set_servo_position(MotionBitServoChannel.S3, GRIP_CLOSED)
    basic.pause(GRIP_MS)
    return move_rack(RACK_UP_COMMAND, RACK_UP_MS)


def place_can():
    global can_color
    raise_ms = place_raise_ms(can_color)
    if stopped or raise_ms == 0:
        return False
    stop_wheels()
    if not move_rack(RACK_UP_COMMAND, raise_ms):
        return False
    motionbit.set_servo_position(MotionBitServoChannel.S3, GRIP_OPEN)
    can_color = 0
    basic.pause(RELEASE_MS)
    return move_rack(RACK_DOWN_COMMAND, raise_ms + RACK_DOWN_MS)


def run_delivery():
    global field_north
    heading = input.compass_heading()
    if stopped or heading < 0 or heading >= 360:
        return False
    field_north = (heading + 270) % 360
    if not walk_path(START_PATH) or not walk_path(PICKUP_PATH):
        return False
    if not face_field(PICKUP_FACE) or not pick_can():
        return False
    if not drive_straight(dock_travel_ms, True) or not walk_path(PICKUP_PATH, True):
        return False
    if not walk_path(station_path(can_color)):
        return False
    if not face_field(1 if can_color == YELLOW else 2):
        return False
    return drive_straight(DROP_APPROACH_MS) and place_can()


def on_button_pressed_a():
    global busy, cycle_started
    # ตำแหน่งรถและรางหลังเริ่มไม่ใช่ท่า START ต้องจัดกลับแล้ว RESET ก่อนรอบใหม่
    if busy or stopped or cycle_started:
        return
    busy = True
    cycle_started = True
    try:
        basic.clear_screen()
        done = run_delivery()
        basic.show_icon(IconNames.YES if done else IconNames.NO)
    finally:
        stop_wheels()
        motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
        busy = False


stop_wheels()
motionbit.set_servo_position(MotionBitServoChannel.S1, 90)
motionbit.set_servo_position(MotionBitServoChannel.S2, GRIP_OPEN)
motionbit.set_servo_position(MotionBitServoChannel.S3, GRIP_OPEN)
input.on_button_pressed(Button.B, stop_all)
input.on_button_pressed(Button.A, on_button_pressed_a)
basic.show_string("A")
