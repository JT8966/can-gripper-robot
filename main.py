# หุ่นคีบกระป๋อง · MOTION:BIT Pro
# เริ่มอ่านที่ run_route() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

RACK_UP = 85  # ปรับมุม S1 ตอนยกชุดคีบ (องศา) ลองกับรางจริงก่อนแขวนกระป๋อง
RACK_DOWN = 55  # ปรับมุม S1 ตอนลดชุดคีบให้ปากคีบอยู่ระดับเดียวกับกระป๋อง
ROTATE_LEFT_READY = 90  # มุมเตรียมของเซอร์โวหมุนชุดคีบด้านซ้าย S4
ROTATE_RIGHT_READY = 90  # มุมเตรียมของเซอร์โวหมุนชุดคีบด้านขวา S5
ROTATE_LEFT_AFTER_GRIP = 90  # ปรับตรงนี้ถ้าต้องการให้ S4 หมุนหลังหนีบ ตอนนี้เท่ากับมุมเตรียม
ROTATE_RIGHT_AFTER_GRIP = 90  # ปรับมุม S5 หลังหนีบให้สอดคล้องกับ S4 และทิศติดตั้งจริง
GRIP_LEFT_OPEN = 65  # มุมอ้าของปากคีบซ้าย S2
GRIP_RIGHT_OPEN = 115  # มุมอ้าของปากคีบขวา S3
GRIP_LEFT_CLOSED = 95  # มุมหุบของ S2 ปรับให้จับกระป๋องได้พอดี
GRIP_RIGHT_CLOSED = 85  # มุมหุบของ S3 ปรับแยกจาก S2 ตามตำแหน่งก้าน
SPEED = 255  # กำลังล้อพื้นฐาน 0–255 ค่า 255 ใช้ตอนออกตัว ถอย และหมุน
LEFT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อซ้าย M1/M2 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
RIGHT = MotionBitMotorDirection.FORWARD  # ทิศเดินหน้าของล้อขวา M3/M4 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
PICKUP_DISTANCE_CM = 10  # ระยะเริ่มคีบ วัดจากหน้าหัว HC-SR04 เป็นซม. เช่น 8 คือรอให้ใกล้ขึ้น
REVERSE_3CM_MS = 50  # เวลาถอยเป็นมิลลิวินาที ถ้าถอยเกิน 3 ซม. ให้ลดค่านี้แล้ววัดซ้ำ
NB142_DETECTED_LEVEL = 1  # ระดับสัญญาณเมื่อ NB142 ตรวจเจอ ใช้ 0 ถ้าโมดูลให้ LOW ตอนตรวจเจอ
NB142_PINS = [DigitalPin.P12, DigitalPin.P13, DigitalPin.P14, DigitalPin.P15, DigitalPin.P16]  # พินของหัวอ่าน NB142 เรียงซ้ายไปขวาตามทิศเดินหน้าของรถ
TURN_TOLERANCE_DEG = 4  # เผื่อมุมรถไหล 4° สั่งเบรกที่ 86° สำหรับเป้าหมาย 90° เพิ่มค่านี้เพื่อเบรกเร็วขึ้น
address = 0x29  # ที่อยู่ I²C ตั้งต้นของเซนเซอร์สี ฟังก์ชันตรวจรุ่นจะเลือกอีกครั้ง
busy = True  # กันปุ่ม A ไว้ระหว่างเปิดเครื่องและเตรียมเข็มทิศ
stopped = False  # สถานะยกเลิกรอบ ปุ่ม B จะเปลี่ยนค่านี้


def stop_wheels():  # รวมคำสั่งหยุดล้อไว้จุดเดียว
    motionbit.brake_motor(MotionBitMotorChannel.ALL)  # เบรกมอเตอร์ทั้งสี่ช่องพร้อมกัน

def on_button_pressed_b():  # ขั้นตอนเมื่อกดปุ่ม B ระหว่างทำงาน
    global stopped  # ใช้สถานะหยุดร่วมกับวงรอบค้นหาและคำสั่งเซอร์โว
    stopped = True  # จำว่าผู้ใช้ยกเลิกรอบนี้แล้ว
    stop_wheels()  # เบรกล้อทันทีที่รับเหตุการณ์ปุ่ม B
input.on_button_pressed(Button.B, on_button_pressed_b)  # ผูกปุ่ม B เข้ากับขั้นตอนหยุดหุ่น

