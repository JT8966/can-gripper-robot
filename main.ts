// หุ่นคีบกระป๋อง · MOTION:BIT Pro
// เริ่มอ่านที่ runRoute() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

const RACK_UP = 85  // ปรับมุม S1 ตอนยกชุดคีบ (องศา) ลองกับรางจริงก่อนแขวนกระป๋อง
const RACK_DOWN = 55  // ปรับมุม S1 ตอนลดชุดคีบให้ปากคีบอยู่ระดับเดียวกับกระป๋อง
const ROTATE_LEFT_READY = 90  // มุมเตรียมของเซอร์โวหมุนชุดคีบด้านซ้าย S4
const ROTATE_RIGHT_READY = 90  // มุมเตรียมของเซอร์โวหมุนชุดคีบด้านขวา S5
const ROTATE_LEFT_AFTER_GRIP = 90  // ปรับตรงนี้ถ้าต้องการให้ S4 หมุนหลังหนีบ ตอนนี้เท่ากับมุมเตรียม
const ROTATE_RIGHT_AFTER_GRIP = 90  // ปรับมุม S5 หลังหนีบให้สอดคล้องกับ S4 และทิศติดตั้งจริง
const GRIP_LEFT_OPEN = 65  // มุมอ้าของปากคีบซ้าย S2
const GRIP_RIGHT_OPEN = 115  // มุมอ้าของปากคีบขวา S3
const GRIP_LEFT_CLOSED = 95  // มุมหุบของ S2 ปรับให้จับกระป๋องได้พอดี
const GRIP_RIGHT_CLOSED = 85  // มุมหุบของ S3 ปรับแยกจาก S2 ตามตำแหน่งก้าน
const SPEED = 255  // กำลังล้อพื้นฐาน 0–255 ค่า 255 ใช้ตอนออกตัว ถอย และหมุน
const LEFT = MotionBitMotorDirection.Forward  // ทิศเดินหน้าของล้อซ้าย M1/M2 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
const RIGHT = MotionBitMotorDirection.Forward  // ทิศเดินหน้าของล้อขวา M3/M4 กลับค่านี้ถ้าทั้งฝั่งหมุนย้อน
const PICKUP_DISTANCE_CM = 10  // ระยะเริ่มคีบ วัดจากหน้าหัว HC-SR04 เป็นซม. เช่น 8 คือรอให้ใกล้ขึ้น
const REVERSE_3CM_MS = 50  // เวลาถอยเป็นมิลลิวินาที ถ้าถอยเกิน 3 ซม. ให้ลดค่านี้แล้ววัดซ้ำ
const NB142_DETECTED_LEVEL = 1  // ระดับสัญญาณเมื่อ NB142 ตรวจเจอ ใช้ 0 ถ้าโมดูลให้ LOW ตอนตรวจเจอ
const NB142_PINS = [  // พินของหัวอ่าน NB142 เรียงซ้ายไปขวาตามทิศเดินหน้าของรถ
    DigitalPin.P12,  // สัญญาณหัวอ่านซ้ายสุด
    DigitalPin.P13,  // สัญญาณหัวอ่านซ้ายกลาง
    DigitalPin.P14,  // สัญญาณหัวอ่านตรงกลาง
    DigitalPin.P15,  // สัญญาณหัวอ่านขวากลาง
    DigitalPin.P16  // สัญญาณหัวอ่านขวาสุด
]
const TURN_TOLERANCE_DEG = 4  // เผื่อมุมรถไหล 4° สั่งเบรกที่ 86° สำหรับเป้าหมาย 90° เพิ่มค่านี้เพื่อเบรกเร็วขึ้น
let address = 0x29  // ที่อยู่ I²C ตั้งต้นของเซนเซอร์สี ฟังก์ชันตรวจรุ่นจะเลือกอีกครั้ง
let busy = true  // กันปุ่ม A ไว้ระหว่างเปิดเครื่องและเตรียมเข็มทิศ
let stopped = false  // สถานะยกเลิกรอบ ปุ่ม B จะเปลี่ยนค่านี้

