// MOTION:BIT Pro | ปรับมุมให้ตรงกับแขนจริงก่อนติดกระป๋อง
const RACK_UP = 85
const RACK_DOWN = 55
// ค่าตั้งต้นสำหรับสองฝั่งที่ติดตั้งหันเข้าหากัน ปรับแต่ละฝั่งตามกลไกจริง
const ELBOW_LEFT_FOLDED = 90
const ELBOW_RIGHT_FOLDED = 90
const ELBOW_LEFT_REACH = 110
const ELBOW_RIGHT_REACH = 70
const GRIP_LEFT_OPEN = 65
const GRIP_RIGHT_OPEN = 115
const GRIP_LEFT_CLOSED = 95
const GRIP_RIGHT_CLOSED = 85
const SPEED = 65 // 0–255
const LEFT = MotionBitMotorDirection.Forward  // เดินหน้าฝั่งซ้าย: M1A และ M2A
const RIGHT = MotionBitMotorDirection.Forward // เดินหน้าฝั่งขวา: M3A และ M4A
const SEARCH_MS = 8000
const BLACK_LEVEL = 1
// หัวอ่าน NB142 เรียงจากซ้ายไปขวาตามทิศเดินหน้าของรถ
const NB142_PINS = [
    DigitalPin.P12, // ซ้ายสุด
    DigitalPin.P13, // ซ้ายกลาง
    DigitalPin.P14, // กลาง
    DigitalPin.P15, // ขวากลาง
    DigitalPin.P16  // ขวาสุด
]
// มุมจากแนวเริ่มต้น: บวกเลี้ยวขวา ลบเลี้ยวซ้าย
const TURN_AFTER_PICKUP_DEG = 90
const TURN_TOLERANCE_DEG = 4
let address = 0x29
let busy = true
let stopped = false

function stopWheels() {
    motionbit.brakeMotor(MotionBitMotorChannel.All)
}

input.onButtonPressed(Button.B, function () {
    stopped = true
    stopWheels()
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
            writeRegister(0x01, 0xeb) // 50 ms integration
            writeRegister(0x0f, 1) // 4x gain
            writeRegister(0x00, 1)
            basic.pause(5)
            writeRegister(0x00, 3)
            basic.pause(60)
            return true
        }
    }
    return false
}

// 0 = พื้นทั่วไป, 1 = แดง, 2 = น้ำเงิน
function floorColor(): number {
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

function driveSides(left: MotionBitMotorDirection, right: MotionBitMotorDirection, leftSpeed: number, rightSpeed: number) {
    motionbit.runMotor(MotionBitMotorChannel.M1, left, leftSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M2, left, leftSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M3, right, rightSpeed)
    motionbit.runMotor(MotionBitMotorChannel.M4, right, rightSpeed)
}

function opposite(dir: MotionBitMotorDirection): MotionBitMotorDirection {
    if (dir == MotionBitMotorDirection.Forward) return MotionBitMotorDirection.Backward
    return MotionBitMotorDirection.Forward
}

function atBorder(): boolean {
    for (let i = 0; i < NB142_PINS.length; i++) {
        if (pins.digitalReadPin(NB142_PINS[i]) == BLACK_LEVEL) return true
    }
    return false
}

function headingError(target: number, heading: number): number {
    return (target - heading + 540) % 360 - 180
}

function pivotTo(target: number): boolean {
    let start = input.runningTime()
    let settled = 0
    while (!stopped && !atBorder() && input.runningTime() - start < 5000) {
        let heading = input.compassHeading()
        if (heading < 0 || heading >= 360 || stopped) break
        let error = headingError(target, heading)
        if (Math.abs(error) <= TURN_TOLERANCE_DEG) {
            stopWheels()
            settled++
            if (settled >= 3) return true
        } else {
            settled = 0
            let speed = Math.min(SPEED, 40 + Math.abs(error))
            if (error > 0) driveSides(LEFT, opposite(RIGHT), speed, speed)
            else driveSides(opposite(LEFT), RIGHT, speed, speed)
        }
        basic.pause(30)
    }
    stopWheels()
    return false
}

function driveTo(color: number, target: number): boolean {
    let start = input.runningTime()
    let hits = 0
    while (!stopped && !atBorder() && input.runningTime() - start < SEARCH_MS) {
        if (floorColor() == color) hits++
        else hits = 0
        if (hits >= 2) break
        let heading = input.compassHeading()
        if (heading < 0 || heading >= 360 || stopped) break
        let correction = Math.max(-SPEED, Math.min(SPEED, 2 * headingError(target, heading)))
        driveSides(LEFT, RIGHT, SPEED + Math.min(0, correction), SPEED - Math.max(0, correction))
        basic.pause(55)
    }
    stopWheels()
    return !stopped && hits >= 2 && !atBorder()
}

function moveRack(angle: number) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S4, angle)
    basic.pause(550)
}

function moveElbow(reach: boolean) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S3, reach ? ELBOW_LEFT_REACH : ELBOW_LEFT_FOLDED)
    motionbit.setServoPosition(MotionBitServoChannel.S5, reach ? ELBOW_RIGHT_REACH : ELBOW_RIGHT_FOLDED)
    basic.pause(550)
}

function moveGrip(close: boolean) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S8, close ? GRIP_LEFT_CLOSED : GRIP_LEFT_OPEN)
    motionbit.setServoPosition(MotionBitServoChannel.S6, close ? GRIP_RIGHT_CLOSED : GRIP_RIGHT_OPEN)
    basic.pause(550)
}

function runRoute(): boolean {
    if (atBorder()) return false
    if (!sensorReady()) {
        basic.showString("I2C")
        return false
    }
    moveRack(RACK_UP)
    moveElbow(false)
    moveGrip(false)
    let outbound = input.compassHeading()
    if (outbound < 0 || outbound >= 360 || !driveTo(1, outbound)) return false
    moveElbow(true)
    moveRack(RACK_DOWN)
    moveGrip(true)
    moveRack(RACK_UP)
    moveElbow(false)
    let dropHeading = (outbound + TURN_AFTER_PICKUP_DEG + 360) % 360
    if (TURN_AFTER_PICKUP_DEG != 0 && !pivotTo(dropHeading)) return false
    if (!driveTo(2, dropHeading)) return false
    moveElbow(true)
    moveRack(RACK_DOWN)
    moveGrip(false)
    moveRack(RACK_UP)
    moveElbow(false)
    return !stopped
}

input.onButtonPressed(Button.A, function () {
    if (busy) return
    busy = true
    stopped = false
    basic.clearScreen()
    let done = runRoute()
    stopWheels()
    if (done) basic.showIcon(IconNames.Yes)
    else basic.showIcon(IconNames.No)
    busy = false
})

stopWheels()
// ให้ micro:bit ขอปรับเทียบครั้งแรกตอนล้อยังหยุด ก่อนผู้ใช้จัดรถเข้าจุดเริ่ม
input.compassHeading()
busy = false
basic.showString("A")
