// MOTION:BIT Pro | ปรับมุมให้ตรงกับแขนจริงก่อนติดกระป๋อง
const RACK_UP = 85
const RACK_DOWN = 55
// ค่าตั้งต้นสำหรับสองฝั่งที่ติดตั้งหันเข้าหากัน ปรับแต่ละฝั่งตามกลไกจริง
const ROTATE_LEFT_READY = 90
const ROTATE_RIGHT_READY = 90
const ROTATE_LEFT_AFTER_GRIP = 90
const ROTATE_RIGHT_AFTER_GRIP = 90
const GRIP_LEFT_OPEN = 65
const GRIP_RIGHT_OPEN = 115
const GRIP_LEFT_CLOSED = 95
const GRIP_RIGHT_CLOSED = 85
const SPEED = 65 // 0–255
const LEFT = MotionBitMotorDirection.Forward  // เดินหน้าฝั่งซ้าย: M1A และ M2A
const RIGHT = MotionBitMotorDirection.Forward // เดินหน้าฝั่งขวา: M3A และ M4A
const PICKUP_DISTANCE_CM = 10 // ค่า X ชั่วคราว วัดจากหน้าหัวอัลตราโซนิก
const REVERSE_3CM_MS = 180 // เวลาทดลองสำหรับถอย 3 ซม. ที่ SPEED บนพื้นจริง
const NB142_DETECTED_LEVEL = 1
// หัวอ่าน NB142 เรียงจากซ้ายไปขวาตามทิศเดินหน้าของรถ
const NB142_PINS = [
    DigitalPin.P12, // ซ้ายสุด
    DigitalPin.P13, // ซ้ายกลาง
    DigitalPin.P14, // กลาง
    DigitalPin.P15, // ขวากลาง
    DigitalPin.P16  // ขวาสุด
]
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

function nb142Detected(): boolean {
    for (let i = 0; i < NB142_PINS.length; i++) {
        if (pins.digitalReadPin(NB142_PINS[i]) == NB142_DETECTED_LEVEL) return true
    }
    return false
}

function headingError(target: number, heading: number): number {
    return (target - heading + 540) % 360 - 180
}

function objectInReach(): boolean {
    pins.digitalWritePin(DigitalPin.P1, 0)
    control.waitMicros(2)
    pins.digitalWritePin(DigitalPin.P1, 1)
    control.waitMicros(10)
    pins.digitalWritePin(DigitalPin.P1, 0)
    let echoUs = pins.pulseIn(DigitalPin.P2, PulseValue.High, 25000)
    return echoUs > 0 && echoUs <= PICKUP_DISTANCE_CM * 58
}

function searchForCan(readColors: boolean): boolean {
    let target = input.compassHeading()
    if (target < 0 || target >= 360) return false
    let turning = false
    let turnStarted = 0
    let settled = 0
    let previousColor = 0
    let nearLastSample = false
    while (!stopped) {
        let detected = nb142Detected()
        let near = false
        if (detected) {
            near = objectInReach()
            detected = nb142Detected()
        }
        if (stopped) return false
        if (!detected && !turning) {
            stopWheels()
            let entry = input.compassHeading()
            if (entry < 0 || entry >= 360 || stopped) return false
            driveSides(opposite(LEFT), opposite(RIGHT), SPEED, SPEED)
            basic.pause(REVERSE_3CM_MS)
            stopWheels()
            if (stopped) return false
            target = (entry + 90) % 360
            turning = true
            turnStarted = input.runningTime()
            settled = 0
            nearLastSample = false
            continue
        }
        if (detected && near) {
            stopWheels()
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
        let error = headingError(target, heading)
        if (turning) {
            if (input.runningTime() - turnStarted >= 5000) return false
            if (Math.abs(error) <= TURN_TOLERANCE_DEG) {
                stopWheels()
                settled++
                turning = settled < 3
            } else {
                settled = 0
                let speed = Math.min(SPEED, 40 + Math.abs(error))
                if (error > 0) driveSides(LEFT, opposite(RIGHT), speed, speed)
                else driveSides(opposite(LEFT), RIGHT, speed, speed)
            }
        } else {
            let correction = Math.max(-SPEED, Math.min(SPEED, 2 * error))
            driveSides(LEFT, RIGHT, SPEED + Math.min(0, correction), SPEED - Math.max(0, correction))
        }
        basic.pause(65)
    }
    return false
}

function moveRack(angle: number) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S1, angle)
    basic.pause(550)
}

function rotateGrip(afterGrip: boolean) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S4, afterGrip ? ROTATE_LEFT_AFTER_GRIP : ROTATE_LEFT_READY)
    motionbit.setServoPosition(MotionBitServoChannel.S5, afterGrip ? ROTATE_RIGHT_AFTER_GRIP : ROTATE_RIGHT_READY)
    basic.pause(550)
}

function moveGrip(close: boolean) {
    if (stopped) return
    motionbit.setServoPosition(MotionBitServoChannel.S2, close ? GRIP_LEFT_CLOSED : GRIP_LEFT_OPEN)
    motionbit.setServoPosition(MotionBitServoChannel.S3, close ? GRIP_RIGHT_CLOSED : GRIP_RIGHT_OPEN)
    basic.pause(550)
}

function runRoute(): boolean {
    let readColors = sensorReady()
    moveRack(RACK_UP)
    rotateGrip(false)
    moveGrip(false)
    let found = searchForCan(readColors)
    stopWheels()
    if (!found || stopped) return false
    moveRack(RACK_DOWN)
    moveGrip(true)
    rotateGrip(true)
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