def write_register(reg: number, value: number):  # ส่งค่าตั้งหนึ่งค่าไปยังรีจิสเตอร์ของ TCS3472
    data = bytearray(2)  # เตรียมข้อมูลสองไบต์สำหรับคำสั่งและค่าที่จะเขียน
    data[0] = 0x80 | reg  # ตั้งบิตคำสั่งของ TCS3472 แล้วใส่หมายเลขรีจิสเตอร์
    data[1] = value  # ใส่ค่าที่ต้องการตั้งลงไบต์ที่สอง
    pins.i2c_write_buffer(address, data)  # ส่งข้อมูลไปยังที่อยู่ I²C ที่เลือกไว้


def sensor_ready():  # ตรวจหาและตั้งค่าเซนเซอร์สีก่อนเริ่มค้นหากระป๋อง
    global address  # ให้การอ่านสีครั้งต่อไปใช้ที่อยู่ที่ตรวจเจอ
    for addr in [0x29, 0x39]:  # ลองสองที่อยู่ I²C ที่ใช้ในตระกูล TCS3472
        address = addr  # เลือกที่อยู่ที่จะทดสอบในรอบนี้
        pins.i2c_write_number(address, 0x92, NumberFormat.UINT8_LE, True)  # เลือกรีจิสเตอร์รหัสชิป และคงบัสไว้สำหรับการอ่านต่อ
        chip_id = pins.i2c_read_number(address, NumberFormat.UINT8_LE)  # อ่านรหัสชิปขนาดหนึ่งไบต์
        if chip_id == 0x44 or chip_id == 0x4d:  # ตั้งค่าเฉพาะเมื่อพบรหัสชิปที่รองรับ
            write_register(0x01, 0xeb)  # ตั้งช่วงสะสมแสงประมาณ 50 มิลลิวินาทีต่อการวัด
            write_register(0x0f, 1)  # ตั้งอัตราขยายสัญญาณแสงเป็น 4 เท่า
            write_register(0x00, 1)  # เปิดไฟเลี้ยงวงจรวัดภายในชิป
            basic.pause(5)  # รอวงจรเริ่มทำงาน 5 มิลลิวินาที
            write_register(0x00, 3)  # เริ่มแปลงแสงเป็นค่าดิจิทัล
            basic.pause(60)  # รอให้ได้ตัวอย่างสีชุดแรก
            return True  # แจ้งว่ารอบนี้เปิดใช้การอ่านสีได้
    return False  # ค้นหากระป๋องต่อได้โดยข้ามการรายงานสี


def floor_color():  # จำแนกพื้นเป็น 0 พื้นทั่วไป 1 แดง หรือ 2 น้ำเงิน
    pins.i2c_write_number(address, 0xb4, NumberFormat.UINT8_LE, True)  # เริ่มอ่านจากช่องความสว่างและเลื่อนไปช่องสีถัดไปอัตโนมัติ
    data = pins.i2c_read_buffer(address, 8)  # อ่านสี่ช่องพร้อมกัน ช่องละสองไบต์
    clear = data.get_number(NumberFormat.UINT16_LE, 0)  # แสงรวมจากไบต์ 0–1 ใช้คัดค่าที่มืดเกินไป
    red = data.get_number(NumberFormat.UINT16_LE, 2)  # ค่าช่องแดงจากไบต์ 2–3
    green = data.get_number(NumberFormat.UINT16_LE, 4)  # ค่าช่องเขียวจากไบต์ 4–5
    blue = data.get_number(NumberFormat.UINT16_LE, 6)  # ค่าช่องน้ำเงินจากไบต์ 6–7
    if clear < 30:  # ตัดตัวอย่างที่แสงรวมน้อยกว่า 30
        return 0  # จัดเป็นพื้นทั่วไปเมื่อแสงน้อย
    if red > green * 1.35 and red > blue * 1.35:  # เกณฑ์แดงต้องมากกว่าทั้งเขียวและน้ำเงิน 1.35 เท่า
        return 1  # ส่งรหัสแถบแดง
    if blue > green * 1.2 and blue > red * 1.35:  # เกณฑ์น้ำเงินต้องมากกว่าเขียว 1.2 เท่าและแดง 1.35 เท่า
        return 2  # ส่งรหัสแถบน้ำเงิน
    return 0  # สีที่เหลือจัดเป็นพื้นทั่วไป