function stopWheels() {  // รวมคำสั่งหยุดล้อไว้จุดเดียว
    motionbit.brakeMotor(MotionBitMotorChannel.All)  // เบรกมอเตอร์ทั้งสี่ช่องพร้อมกัน
}

input.onButtonPressed(Button.B, function () {  // ขั้นตอนเมื่อกดปุ่ม B ระหว่างทำงาน
    stopped = true  // จำว่าผู้ใช้ยกเลิกรอบนี้แล้ว
    stopWheels()  // เบรกล้อทันทีที่รับเหตุการณ์ปุ่ม B
})

function writeRegister(reg: number, value: number) {  // ส่งค่าตั้งหนึ่งค่าไปยังรีจิสเตอร์ของ TCS3472
    let data = pins.createBuffer(2)  // เตรียมข้อมูลสองไบต์สำหรับคำสั่งและค่าที่จะเขียน
    data[0] = 0x80 | reg  // ตั้งบิตคำสั่งของ TCS3472 แล้วใส่หมายเลขรีจิสเตอร์
    data[1] = value  // ใส่ค่าที่ต้องการตั้งลงไบต์ที่สอง
    pins.i2cWriteBuffer(address, data)  // ส่งข้อมูลไปยังที่อยู่ I²C ที่เลือกไว้
}

function sensorReady(): boolean {  // ตรวจหาและตั้งค่าเซนเซอร์สีก่อนเริ่มค้นหากระป๋อง
    for (let addr of [0x29, 0x39]) {  // ลองสองที่อยู่ I²C ที่ใช้ในตระกูล TCS3472
        address = addr  // เลือกที่อยู่ที่จะทดสอบในรอบนี้
        pins.i2cWriteNumber(address, 0x92, NumberFormat.UInt8LE, true)  // เลือกรีจิสเตอร์รหัสชิป และคงบัสไว้สำหรับการอ่านต่อ
        let id = pins.i2cReadNumber(address, NumberFormat.UInt8LE)  // อ่านรหัสชิปขนาดหนึ่งไบต์
        if (id == 0x44 || id == 0x4d) {  // ตั้งค่าเฉพาะเมื่อพบรหัสชิปที่รองรับ
            writeRegister(0x01, 0xeb)  // ตั้งช่วงสะสมแสงประมาณ 50 มิลลิวินาทีต่อการวัด
            writeRegister(0x0f, 1)  // ตั้งอัตราขยายสัญญาณแสงเป็น 4 เท่า
            writeRegister(0x00, 1)  // เปิดไฟเลี้ยงวงจรวัดภายในชิป
            basic.pause(5)  // รอวงจรเริ่มทำงาน 5 มิลลิวินาที
            writeRegister(0x00, 3)  // เริ่มแปลงแสงเป็นค่าดิจิทัล
            basic.pause(60)  // รอให้ได้ตัวอย่างสีชุดแรก
            return true  // แจ้งว่ารอบนี้เปิดใช้การอ่านสีได้
        }
    }
    return false  // ค้นหากระป๋องต่อได้โดยข้ามการรายงานสี
}

function floorColor(): number {  // จำแนกพื้นเป็น 0 พื้นทั่วไป 1 แดง หรือ 2 น้ำเงิน
    pins.i2cWriteNumber(address, 0xb4, NumberFormat.UInt8LE, true)  // เริ่มอ่านจากช่องความสว่างและเลื่อนไปช่องสีถัดไปอัตโนมัติ
    let data = pins.i2cReadBuffer(address, 8)  // อ่านสี่ช่องพร้อมกัน ช่องละสองไบต์
    let clear = data.getNumber(NumberFormat.UInt16LE, 0)  // แสงรวมจากไบต์ 0–1 ใช้คัดค่าที่มืดเกินไป
    let red = data.getNumber(NumberFormat.UInt16LE, 2)  // ค่าช่องแดงจากไบต์ 2–3
    let green = data.getNumber(NumberFormat.UInt16LE, 4)  // ค่าช่องเขียวจากไบต์ 4–5
    let blue = data.getNumber(NumberFormat.UInt16LE, 6)  // ค่าช่องน้ำเงินจากไบต์ 6–7
    if (clear < 30) return 0  // ถ้าแสงรวมน้อยกว่า 30 ให้ถือเป็นพื้นทั่วไป
    if (red > green * 1.35 && red > blue * 1.35) return 1  // ส่งรหัส 1 เมื่อแดงเด่นกว่าเขียวและน้ำเงิน 1.35 เท่า
    if (blue > green * 1.2 && blue > red * 1.35) return 2  // ส่งรหัส 2 เมื่อน้ำเงินเด่นกว่าเขียว 1.2 เท่าและแดง 1.35 เท่า
    return 0  // สีที่เหลือจัดเป็นพื้นทั่วไป
}

