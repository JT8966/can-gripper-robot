// หุ่นคีบกระป๋อง · MOTION:BIT Pro
// เริ่มอ่านที่ runRoute() เพื่อดูลำดับงาน หรือแก้ค่ามุม ระยะ และกำลังล้อที่ต้นไฟล์

const RACK_DOWN_COMMAND = 75
const RACK_DOWN_MS = 0
const ROTATE_RIGHT_COMMAND = 105
const ROTATE_RIGHT_MS = 0
const GRIP_RIGHT_OPEN = 10
const GRIP_LEFT_OPEN = 20
const GRIP_RIGHT_CLOSED = GRIP_RIGHT_OPEN
const GRIP_LEFT_CLOSED = GRIP_LEFT_OPEN
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
const TURN_DEG = 90  // มุมหมุนขวาเมื่อ NB142 หลุดกรอบ
const TURN_TOLERANCE_DEG = 4  // เผื่อมุมรถไหล 4° สั่งเบรกที่ 86° สำหรับเป้าหมาย 90° เพิ่มค่านี้เพื่อเบรกเร็วขึ้น
let address = 0x29
let busy = true
let stopped = false

function stopWheels() {
    motionbit.brakeMotor(MotionBitMotorChannel.All)
}

input.onButtonPressed(Button.B, function () {
    stopped = true
    stopWheels()
    motionbit.setServoPosition(MotionBitServoChannel.S1, 90)
    motionbit.setServoPosition(MotionBitServoChannel.S2, 90)
})

function writeRegister(reg: number, value: number) {
    let data = pins.createBuffer(2)
    data[0] = 0x80 | reg
    data[1] = value
    pins.i2cWriteBuffer(address, data)
}

function sensorReady(): boolean {
    for (let addr of [0x29, 0x39]) {
        address = addr
        pins.i2cWriteNumber(address, 0x92, NumberFormat.UInt8LE, true)
        let id = pins.i2cReadNumber(address, NumberFormat.UInt8LE)
        if (id == 0x44 || id == 0x4d) {
            writeRegister(0x01, 0xeb)  // ตั้งช่วงสะสมแสงประมาณ 50 มิลลิวินาทีต่อการวัด
            writeRegister(0x0f, 1)  // ตั้งอัตราขยายสัญญาณแสงเป็น 4 เท่า
            writeRegister(0x00, 1)  // เปิดไฟเลี้ยงวงจรวัดภายในชิป
            basic.pause(5)
            writeRegister(0x00, 3)  // เริ่มแปลงแสงเป็นค่าดิจิทัล
            basic.pause(60)
            return true
        }
    }
    return false
}

function floorColor(): number {  // จำแนกพื้นเป็น 0 พื้นทั่วไป 1 แดง หรือ 2 น้ำเงิน
    pins.i2cWriteNumber(address, 0xb4, NumberFormat.UInt8LE, true)
    let data = pins.i2cReadBuffer(address, 8)
    let clear = data.getNumber(NumberFormat.UInt16LE, 0)
    let red = data.getNumber(NumberFormat.UInt16LE, 2)
    let green = data.getNumber(NumberFormat.UInt16LE, 4)
    let blue = data.getNumber(NumberFormat.UInt16LE, 6)
    if (clear < 30) return 0
    if (red > green * 1.35 && red > blue * 1.35) return 1
    if (blue > green * 1.2 && blue > red * 1.35) return 2
    return 0
}

function driveSides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, trim: number = 0) {  // ขับล้อแยกทิศซ้าย–ขวา โดย trim คือกำลังที่ผ่อนด้านหนึ่ง
    if (left == right && trim == 0) {
        motionbit.runMotor(MotionBitMotorChannel.All, left, SPEED)
        return
    }
    let leftSpeed = SPEED + Math.min(0, trim)
    let rightSpeed = SPEED - Math.max(0, trim)
    motionbit.runMotor(MotionBitMotorChannel.M1, left, leftSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M2, left, leftSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M3, right, rightSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M4, right, rightSpeed)
}

function opposite(dir: MotionBitMotorDirection): MotionBitMotorDirection {
    if (dir == MotionBitMotorDirection.Forward) return MotionBitMotorDirection.Backward
    return MotionBitMotorDirection.Forward
}

function nb142Mask(): number {
    let mask = 0
    for (let i = 0; i < NB142_PINS.length; i++) {
        if (pins.digitalReadPin(NB142_PINS[i]) == NB142_DETECTED_LEVEL) mask |= 1 << i
    }
    return mask
}

// หันเข้าหาฝั่งที่ยังติด ถ้าสองฝั่งสมดุลให้คงทิศแก้ล่าสุด
function alignmentDirection(mask: number, previous: number): number {
    let balance = 0
    for (let i = 0; i < NB142_PINS.length; i++) {
        if ((mask & (1 << i)) != 0) balance += i - 2
    }
    if (balance == 0) return previous
    return balance > 0 ? 1 : -1
}

function headingError(target: number, heading: number): number {
    return (target - heading + 540) % 360 - 180
}

function objectInReach(): boolean {
    pins.digitalWritePin(DigitalPin.P0, 0)
    control.waitMicros(2)
    pins.digitalWritePin(DigitalPin.P0, 1)
    control.waitMicros(10)
    pins.digitalWritePin(DigitalPin.P0, 0)
    let echoUs = pins.pulseIn(DigitalPin.P1, PulseValue.High, 25000)
    return echoUs > 0 && echoUs <= PICKUP_DISTANCE_CM * 58
}