def drive_sides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, trim: number = 0):  # ขับล้อแยกทิศซ้าย–ขวา โดย trim คือกำลังที่ผ่อนด้านหนึ่ง
    if left == right and trim == 0:  # เมื่อสั่งทิศเดียวกันและสองฝั่งใช้กำลังเท่ากัน
        motionbit.run_motor(MotionBitMotorChannel.ALL, left, SPEED)  # ใช้คำสั่ง All เพื่อขับ M1–M4 พร้อมกัน
        return  # จบคำสั่งนี้เมื่อขับครบสี่ล้อแล้ว
    left_speed = SPEED + min(0, trim)  # ลดกำลังฝั่งซ้ายเมื่อ trim ติดลบ
    right_speed = SPEED - max(0, trim)  # ลดกำลังฝั่งขวาเมื่อ trim เป็นบวก
    motionbit.run_motor(MotionBitMotorChannel.M1, left, left_speed)  # ส่งทิศและกำลังให้มอเตอร์ซ้าย M1
    motionbit.run_motor(MotionBitMotorChannel.M2, left, left_speed)  # ส่งค่าเดียวกันให้มอเตอร์ซ้าย M2
    motionbit.run_motor(MotionBitMotorChannel.M3, right, right_speed)  # ส่งทิศและกำลังให้มอเตอร์ขวา M3
    motionbit.run_motor(MotionBitMotorChannel.M4, right, right_speed)  # ส่งค่าเดียวกันให้มอเตอร์ขวา M4


def opposite(direction: MotionBitMotorDirection):  # หาทิศกลับข้างสำหรับถอยรถหรือหมุนอยู่กับที่
    if direction == MotionBitMotorDirection.FORWARD:  # ตรวจว่าทิศที่รับเข้ามาคือเดินหน้าหรือไม่
        return MotionBitMotorDirection.BACKWARD  # ถ้ารับทิศเดินหน้า ให้คืนทิศถอย
    return MotionBitMotorDirection.FORWARD  # ถ้ารับทิศถอย ให้คืนทิศเดินหน้า


def nb142_detected():  # ตรวจว่าหัวอ่าน NB142 อย่างน้อยหนึ่งช่องยังเจอพื้นที่
    for i in range(len(NB142_PINS)):  # ไล่อ่านพินทั้งห้าตามรายการด้านบน
        if pins.digital_read_pin(NB142_PINS[i]) == NB142_DETECTED_LEVEL:  # เทียบสัญญาณดิจิทัลกับค่าที่ถือว่าตรวจเจอ
            return True  # เจอช่องแรกแล้วคืนผลได้ทันที
    return False  # ครบห้าช่องแล้วไม่มีช่องใดตรวจเจอ


def heading_error(target: number, heading: number):  # หามุมต่างแบบมีเครื่องหมาย แม้ทิศจะข้าม 359° ไป 0°
    return (target - heading + 540) % 360 - 180  # เลือกมุมระยะสั้นในช่วง −180° ถึงต่ำกว่า 180°


def object_in_reach():  # วัดด้วย HC-SR04 แล้วตอบว่าวัตถุอยู่ในระยะคีบหรือยัง
    pins.digital_write_pin(DigitalPin.P0, 0)  # ดึง TRIG ที่ P0 ลงต่ำก่อนส่งพัลส์
    control.wait_micros(2)  # คงระดับต่ำ 2 ไมโครวินาที
    pins.digital_write_pin(DigitalPin.P0, 1)  # ยก TRIG ขึ้นสูงเพื่อเริ่มพัลส์
    control.wait_micros(10)  # คงระดับสูง 10 ไมโครวินาที
    pins.digital_write_pin(DigitalPin.P0, 0)  # จบพัลส์ TRIG ให้โมดูลเริ่มวัด
    echo_us = pins.pulse_in(DigitalPin.P1, PulseValue.HIGH, 25000)  # วัดความกว้างพัลส์ ECHO ที่ P1 รอได้สูงสุด 25,000 ไมโครวินาที
    return echo_us > 0 and echo_us <= PICKUP_DISTANCE_CM * 58  # รับเฉพาะพัลส์ที่มีจริงและอยู่ในระยะที่ตั้งไว้ ประมาณ 58 ไมโครวินาทีต่อซม.