function driveSides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, trim: number = 0) {  // ขับล้อแยกทิศซ้าย–ขวา โดย trim คือกำลังที่ผ่อนด้านหนึ่ง
    if (left == right && trim == 0) {  // เมื่อสั่งทิศเดียวกันและสองฝั่งใช้กำลังเท่ากัน
        motionbit.runMotor(MotionBitMotorChannel.All, left, SPEED)  // ใช้คำสั่ง All เพื่อขับ M1–M4 พร้อมกัน
        return  // จบคำสั่งนี้เมื่อขับครบสี่ล้อแล้ว
    }
    let leftSpeed = SPEED + Math.min(0, trim)  // ลดกำลังฝั่งซ้ายเมื่อ trim ติดลบ
    let rightSpeed = SPEED - Math.max(0, trim)  // ลดกำลังฝั่งขวาเมื่อ trim เป็นบวก
    motionbit.runMotor(MotionBitMotorChannel.M1, left, leftSpeed)  // ส่งทิศและกำลังให้มอเตอร์ซ้าย M1
    motionbit.runMotor(MotionBitMotorChannel.M2, left, leftSpeed)  // ส่งค่าเดียวกันให้มอเตอร์ซ้าย M2
    motionbit.runMotor(MotionBitMotorChannel.M3, right, rightSpeed)  // ส่งทิศและกำลังให้มอเตอร์ขวา M3
    motionbit.runMotor(MotionBitMotorChannel.M4, right, rightSpeed)  // ส่งค่าเดียวกันให้มอเตอร์ขวา M4
}

function opposite(dir: MotionBitMotorDirection): MotionBitMotorDirection {  // หาทิศกลับข้างสำหรับถอยรถหรือหมุนอยู่กับที่
    if (dir == MotionBitMotorDirection.Forward) return MotionBitMotorDirection.Backward  // ถ้าสั่งเดินหน้าอยู่ ทิศตรงข้ามคือถอย
    return MotionBitMotorDirection.Forward  // ถ้ารับทิศถอย ให้คืนทิศเดินหน้า
}

function nb142Detected(): boolean {  // ตรวจว่าหัวอ่าน NB142 อย่างน้อยหนึ่งช่องยังเจอพื้นที่
    for (let i = 0; i < NB142_PINS.length; i++) {  // ไล่อ่านพินทั้งห้าตามรายการด้านบน
        if (pins.digitalReadPin(NB142_PINS[i]) == NB142_DETECTED_LEVEL) return true  // ถ้าค่าของช่องนี้ตรงกับระดับตรวจเจอ ให้รายงานว่าพบพื้นที่
    }
    return false  // ครบห้าช่องแล้วไม่มีช่องใดตรวจเจอ
}

function headingError(target: number, heading: number): number {  // หามุมต่างแบบมีเครื่องหมาย แม้ทิศจะข้าม 359° ไป 0°
    return (target - heading + 540) % 360 - 180  // เลือกมุมระยะสั้นในช่วง −180° ถึงต่ำกว่า 180°
}

