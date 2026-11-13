// Run with Node 24: node tests/search.cjs
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { stripTypeScriptTypes } = require('node:module')
const source = stripTypeScriptTypes(fs.readFileSync(path.join(__dirname, '../main.ts'), 'utf8'))

function simulate(cancelWhileReversing, driftDegrees = 15, turnStep = 15) {
    let ms = 0, heading = 350, detected = true, straightTime = 0, nearReadings = 0
    const reversals = [], turnHeadings = [], servos = [], buttons = {}, wheels = {}
    let icon, corrected = false, drifted = false, lastTrim = 0
    const power = {}
    let pivotDegrees = 0, pivotStarts = 0
    let launchReadings = 0
    const context = {
        DigitalPin: {P0:0, P1:1, P12:12, P13:13, P14:14, P15:15, P16:16},
        MotionBitMotorDirection: {Forward:1, Backward:-1},
        MotionBitMotorChannel: {M1:1, M2:2, M3:3, M4:4, All:0},
        MotionBitServoChannel: {S1:1, S2:2, S3:3, S4:4, S5:5},
        Button: {A:'A', B:'B'}, IconNames: {Yes:1, No:0}, PulseValue: {High:1},
        NumberFormat: {UInt8LE:0},
        input: {runningTime:()=>ms, compassHeading() {
                if(ms>0 && !drifted && ++launchReadings===2) return (heading+10)%360
                return heading
            },
            onButtonPressed:(b,fn)=>{buttons[b]=fn}},
        control: {waitMicros(){}},
        pins: {
            digitalReadPin:()=>Number(detected),
            digitalWritePin(p){assert.equal(p,0)},
            i2cWriteNumber(){}, i2cReadNumber:()=>0,
            pulseIn(p) {
                assert.equal(p,1)
                if (reversals.length < 2 || straightTime < 325) return ms%2 ? 0 : 5800
                if (nearReadings++) assert.equal(wheels[1],0)
                return 580
            }
        },
        motionbit: {
            runMotor(m,d,s) {
                if(m===3 && d===-1 && wheels[1]===1) pivotStarts++
                assert(s >= 175 && s <= 255)
                if(m===0) {
                    assert.equal(s,255)
                    for(let motor=1;motor<=4;motor++) {
                        wheels[motor]=d
                        power[motor]=s
                    }
                } else {
                    wheels[m]=d
                    power[m]=s
                }
            },
            brakeMotor(){
                if(wheels[1]===1 && wheels[3]===-1) {
                    assert(pivotDegrees>=86, 'braked partway through the right pivot')
                    turnHeadings.push(heading)
                }
                assert(!(drifted && detected && reversals.length===0), 'braked while correcting straight travel')
                for(let m=1;m<=4;m++) wheels[m]=0
            },
            setServoPosition(p,a) {assert.equal(wheels[1],0);servos.push([p,a])}
        },
        basic: {
            showString(){}, clearScreen(){}, showIcon:i=>{icon=i},
            pause(n) {
                ms+=n
                assert(ms < 30000, 'route failed to finish')
                assert.equal(wheels[1],wheels[2])
                assert.equal(wheels[3],wheels[4])
                assert.equal(power[1],power[2])
                assert.equal(power[3],power[4])
                if(wheels[1]===1 && wheels[3]===1) {
                    straightTime+=n
                    const trim=power[1]-power[3]
                    assert.equal(Math.max(power[1],power[3]),255)
                    assert(Math.abs(trim-lastTrim)<=16)
                    lastTrim=trim
                    if(!drifted) {
                        assert.equal(trim,0,'all four motors must launch at 255')
                        heading=(heading+driftDegrees+360)%360
                        drifted=true
                    } else if(!corrected && trim!==0) {
                        assert.equal(Math.sign(trim),-Math.sign(driftDegrees))
                        heading=350
                        corrected=true
                    }
                    if(reversals.length<2 && straightTime >= (reversals.length ? 325 : 9000)) detected=false
                } else if(wheels[1]===-1 && wheels[3]===-1) {
                    assert.equal(Math.min(power[1],power[3]),255)
                    assert.equal(detected,false)
                    reversals.push(n)
                    pivotDegrees=0
                    straightTime=0
                    if(cancelWhileReversing) buttons.B()
                } else if(wheels[1]===1 && wheels[3]===-1) {
                    assert(reversals.length>0,'pivoted while driving straight')
                    assert.equal(Math.min(power[1],power[3]),255)
                    heading=(heading+turnStep)%360
                    pivotDegrees+=turnStep
                    if(pivotDegrees>=86) detected=true
                }
            }
        }
    }
    vm.runInNewContext(source,context)
    buttons.A()
    assert.equal(wheels[1],0)
    assert.equal(wheels[3],0)
    assert.equal(pivotStarts, turnHeadings.length)
    return {reversals,turnHeadings,servos,icon,corrected}
}