def search_for_can(read_colors: bool):  # ควบคุมล้อและตรวจวัตถุซ้ำจนพบกระป๋องหรือยกเลิกรอบ
    target = input.compass_heading()  # จำทิศเริ่มต้นจากเข็มทิศไว้เป็นแนวเดินตรง
    if target < 0 or target >= 360:  # ตรวจว่าค่าเข็มทิศเริ่มต้นอยู่นอกช่วง 0–359° หรือไม่
        return False  # ยกเลิกการค้นหาเมื่อกำหนดแนวเดินไม่ได้
    turning = False  # เริ่มรอบในโหมดเดินตรง
    turn_started = 0  # เตรียมเก็บเวลาเริ่มหมุนเพื่อจับเวลาครบ 5 วินาที
    turn_entry = 0  # เตรียมเก็บทิศตั้งต้นสำหรับวัดมุมหมุนขวา
    pivot_powered = False  # จำว่าได้สั่งล้อให้หมุนสวนกันไปแล้วหรือยัง
    next_ping = 0  # เวลาเร็วที่สุดที่จะยิงอัลตราโซนิกครั้งถัดไป
    previous_color = 0  # จำสีครั้งก่อนเพื่อรายงานเฉพาะตอนเปลี่ยนแถบ
    near_last_sample = False  # เริ่มโดยยังไม่มีผลวัดใกล้ให้ยืนยัน
    trim = 0  # เริ่มโดยให้ล้อสองฝั่งใช้กำลังเท่ากัน
    starting = True  # ให้คำสั่งเดินหน้าครั้งแรกออกตัวพร้อมกันทั้งสี่ล้อ
    while not stopped:  # วนค้นหาตราบใดที่ยังไม่ได้กด B
        detected = nb142_detected()  # อ่านว่า NB142 ยังตรวจเจออย่างน้อยหนึ่งช่องหรือไม่
        near = False  # เริ่มรอบการอ่านโดยยังไม่มีผลระยะใกล้
        if detected and input.running_time() >= next_ping:  # ยิงวัดเมื่อยังอยู่ในพื้นที่และถึงเวลาวัดรอบใหม่
            near = object_in_reach()  # ตรวจว่ามีวัตถุใกล้พอจะคีบหรือไม่
            next_ping = input.running_time() + 65  # เว้นอย่างน้อย 65 มิลลิวินาทีก่อนยิงครั้งถัดไป
            detected = nb142_detected()  # เช็กพื้นที่ซ้ำเพราะรถอาจเคลื่อนระหว่างรอเสียงสะท้อน
        if stopped:  # ตรวจปุ่มหยุดอีกครั้งหลังอ่านเซนเซอร์
            return False  # ออกจากการค้นหาโดยไม่เริ่มคีบ
        if not detected and not turning:  # เมื่อทั้งห้าช่องไม่เจอและรถยังไม่ได้กำลังเลี้ยว
            stop_wheels()  # เบรกก่อนเปลี่ยนจากเดินหน้าเป็นถอย
            entry = input.compass_heading()  # จำทิศรถก่อนถอยไว้เป็นจุดเริ่มของการเลี้ยว
            if entry < 0 or entry >= 360 or stopped:  # ตรวจทิศก่อนถอยและตรวจว่ามีคำสั่งหยุดแทรกหรือไม่
                return False  # จบรอบถ้าไม่สามารถเริ่มหลบขอบได้
            drive_sides(opposite(LEFT), opposite(RIGHT))  # ขับล้อทั้งสองฝั่งย้อนทิศเดินหน้าเพื่อถอยพร้อมกัน
            basic.pause(REVERSE_3CM_MS)  # ถอยตามเวลาที่ปรับไว้สำหรับระยะประมาณ 3 ซม.
            stop_wheels()  # เบรกเมื่อครบเวลาถอย
            if stopped:  # ตรวจว่ากด B ระหว่างถอยหรือไม่
                return False  # ยกเลิกรอบก่อนเริ่มหมุน
            target = (entry + 90) % 360  # กำหนดทิศใหม่ทางขวา 90° ถ้าแก้มุม ให้แก้เลขเดียวกันที่เงื่อนไขจบการหมุนด้วย
            turning = True  # สลับเข้าโหมดหมุนขวา
            starting = True  # เตรียมออกตัวเต็มกำลังอีกครั้งเมื่อหมุนเสร็จ
            trim = 0  # ล้างส่วนต่างกำลังที่ใช้แก้รถเบนก่อนหน้า
            turn_entry = entry  # ใช้ทิศก่อนถอยเป็นศูนย์สำหรับนับองศาที่หมุน
            pivot_powered = False  # อนุญาตให้ส่งคำสั่งหมุนครั้งแรก
            turn_started = input.running_time()  # เริ่มจับเวลาการหมุนที่จุดนี้
            near_last_sample = False  # ทิ้งผลวัดวัตถุใกล้จากแนวเดินเดิม
            continue  # กลับไปอ่านเซนเซอร์และเริ่มควบคุมการเลี้ยว
        if detected and near:  # พิจารณาคีบเมื่อยังเจอพื้นที่และวัตถุอยู่ในระยะ
            stop_wheels()  # เบรกล้อทันทีตั้งแต่ผลใกล้ครั้งแรก
            trim = 0  # ล้างกำลังชดเชยขณะรถหยุด
            starting = True  # ถ้าต้องเดินหน้าต่อ ให้ออกตัวสี่ล้อพร้อมกัน
            pivot_powered = False  # ถ้าต้องหมุนต่อ ให้ส่งคำสั่งมอเตอร์ใหม่หลังเบรก
            if near_last_sample:  # ตรวจว่ารอบก่อนก็อ่านค่าใกล้เช่นกันหรือไม่
                return True  # ยืนยันผลระยะใกล้สองครั้งแล้ว ส่งต่อให้ลำดับคีบ
            near_last_sample = True  # บันทึกผลใกล้ครั้งแรกไว้รอยืนยัน
            basic.pause(65)  # รอ 65 มิลลิวินาทีขณะล้อหยุดก่อนวัดยืนยัน
            continue  # เริ่มรอบใหม่เพื่ออ่านระยะซ้ำ
        near_last_sample = False  # ล้างผลใกล้เมื่อเงื่อนไขยืนยันไม่ครบ
        if read_colors:  # อ่านสีเฉพาะเมื่อพบ TCS3472 ตอนเตรียมตัว
            color = floor_color()  # จำแนกสีพื้นใต้หัวอ่าน
            if color != previous_color:  # เปรียบเทียบกับสีครั้งก่อน
                if color == 1:  # ตรวจว่าเพิ่งเข้าแถบแดงหรือไม่
                    serial.write_line("RED")  # ส่ง RED ทาง Serial ให้ดูในคอมพิวเตอร์
                if color == 2:  # ตรวจว่าเพิ่งเข้าแถบน้ำเงินหรือไม่
                    serial.write_line("BLUE")  # ส่ง BLUE ทาง Serial ให้ดูในคอมพิวเตอร์
                previous_color = color  # จำสีนี้ไว้เทียบในรอบถัดไป
        heading = input.compass_heading()  # อ่านทิศปัจจุบันเพื่อปรับล้อหรือวัดมุมเลี้ยว
        if heading < 0 or heading >= 360 or stopped:  # ตรวจว่าเข็มทิศอ่านได้และรอบยังทำงานอยู่
            return False  # จบการค้นหาให้ผู้เรียกเบรกเมื่อทิศผิดปกติหรือกด B
        error = heading_error(target, heading)  # หาว่าต้องแก้แนวไปทางไหนและกี่องศา
        if turning and input.running_time() - turn_started >= 5000:  # ตรวจว่าหมุนเกินเวลา 5,000 มิลลิวินาทีหรือยัง
            return False  # จบการค้นหาให้ผู้เรียกเบรกเมื่อเลี้ยวไม่สำเร็จ
        if not turning:  # เลือกควบคุมการเดินตรงเมื่ออยู่นอกโหมดหมุน
            amount = min(80, 3 * max(0, abs(error) - 2))  # ยอมให้เบน 2° แล้วชดเชย 3 หน่วยต่อองศาที่เกิน จำกัดส่วนต่างไว้ที่ 80
            desired = amount if error > 0 else -amount  # กำหนดฝั่งที่จะผ่อนกำลังตามเครื่องหมายมุม
            if starting:  # แยกคำสั่งเดินหน้าครั้งแรกหลังเริ่มหรือหยุด
                trim = 0  # ออกตัวด้วยกำลังเท่ากันทั้งสี่ล้อ ค่าปัจจุบันคือ 255
                starting = False  # เปิดให้ปรับกำลังล้อตั้งแต่รอบถัดไป
            else:  # ระหว่างวิ่งใช้ค่าจากเข็มทิศแก้แนว
                trim += max(-16, min(16, desired - trim))  # ขยับส่วนต่างกำลังเข้าหาค่าเป้าทีละไม่เกิน 16 เพื่อให้เปลี่ยนทิศนุ่มขึ้น
            drive_sides(LEFT, RIGHT, trim)  # ให้ทั้งสี่ล้อเดินหน้าโดยผ่อนกำลังตามค่าที่คำนวณ
        elif heading_error(heading, turn_entry) < 90 - TURN_TOLERANCE_DEG:  # หมุนต่อจนถึงมุมเป้าลบระยะเผื่อเบรก ถ้าเปลี่ยน 90 ให้แก้มุมเป้าด้านบนด้วย
            if not pivot_powered:  # ส่งคำสั่งหมุนเฉพาะเมื่อยังไม่ได้จ่ายกำลังสำหรับการหมุนนี้
                drive_sides(LEFT, opposite(RIGHT))  # หมุนขวาอยู่กับที่โดยให้ล้อซ้ายเดินหน้าและล้อขวาถอย
                pivot_powered = True  # จำว่าล้อกำลังหมุนต่อเนื่องอยู่แล้ว
            basic.pause(10)  # รอ 10 มิลลิวินาทีก่อนตรวจทิศอีกครั้งโดยล้อยังหมุน
            continue  # วนตรวจมุมและเซนเซอร์โดยข้ามช่วงพักของการเดินตรง
        else:  # เข้าขั้นจบการเลี้ยวเมื่อหมุนถึงมุมเบรกแล้ว
            stop_wheels()  # เบรกทั้งสี่ล้อเมื่อถึงมุมที่ตั้ง
            turning = False  # กลับเข้าโหมดเดินตรง
            pivot_powered = False  # ล้างสถานะจ่ายกำลังหมุนไว้สำหรับการเลี้ยวครั้งหน้า
        basic.pause(65)  # พัก 65 มิลลิวินาทีก่อนควบคุมล้อรอบถัดไป
    return False  # ส่งผลยกเลิกเมื่อปุ่ม B ทำให้หลุดจากวงรอบค้นหา