function searchForCan(readColors: boolean): boolean {
    let target = input.compassHeading()
    if (target < 0 || target >= 360) return false
    let turning = false
    let turnStarted = 0
    let turnEntry = 0
    let nextPing = 0
    let previousColor = 0
    let nearLastSample = false
    let trim = 0
    let wheelsMoving = false
    let aligning = false
    let direction = 1
    while (!stopped) {
        let mask = nb142Mask()
        let near = false
        if (mask == 31 && input.runningTime() >= nextPing) {
            near = objectInReach()
            nextPing = input.runningTime() + 65
            mask = nb142Mask()
        }
        if (stopped) return false
        if (mask != 0 && mask != 31) {
            if (!aligning) {
                stopWheels()
                turnStarted = input.runningTime()
                turning = false
                aligning = true
                wheelsMoving = false
            }
            if (input.runningTime() - turnStarted >= 5000) return false
            let next = alignmentDirection(mask, direction)
            if (!wheelsMoving || next != direction) {
                if (next > 0) driveSides(LEFT, opposite(RIGHT))
                else driveSides(opposite(LEFT), RIGHT)
                direction = next
                wheelsMoving = true
            }
            nearLastSample = false
            basic.pause(10)
            continue
        }
        if (aligning) {
            stopWheels()
            aligning = false
            wheelsMoving = false
            if (mask == 31) {
                target = input.compassHeading()
                if (target < 0 || target >= 360 || stopped) return false
            }
        }
        if (mask == 0 && !turning) {
            stopWheels()
            turnEntry = input.compassHeading()
            if (turnEntry < 0 || turnEntry >= 360 || stopped) return false
            driveSides(opposite(LEFT), opposite(RIGHT))
            basic.pause(REVERSE_3CM_MS)
            stopWheels()
            if (stopped) return false
            target = (turnEntry + TURN_DEG) % 360
            turning = true
            direction = 1
            wheelsMoving = false
            turnStarted = input.runningTime()
            nearLastSample = false
            continue
        }
        if (mask == 31 && near) {
            stopWheels()
            wheelsMoving = false
            if (nearLastSample) return true
            nearLastSample = true
            basic.pause(65)
            continue
        }
        nearLastSample = false
        if (readColors) {
            let color = floorColor()
            if (color != previousColor) {
                if (color == 1) serial.writeLine("RED")
                if (color == 2) serial.writeLine("BLUE")
                previousColor = color
            }
        }
        let heading = input.compassHeading()
        if (heading < 0 || heading >= 360 || stopped) return false
        if (turning && input.runningTime() - turnStarted >= 5000) return false
        if (!turning) {
            if (wheelsMoving) {
                let error = headingError(target, heading)
                let amount = Math.min(80, 3 * Math.max(0, Math.abs(error) - 2))
                let desired = error > 0 ? amount : -amount
                trim += Math.max(-16, Math.min(16, desired - trim))
            } else {
                trim = 0  // ออกตัวเต็มกำลังพร้อมกันทั้งสี่ล้อ
                wheelsMoving = true
            }
            driveSides(LEFT, RIGHT, trim)
        } else if (headingError(heading, turnEntry) < TURN_DEG - TURN_TOLERANCE_DEG) {
            if (!wheelsMoving) {
                driveSides(LEFT, opposite(RIGHT))
                wheelsMoving = true
            }
            basic.pause(10)
            continue
        } else {
            stopWheels()
            turning = false
            wheelsMoving = false
        }
        basic.pause(65)
    }
    return false
}

function runTimedServo(channel: MotionBitServoChannel, command: number, duration: number) {
    if (stopped || duration <= 0) return
    motionbit.setServoPosition(channel, command)
    basic.pause(duration)
    motionbit.setServoPosition(channel, 90)
}

function setGrip(right: number, left: number) {
    motionbit.setServoPosition(MotionBitServoChannel.S4, right)
    motionbit.setServoPosition(MotionBitServoChannel.S5, left)
}

function runRoute(): boolean {
    setGrip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
    let found = searchForCan(sensorReady())
    stopWheels()
    if (!found || stopped) return false
    runTimedServo(MotionBitServoChannel.S1, RACK_DOWN_COMMAND, RACK_DOWN_MS)
    if (stopped) return false
    setGrip(GRIP_RIGHT_CLOSED, GRIP_LEFT_CLOSED)
    basic.pause(550)
    runTimedServo(MotionBitServoChannel.S2, ROTATE_RIGHT_COMMAND, ROTATE_RIGHT_MS)
    return !stopped
}

input.onButtonPressed(Button.A, function () {
    if (busy) return
    busy = true
    stopped = false
    basic.clearScreen()
    let done = runRoute()
    if (done) basic.showIcon(IconNames.Yes)
    else basic.showIcon(IconNames.No)
    busy = false
})

stopWheels()
basic.showIcon(IconNames.Yes)
motionbit.setServoPosition(MotionBitServoChannel.S2, 90)
setGrip(GRIP_RIGHT_OPEN, GRIP_LEFT_OPEN)
basic.pause(1000)
input.compassHeading()  // เรียกเข็มทิศขณะรถจอด เพื่อให้ปรับเทียบก่อนเริ่มถ้าบอร์ดร้องขอ
busy = false
basic.showString("A")