function objectInReach(): boolean {  // วัดด้วย HC-SR04 แล้วตอบว่าวัตถุอยู่ในระยะคีบหรือยัง
    pins.digitalWritePin(DigitalPin.P0, 0)  // ดึง TRIG ที่ P0 ลงต่ำก่อนส่งพัลส์
    control.waitMicros(2)  // คงระดับต่ำ 2 ไมโครวินาที
    pins.digitalWritePin(DigitalPin.P0, 1)  // ยก TRIG ขึ้นสูงเพื่อเริ่มพัลส์
    control.waitMicros(10)  // คงระดับสูง 10 ไมโครวินาที
    pins.digitalWritePin(DigitalPin.P0, 0)  // จบพัลส์ TRIG ให้โมดูลเริ่มวัด
    let echoUs = pins.pulseIn(DigitalPin.P1, PulseValue.High, 25000)  // วัดความกว้างพัลส์ ECHO ที่ P1 รอได้สูงสุด 25,000 ไมโครวินาที
    return echoUs > 0 && echoUs <= PICKUP_DISTANCE_CM * 58  // รับเฉพาะพัลส์ที่มีจริงและอยู่ในระยะที่ตั้งไว้ ประมาณ 58 ไมโครวินาทีต่อซม.
}

function searchForCan(readColors: boolean): boolean {  // ควบคุมล้อและตรวจวัตถุซ้ำจนพบกระป๋องหรือยกเลิกรอบ
    let target = input.compassHeading()  // จำทิศเริ่มต้นจากเข็มทิศไว้เป็นแนวเดินตรง
    if (target < 0 || target >= 360) return false  // ยกเลิกการค้นหาเมื่อเข็มทิศเริ่มต้นอยู่นอกช่วง 0–359°
    let turning = false  // เริ่มรอบในโหมดเดินตรง
    let turnStarted = 0  // เตรียมเก็บเวลาเริ่มหมุนเพื่อจับเวลาครบ 5 วินาที
    let turnEntry = 0  // เตรียมเก็บทิศตั้งต้นสำหรับวัดมุมหมุนขวา
    let pivotPowered = false  // จำว่าได้สั่งล้อให้หมุนสวนกันไปแล้วหรือยัง
    let nextPing = 0  // เวลาเร็วที่สุดที่จะยิงอัลตราโซนิกครั้งถัดไป
    let previousColor = 0  // จำสีครั้งก่อนเพื่อรายงานเฉพาะตอนเปลี่ยนแถบ
    let nearLastSample = false  // เริ่มโดยยังไม่มีผลวัดใกล้ให้ยืนยัน
    let trim = 0  // เริ่มโดยให้ล้อสองฝั่งใช้กำลังเท่ากัน
    let starting = true  // ให้คำสั่งเดินหน้าครั้งแรกออกตัวพร้อมกันทั้งสี่ล้อ
    while (!stopped) {  // วนค้นหาตราบใดที่ยังไม่ได้กด B
        let detected = nb142Detected()  // อ่านว่า NB142 ยังตรวจเจออย่างน้อยหนึ่งช่องหรือไม่
        let near = false  // เริ่มรอบการอ่านโดยยังไม่มีผลระยะใกล้
        if (detected && input.runningTime() >= nextPing) {  // ยิงวัดเมื่อยังอยู่ในพื้นที่และถึงเวลาวัดรอบใหม่
            near = objectInReach()  // ตรวจว่ามีวัตถุใกล้พอจะคีบหรือไม่
            nextPing = input.runningTime() + 65  // เว้นอย่างน้อย 65 มิลลิวินาทีก่อนยิงครั้งถัดไป
            detected = nb142Detected()  // เช็กพื้นที่ซ้ำเพราะรถอาจเคลื่อนระหว่างรอเสียงสะท้อน
        }
        if (stopped) return false  // ถ้ากด B ระหว่างอ่านเซนเซอร์ ให้ออกจากการค้นหา
        if (!detected && !turning) {  // เมื่อทั้งห้าช่องไม่เจอและรถยังไม่ได้กำลังเลี้ยว
            stopWheels()  // เบรกก่อนเปลี่ยนจากเดินหน้าเป็นถอย
            let entry = input.compassHeading()  // จำทิศรถก่อนถอยไว้เป็นจุดเริ่มของการเลี้ยว
            if (entry < 0 || entry >= 360 || stopped) return false  // ยกเลิกก่อนถอยถ้าเข็มทิศอ่านไม่ได้หรือกด B
            driveSides(opposite(LEFT), opposite(RIGHT))  // ขับล้อทั้งสองฝั่งย้อนทิศเดินหน้าเพื่อถอยพร้อมกัน
            basic.pause(REVERSE_3CM_MS)  // ถอยตามเวลาที่ปรับไว้สำหรับระยะประมาณ 3 ซม.
            stopWheels()  // เบรกเมื่อครบเวลาถอย
            if (stopped) return false  // ถ้ากด B ระหว่างถอย ให้จบรอบก่อนเริ่มหมุน
            target = (entry + 90) % 360  // กำหนดทิศใหม่ทางขวา 90° ถ้าแก้มุม ให้แก้เลขเดียวกันที่เงื่อนไขจบการหมุนด้วย
            turning = true  // สลับเข้าโหมดหมุนขวา
            starting = true  // เตรียมออกตัวเต็มกำลังอีกครั้งเมื่อหมุนเสร็จ
            trim = 0  // ล้างส่วนต่างกำลังที่ใช้แก้รถเบนก่อนหน้า
            turnEntry = entry  // ใช้ทิศก่อนถอยเป็นศูนย์สำหรับนับองศาที่หมุน
            pivotPowered = false  // อนุญาตให้ส่งคำสั่งหมุนครั้งแรก
            turnStarted = input.runningTime()  // เริ่มจับเวลาการหมุนที่จุดนี้
            nearLastSample = false  // ทิ้งผลวัดวัตถุใกล้จากแนวเดินเดิม
            continue  // กลับไปอ่านเซนเซอร์และเริ่มควบคุมการเลี้ยว
        }
        if (detected && near) {  // พิจารณาคีบเมื่อยังเจอพื้นที่และวัตถุอยู่ในระยะ
            stopWheels()  // เบรกล้อทันทีตั้งแต่ผลใกล้ครั้งแรก
            trim = 0  // ล้างกำลังชดเชยขณะรถหยุด
            starting = true  // ถ้าต้องเดินหน้าต่อ ให้ออกตัวสี่ล้อพร้อมกัน
            pivotPowered = false  // ถ้าต้องหมุนต่อ ให้ส่งคำสั่งมอเตอร์ใหม่หลังเบรก
            if (nearLastSample) return true  // ถ้าวัดใกล้เป็นครั้งที่สอง ส่งผลยืนยันให้เริ่มคีบ
            nearLastSample = true  // บันทึกผลใกล้ครั้งแรกไว้รอยืนยัน
            basic.pause(65)  // รอ 65 มิลลิวินาทีขณะล้อหยุดก่อนวัดยืนยัน
            continue  // เริ่มรอบใหม่เพื่ออ่านระยะซ้ำ
        }
        nearLastSample = false  // ล้างผลใกล้เมื่อเงื่อนไขยืนยันไม่ครบ
        if (readColors) {  // อ่านสีเฉพาะเมื่อพบ TCS3472 ตอนเตรียมตัว
            let color = floorColor()  // จำแนกสีพื้นใต้หัวอ่าน
            if (color != previousColor) {  // เปรียบเทียบกับสีครั้งก่อน
                if (color == 1) serial.writeLine("RED")  // เมื่อเข้าแถบแดง ให้ส่ง RED ทาง Serial
                if (color == 2) serial.writeLine("BLUE")  // เมื่อเข้าแถบน้ำเงิน ให้ส่ง BLUE ทาง Serial
                previousColor = color  // จำสีนี้ไว้เทียบในรอบถัดไป
            }
        }
        let heading = input.compassHeading()  // อ่านทิศปัจจุบันเพื่อปรับล้อหรือวัดมุมเลี้ยว
        if (heading < 0 || heading >= 360 || stopped) return false  // ถ้าเข็มทิศอ่านไม่ได้หรือกด B ให้จบการค้นหา
        let error = headingError(target, heading)  // หาว่าต้องแก้แนวไปทางไหนและกี่องศา
        if (turning && input.runningTime() - turnStarted >= 5000) return false  // ถ้าหมุนไม่สำเร็จใน 5,000 มิลลิวินาที ให้ยกเลิกรอบ
        if (!turning) {  // เลือกควบคุมการเดินตรงเมื่ออยู่นอกโหมดหมุน
            let amount = Math.min(80, 3 * Math.max(0, Math.abs(error) - 2))  // ยอมให้เบน 2° แล้วชดเชย 3 หน่วยต่อองศาที่เกิน จำกัดส่วนต่างไว้ที่ 80
            let desired = error > 0 ? amount : -amount  // กำหนดฝั่งที่จะผ่อนกำลังตามเครื่องหมายมุม
            if (starting) {  // แยกคำสั่งเดินหน้าครั้งแรกหลังเริ่มหรือหยุด
                trim = 0  // ออกตัวด้วยกำลังเท่ากันทั้งสี่ล้อ ค่าปัจจุบันคือ 255
                starting = false  // เปิดให้ปรับกำลังล้อตั้งแต่รอบถัดไป
            } else {  // ระหว่างวิ่งใช้ค่าจากเข็มทิศแก้แนว
                trim += Math.max(-16, Math.min(16, desired - trim))  // ขยับส่วนต่างกำลังเข้าหาค่าเป้าทีละไม่เกิน 16 เพื่อให้เปลี่ยนทิศนุ่มขึ้น
            }
            driveSides(LEFT, RIGHT, trim)  // ให้ทั้งสี่ล้อเดินหน้าโดยผ่อนกำลังตามค่าที่คำนวณ
        } else if (headingError(heading, turnEntry) < 90 - TURN_TOLERANCE_DEG) {  // หมุนต่อจนถึงมุมเป้าลบระยะเผื่อเบรก ถ้าเปลี่ยน 90 ให้แก้มุมเป้าด้านบนด้วย
            if (!pivotPowered) {  // ส่งคำสั่งหมุนเฉพาะเมื่อยังไม่ได้จ่ายกำลังสำหรับการหมุนนี้
                driveSides(LEFT, opposite(RIGHT))  // หมุนขวาอยู่กับที่โดยให้ล้อซ้ายเดินหน้าและล้อขวาถอย
                pivotPowered = true  // จำว่าล้อกำลังหมุนต่อเนื่องอยู่แล้ว
            }
            basic.pause(10)  // รอ 10 มิลลิวินาทีก่อนตรวจทิศอีกครั้งโดยล้อยังหมุน
            continue  // วนตรวจมุมและเซนเซอร์โดยข้ามช่วงพักของการเดินตรง
        } else {  // เข้าขั้นจบการเลี้ยวเมื่อหมุนถึงมุมเบรกแล้ว
            stopWheels()  // เบรกทั้งสี่ล้อเมื่อถึงมุมที่ตั้ง
            turning = false  // กลับเข้าโหมดเดินตรง
            pivotPowered = false  // ล้างสถานะจ่ายกำลังหมุนไว้สำหรับการเลี้ยวครั้งหน้า
        }
        basic.pause(65)  // พัก 65 มิลลิวินาทีก่อนควบคุมล้อรอบถัดไป
    }
    return false  // ส่งผลยกเลิกเมื่อปุ่ม B ทำให้หลุดจากวงรอบค้นหา
}