def move_rack(angle: number):  # สั่งเซอร์โวตัวล่างให้ยกหรือลดชุดคีบไปยังมุมที่รับมา
    if stopped:  # ตรวจคำสั่งหยุดก่อนขยับราง
        return  # ข้ามการขยับเมื่อรอบถูกยกเลิก
    motionbit.set_servo_position(MotionBitServoChannel.S1, angle)  # ส่งมุมให้เซอร์โว S1 ที่ขับเฟืองราง
    basic.pause(550)  # เผื่อให้รางเคลื่อนถึงตำแหน่ง 550 มิลลิวินาที


def rotate_grip(after_grip: bool):  # จัดมุมเซอร์โวคู่หมุนตามท่าเตรียมหรือท่าหลังหนีบ
    if stopped:  # ตรวจคำสั่งหยุดก่อนหมุนชุดคีบ
        return  # ข้ามการหมุนเมื่อรอบถูกยกเลิก
    motionbit.set_servo_position(MotionBitServoChannel.S4,  # สั่งเซอร์โวหมุนชุดคีบด้านซ้าย S4
        ROTATE_LEFT_AFTER_GRIP if after_grip else ROTATE_LEFT_READY)  # เลือกมุมซ้ายจากค่าท่าเตรียมหรือหลังหนีบที่ต้นไฟล์
    motionbit.set_servo_position(MotionBitServoChannel.S5,  # สั่งเซอร์โวหมุนชุดคีบด้านขวา S5
        ROTATE_RIGHT_AFTER_GRIP if after_grip else ROTATE_RIGHT_READY)  # เลือกมุมขวาจากค่าท่าเตรียมหรือหลังหนีบที่ต้นไฟล์
    basic.pause(550)  # รอให้คู่หมุนเคลื่อนถึงมุมก่อนทำขั้นต่อไป