const run=simulate(false)
assert.deepEqual(run.reversals,[50,50])
assert(run.corrected)
assert(simulate(false,-15).corrected)
assert.deepEqual(run.turnHeadings,[80,170])
assert.deepEqual(simulate(false,15,16).turnHeadings,[86,182])
assert.deepEqual(run.servos.map(([pin])=>pin),[1,4,5,2,3,1,2,3,4,5])
assert.deepEqual(run.servos.slice(5,8),[[1,55],[2,95],[3,85]])
assert.equal(run.icon,1)
const cancelled=simulate(true)
assert.deepEqual(cancelled.reversals,[50])
assert.equal(cancelled.servos.length,5)
assert.equal(cancelled.icon,0)
console.log('Continuous search, two boundary turns, sonar pickup and B stop passed.')

// Drive the actual button handler through a partial mask; no forward command is
// allowed until all five inputs recover. Also exercise interruption of a 90° turn.
function simulateAlignment(initialMask, expectedDirection, duringTurn = false, action = 'recover') {
    let mask = duringTurn ? 0 : initialMask
    let ms = 0, aligned = false, finished = false, icon
    const buttons = {}, wheels = [0, 0, 0, 0, 0]
    const ctx = {
        DigitalPin:{P0:0,P1:1,P12:12,P13:13,P14:14,P15:15,P16:16},
        MotionBitMotorDirection:{Forward:1,Backward:-1},
        MotionBitMotorChannel:{M1:1,M2:2,M3:3,M4:4,All:0},
        MotionBitServoChannel:{S1:1,S2:2,S3:3,S4:4,S5:5},
        Button:{A:'A',B:'B'}, IconNames:{Yes:1,No:0}, PulseValue:{High:1},
        NumberFormat:{UInt8LE:0},
        input:{onButtonPressed:(b,f)=>buttons[b]=f, runningTime:()=>ms, compassHeading:()=>350},
        pins:{digitalReadPin:p=>(mask >> (p-12)) & 1, digitalWritePin(){},
            i2cWriteNumber(){}, i2cReadNumber:()=>0, pulseIn:()=>finished ? 580 : 5800},
        control:{waitMicros(){}},
        motionbit:{
            brakeMotor:()=>wheels.fill(0),
            runMotor(m,d){if(m===0) wheels.fill(d); else wheels[m]=d},
            setServoPosition(){assert.equal(wheels[1],0)}
        },
        basic:{showString(){},clearScreen(){},showIcon:i=>icon=i,
            pause(n){
                ms+=n
                assert(ms<9000)
                if(wheels[1]===0) return
                if(mask===0) {
                    if(wheels[1]===1 && wheels[3]===-1) mask=initialMask
                } else if(mask!==31) {
                    assert.equal(wheels[1],expectedDirection)
                    assert.equal(wheels[3],-expectedDirection)
                    aligned=true
                    if(action==='recover') mask=31
                    if(action==='cancel') buttons.B()
                } else {
                    assert.equal(wheels[1],1)
                    assert.equal(wheels[3],1)
                    finished=true
                }
            }}
    }
    vm.runInNewContext(source,ctx)
    buttons.A()
    assert(aligned)
    assert.equal(finished,action==='recover')
    assert.equal(icon,action==='recover' ? 1 : 0)
    assert.equal(wheels[1],0)
    assert.equal(wheels[3],0)
}
for(let i=0;i<5;i++) simulateAlignment(31 ^ (1<<i),i<=2 ? 1 : -1)
simulateAlignment(7,-1,true)
simulateAlignment(28,1,false,'timeout')
simulateAlignment(28,1,false,'cancel')
console.log('Each missing channel, interrupted turn, alignment timeout and B stop passed.')