function moveRack(angle: number) {  // สั่งเซอร์โวตัวล่างให้ยกหรือลดชุดคีบไปยังมุมที่รับมา
    if (stopped) return  // ข้ามการขยับรางถ้ากด B
    motionbit.setServoPosition(MotionBitServoChannel.S1, angle)  // ส่งมุมให้เซอร์โว S1 ที่ขับเฟืองราง
    basic.pause(550)  // เผื่อให้รางเคลื่อนถึงตำแหน่ง 550 มิลลิวินาที
}

function rotateGrip(afterGrip: boolean) {  // จัดมุมเซอร์โวคู่หมุนตามท่าเตรียมหรือท่าหลังหนีบ
    if (stopped) return  // ข้ามการหมุนถ้ากด B
    motionbit.setServoPosition(MotionBitServoChannel.S4, afterGrip ? ROTATE_LEFT_AFTER_GRIP : ROTATE_LEFT_READY)  // สั่ง S4 ไปมุมเตรียมหรือมุมหลังหนีบของด้านซ้าย
    motionbit.setServoPosition(MotionBitServoChannel.S5, afterGrip ? ROTATE_RIGHT_AFTER_GRIP : ROTATE_RIGHT_READY)  // สั่ง S5 ไปมุมเตรียมหรือมุมหลังหนีบของด้านขวา
    basic.pause(550)  // รอให้คู่หมุนเคลื่อนถึงมุมก่อนทำขั้นต่อไป
}