def move_grip(close: bool):  # สั่งปากคีบสองข้างให้หุบหรืออ้า
    if stopped:  # ตรวจคำสั่งหยุดก่อนขยับปากคีบ
        return  # ข้ามการหนีบเมื่อรอบถูกยกเลิก
    motionbit.set_servo_position(MotionBitServoChannel.S2,  # สั่งเซอร์โวปากคีบซ้าย S2
        GRIP_LEFT_CLOSED if close else GRIP_LEFT_OPEN)  # เลือกมุมหุบหรืออ้าของด้านซ้าย
    motionbit.set_servo_position(MotionBitServoChannel.S3,  # สั่งเซอร์โวปากคีบขวา S3
        GRIP_RIGHT_CLOSED if close else GRIP_RIGHT_OPEN)  # เลือกมุมหุบหรืออ้าของด้านขวา
    basic.pause(550)  # รอให้ปากคีบทั้งคู่ไปถึงตำแหน่ง 550 มิลลิวินาที


def run_route():  # ลำดับงานหนึ่งรอบ แก้ตรงนี้หากต้องการสลับขั้นตอนของแขน
    read_colors = sensor_ready()  # ตรวจและตั้งค่าเซนเซอร์สี ผลที่ได้ใช้เปิดการรายงานสี
    move_rack(RACK_UP)  # ยกรางขึ้นเพื่อเตรียมวิ่ง
    rotate_grip(False)  # จัดคู่หมุน S4/S5 ไว้ที่มุมเตรียม
    move_grip(False)  # อ้าปากคีบ S2/S3 ก่อนค้นหา
    found = search_for_can(read_colors)  # เริ่มขับค้นหาและรอผลยืนยันระยะจากอัลตราโซนิก
    stop_wheels()  # หยุดล้อก่อนตัดสินใจขยับแขน
    if not found or stopped:  # ตรวจว่าค้นหาล้มเหลวหรือมีคำสั่งยกเลิกหรือไม่
        return False  # จบรอบโดยข้ามขั้นตอนคีบถ้าเงื่อนไขไม่ผ่าน
    move_rack(RACK_DOWN)  # ลดราง S1 ให้ปากคีบอยู่ระดับกระป๋อง
    move_grip(True)  # หุบ S2/S3 พร้อมกันเพื่อจับกระป๋อง
    rotate_grip(True)  # สั่ง S4/S5 ไปมุมหลังหนีบ ปัจจุบันเท่าท่าเตรียมจึงค้างที่ 90°
    return not stopped  # รายงานว่าทำงานครบหากไม่มีการกดหยุด

