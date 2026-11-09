// MOTION:BIT Pro | ปรับมุมให้ตรงกับแขนจริงก่อนติดกระป๋อง
const ARM_UP = 85
const ARM_DOWN = 55
const GRIP_OPEN = 65
const GRIP_CLOSED = 95
const BASE_FRONT = 90
const BASE_DROP = 110
const SPEED = 65 // 0–255
const LEFT = MotionBitMotorDirection.Forward
const RIGHT = MotionBitMotorDirection.Forward
const SEARCH_MS = 8000
// หลังยกกระป๋อง: 0 = ตรง, ค่าบวก = หมุนขวา, ค่าลบ = หมุนซ้าย (มิลลิวินาที)
const TURN_AFTER_PICKUP_MS = 0
let address = 0x29
let busy = false
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

function driveSides(left: MotionBitMotorDirection, right: MotionBitMotorDirection) {
    motionbit.runMotor(MotionBitMotorChannel.M1, left, SPEED)
    motionbit.runMotor(MotionBitMotorChannel.M2, left, SPEED)
    motionbit.runMotor(MotionBitMotorChannel.M3, right, SPEED)
    motionbit.runMotor(MotionBitMotorChannel.M4, right, SPEED)
}

function opposite(dir: MotionBitMotorDirection): MotionBitMotorDirection {
    if (dir == MotionBitMotorDirection.Forward) return MotionBitMotorDirection.Backward
    return MotionBitMotorDirection.Forward
}

function pivot(ms: number) {
    if (stopped || ms == 0) return
    if (ms > 0) driveSides(LEFT, opposite(RIGHT))
    else driveSides(opposite(LEFT), RIGHT)
    let end = input.runningTime() + Math.abs(ms)
    while (!stopped && input.runningTime() < end) basic.pause(10)
    stopWheels()
}

function driveTo(color: number): boolean {
    if (stopped) return false
    driveSides(LEFT, RIGHT)
    let start = input.runningTime()
    let hits = 0
    while (!stopped && input.runningTime() - start < SEARCH_MS) {
        if (floorColor() == color) hits++
        else hits = 0
        if (hits >= 2) break
        basic.pause(55)
    }
    stopWheels()
    return !stopped && hits >= 2
}

function moveServo(channel: MotionBitServoChannel, angle: number) {
    if (stopped) return
    motionbit.setServoPosition(channel, angle)
    basic.pause(550)
}

function runRoute(): boolean {
    if (!sensorReady()) {
        basic.showString("I2C")
        return false
    }
    moveServo(MotionBitServoChannel.S4, ARM_UP)
    moveServo(MotionBitServoChannel.S3, BASE_FRONT)
    moveServo(MotionBitServoChannel.S8, GRIP_OPEN)
    if (!driveTo(1)) return false
    moveServo(MotionBitServoChannel.S4, ARM_DOWN)
    moveServo(MotionBitServoChannel.S8, GRIP_CLOSED)
    moveServo(MotionBitServoChannel.S4, ARM_UP)
    pivot(TURN_AFTER_PICKUP_MS)
    if (!driveTo(2)) return false
    moveServo(MotionBitServoChannel.S3, BASE_DROP)
    moveServo(MotionBitServoChannel.S4, ARM_DOWN)
    moveServo(MotionBitServoChannel.S8, GRIP_OPEN)
    moveServo(MotionBitServoChannel.S4, ARM_UP)
    moveServo(MotionBitServoChannel.S3, BASE_FRONT)
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
basic.showString("A")