function moveGrip(close: boolean) {  // สั่งปากคีบสองข้างให้หุบหรืออ้า
    if (stopped) return  // ข้ามการหนีบถ้ากด B
    motionbit.setServoPosition(MotionBitServoChannel.S2, close ? GRIP_LEFT_CLOSED : GRIP_LEFT_OPEN)  // สั่ง S2 ไปมุมหุบหรืออ้าของปากคีบซ้าย
    motionbit.setServoPosition(MotionBitServoChannel.S3, close ? GRIP_RIGHT_CLOSED : GRIP_RIGHT_OPEN)  // สั่ง S3 ไปมุมหุบหรืออ้าของปากคีบขวา
    basic.pause(550)  // รอให้ปากคีบทั้งคู่ไปถึงตำแหน่ง 550 มิลลิวินาที
}

function runRoute(): boolean {  // ลำดับงานหนึ่งรอบ แก้ตรงนี้หากต้องการสลับขั้นตอนของแขน
    let readColors = sensorReady()  // ตรวจและตั้งค่าเซนเซอร์สี ผลที่ได้ใช้เปิดการรายงานสี
    moveRack(RACK_UP)  // ยกรางขึ้นเพื่อเตรียมวิ่ง
    rotateGrip(false)  // จัดคู่หมุน S4/S5 ไว้ที่มุมเตรียม
    moveGrip(false)  // อ้าปากคีบ S2/S3 ก่อนค้นหา
    let found = searchForCan(readColors)  // เริ่มขับค้นหาและรอผลยืนยันระยะจากอัลตราโซนิก
    stopWheels()  // หยุดล้อก่อนตัดสินใจขยับแขน
    if (!found || stopped) return false  // ถ้าค้นหาไม่สำเร็จหรือกด B ให้จบรอบก่อนขยับแขน
    moveRack(RACK_DOWN)  // ลดราง S1 ให้ปากคีบอยู่ระดับกระป๋อง
    moveGrip(true)  // หุบ S2/S3 พร้อมกันเพื่อจับกระป๋อง
    rotateGrip(true)  // สั่ง S4/S5 ไปมุมหลังหนีบ ปัจจุบันเท่าท่าเตรียมจึงค้างที่ 90°
    return !stopped  // รายงานว่าทำงานครบหากไม่มีการกดหยุด
}