def on_button_pressed_a():  # ขั้นตอนเริ่มรอบเมื่อกด A บนตัว micro:bit
    global busy, stopped  # ใช้สถานะร่วมกับปุ่ม B และวงรอบค้นหา
    if busy:  # ตรวจว่ามีรอบอื่นกำลังทำงานอยู่หรือไม่
        return  # ข้ามการกด A ซ้ำระหว่างทำงาน
    busy = True  # ล็อกการเริ่มรอบใหม่จนกว่างานนี้จะเสร็จ
    stopped = False  # ล้างคำสั่งหยุดจากรอบก่อน
    basic.clear_screen()  # ล้างตัวอักษรบนจอก่อนออกตัว
    done = run_route()  # เริ่มลำดับงานและเก็บว่าทำสำเร็จหรือไม่
    stop_wheels()  # เบรกล้ออีกครั้งก่อนแสดงผล
    if done:  # เลือกสัญลักษณ์ตามผลของรอบ
        basic.show_icon(IconNames.YES)  # แสดงเครื่องหมายถูกเมื่อทำครบลำดับ
    else:  # กรณียกเลิกหรือจบรอบด้วยปัญหา
        basic.show_icon(IconNames.NO)  # แสดงกากบาทให้ผู้ใช้เห็นว่ารอบหยุดก่อนสำเร็จ
    busy = False  # ปลดล็อกให้กด A เริ่มรอบถัดไป
input.on_button_pressed(Button.A, on_button_pressed_a)  # ผูกปุ่ม A เข้ากับขั้นตอนเริ่มรอบ

stop_wheels()  # ตอนเปิดเครื่องให้ล้อหยุดไว้ก่อน
input.compass_heading()  # เรียกเข็มทิศขณะรถจอด เพื่อให้ปรับเทียบก่อนเริ่มถ้าบอร์ดร้องขอ
busy = False  # ให้เริ่มรอบได้หลังขั้นเตรียมเข็มทิศ
basic.show_string("A")  # แสดง A เพื่อบอกว่าพร้อมรับปุ่มเริ่ม
