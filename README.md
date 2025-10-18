### Knobs (8 Rotary Encoders - CC 85-92 in Transport Mode)

**Up and Down buttons cycle through 3 banks:**

#### Bank 0(Up arrow) - MIXER MODE
- **Knob 1** (CC 85): Chain 0 Level
- **Knob 2** (CC 86): Chain 1 Level  
- **Knob 3** (CC 87): Chain 2 Level
- **Knob 4** (CC 88): Chain 3 Level
- **Knob 5** (CC 89): Chain 4 Level
- **Knob 6** (CC 90): Chain 5 Level
- **Knob 7** (CC 91): Chain 6 Level
- **Knob 8** (CC 92): **MASTER Level** (always mixer channel 16)

#### Bank 1(Down arrow) - CONTROL MODE (Default on startup)
- **Knob 1** (CC 85): ZYNPOT 0 (Main Rotary 1)
- **Knob 2** (CC 86): ZYNPOT 1 (Main Rotary 2)
- **Knob 3** (CC 87): ZYNPOT 2 (Main Rotary 3)
- **Knob 4** (CC 88): ZYNPOT 3 (Main Rotary 4)
- **Knob 5** (CC 89): Arrow LEFT/RIGHT
- **Knob 6** (CC 90): Arrow UP/DOWN
- **Knob 7** (CC 91): Preset Browse (Previous/Next)
- **Knob 8** (CC 92): SELECT (CW) / BACK (CCW)

#### Bank 2 - CC PASSTHROUGH MODE
- **Knob 1-8** (CC 85-92): Send CC 24-31 to synths

### Pads (16 Velocity-Sensitive Pads)

**Top Row (Notes 96-103):**
- Pads 0-6: **SOLO** for Chains 0-6 (skips master if in chain list)
- Pad 7: **OFF** (no solo for master)

**Bottom Row (Notes 112-119):**
- Pads 0-6: **MUTE** for Chains 0-6 (skips master if in chain list)
- Pad 7: **MUTE** for Master Channel (mixer channel 16)

### Buttons

**Navigation:**
- **>** (CC 104): Select
- **Func** (CC 105): MENU
- **Pad Up** (CC 106): BACK
- **Pad Down** (CC 107): PRESET

**Additional Transport:**
- **Play Button** (CC 0x73): TOGGLE_PLAY (normal) / TOGGLE_MIDI_PLAY (with Shift)
- **Record Button** (CC 0x75): TOGGLE_RECORD (normal) / TOGGLE_MIDI_RECORD (with Shift)

### Press Durations
- **Short**: < 0.5 seconds
- **Bold**: 0.5 - 1.5 seconds  
- **Long**: > 1.5 seconds

### LED Feedback

**Pads:**
- Solo Active: Yellow/Orange (vel 14)
- Solo Inactive: Dim White (vel 118)
- Muted: Red (vel 5)
- Unmuted: Green (vel 64)
- No Chain/Master Solo: OFF (vel 0)

## Notes

- Master channel is **always** on the far right
- Default startup bank for knobs is Bank 1 (Control Mode)