input.onButtonPressed(Button.A, function () {  // ขั้นตอนเริ่มรอบเมื่อกด A บนตัว micro:bit
    if (busy) return  // ข้ามการกด A ซ้ำขณะอีกรอบกำลังทำงาน
    busy = true  // ล็อกการเริ่มรอบใหม่จนกว่างานนี้จะเสร็จ
    stopped = false  // ล้างคำสั่งหยุดจากรอบก่อน
    basic.clearScreen()  // ล้างตัวอักษรบนจอก่อนออกตัว
    let done = runRoute()  // เริ่มลำดับงานและเก็บว่าทำสำเร็จหรือไม่
    stopWheels()  // เบรกล้ออีกครั้งก่อนแสดงผล
    if (done) basic.showIcon(IconNames.Yes)  // แสดงเครื่องหมายถูกเมื่อทำครบลำดับ
    else basic.showIcon(IconNames.No)  // แสดงกากบาทให้ผู้ใช้เห็นว่ารอบหยุดก่อนสำเร็จ
    busy = false  // ปลดล็อกให้กด A เริ่มรอบถัดไป
})

stopWheels()  // ตอนเปิดเครื่องให้ล้อหยุดไว้ก่อน
input.compassHeading()  // เรียกเข็มทิศขณะรถจอด เพื่อให้ปรับเทียบก่อนเริ่มถ้าบอร์ดร้องขอ
busy = false  // ให้เริ่มรอบได้หลังขั้นเตรียมเข็มทิศ
basic.showString("A")  // แสดง A เพื่อบอกว่าพร้อมรับปุ่มเริ่ม
