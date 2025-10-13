#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Control Device Driver
#
# Zynthian Control Device Driver for "Novation Launchkey Mini MK4 37"
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#                         Jorge Razon <jrazon@gmail.com>
#
#
#******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#******************************************************************************
# This driver implements support for the Novation Launchkey Mini MK4 37-key
# controller in DAW mode, with support for:
# - Keyboard input (all notes pass through to synths)
# - Pad buttons (top row for solo, bottom row for mute)
# - Mixer control (knobs 1-6 for levels, with soft takeover) in bank 0
# - ZynPot control (knobs 1-4 in bank 1)
#******************************************************************************
from time import sleep, time
from threading import Timer

# Zynthian specific modules
from zyngine.ctrldev.zynthian_ctrldev_base import zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

# ------------------------------------------------------------------------------------------------------------------
# Novation Launchkey Mini MK4 37
# ------------------------------------------------------------------------------------------------------------------

class zynthian_ctrldev_launchkey_mk4_37(zynthian_ctrldev_zynpad, zynthian_ctrldev_zynmixer):

    dev_ids = ["Launchkey Mini MK4 37 IN 2"]  # In DAW mode, everything comes through IN 2 (like MK3)
    driver_name = "Launchkey MiniMK4 37"
    driver_description = "Interface Novation Launchkey Mini Mk4 with zynpad"
    unroute_from_chains = True  # Prevent automatic routing, we'll handle keyboard notes explicitly

    PAD_COLOURS = [71, 104, 76, 51, 104, 41, 64, 12, 11, 71, 4, 67, 42, 9, 105, 15]
    STARTING_COLOUR = 123
    STOPPING_COLOUR = 120
    
    # Function to initialise class
    def __init__(self, state_manager, idev_in, idev_out=None):
        self.shift = False
        self.press_times = {}
        self.knob_bank = 0  # Track current knob bank (0 = mixer, 1 = zynpot+CC, 2 = CC)
        self.mixer_synced = {}  # Track which mixer knobs have synced with current mixer levels
        self.last_zynpot_values = {}  # Track last values for ZYNPOT delta calculation
        super().__init__(state_manager, idev_in, idev_out)
        self.sys_ex_header = (0xF0, 0x00, 0x20, 0x29, 0x02, 0x14)

    def send_sysex(self, data):
        if self.idev_out is not None:
            msg = self.sys_ex_header + bytes.fromhex(data) + (0xF7,)
            lib_zyncore.dev_send_midi_event(self.idev_out, msg, len(msg))
            sleep(0.05)

    def init(self):
        # Enable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 127)
        self.cols = 8
        self.rows = 2
        super().init()
        # Light up navigation buttons
        self.update_button_leds()
        # Schedule pad LED update after 10 seconds to ensure chains are loaded
        Timer(10.0, self.update_pad_leds).start()
        
        # Register callbacks for real-time updates
        try:
            # Update pad LEDs when chains change
            self.state_manager.chain_manager_changed_signal.connect(self.update_pad_leds)
            # Update when mixer state changes
            if hasattr(self.state_manager, 'zynmixer'):
                self.state_manager.zynmixer.level_changed_signal.connect(self.update_pad_leds)
        except:
            pass  # Signals may not be available

    def refresh(self):
        """Called when screen changes - reset knob tracking for pickup mode"""
        # Clear mixer sync so knobs re-sync with new values
        self.mixer_synced.clear()
        # Update pad LEDs
        self.update_pad_leds()

    def update_button_leds(self):
        """Light up the navigation buttons and show bank state"""
        if self.idev_out is None:
            return
        # Light up navigation buttons (not 51/52, those show bank state)
        cc_buttons = [104, 105, 0x66, 0x67, 106, 107]
        for cc in cc_buttons:
            lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, cc, 127)
        
        # Update bank indicator LEDs
        # Button 51 lights for bank 0, button 52 for bank 1, both off for bank 2
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 51, 127 if self.knob_bank == 0 else 0)
        lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, 52, 127 if self.knob_bank == 1 else 0)

    def end(self):
        # Disconnect signals
        try:
            self.state_manager.chain_manager_changed_signal.disconnect(self.update_pad_leds)
            if hasattr(self.state_manager, 'zynmixer'):
                self.state_manager.zynmixer.level_changed_signal.disconnect(self.update_pad_leds)
        except:
            pass
        super().end()
        # Disable DAW mode on launchkey
        lib_zyncore.dev_send_note_on(self.idev_out, 15, 12, 0)
    
    def update_pad_leds(self):
        """Update pad LEDs based on mixer mute/solo state"""
        if self.idev_out is None:
            return
        
        try:
            # Verify chain_manager and zynmixer are available
            if not hasattr(self, 'chain_manager') or not hasattr(self, 'zynmixer'):
                return
            
            # Update solo pads (top row: 96-103 for tracks 0-7)
            for i in range(8):
                note = 96 + i
                try:
                    chain = self.chain_manager.get_chain_by_position(i, midi=False)
                    
                    if chain and hasattr(chain, 'mixer_chan') and chain.mixer_chan is not None and chain.mixer_chan < 17:
                        mixer_chan = chain.mixer_chan
                        is_soloed = self.zynmixer.get_solo(mixer_chan)
                        
                        if is_soloed:
                            # Soloed - solid yellow/orange (channel 0, high velocity)
                            chan = 0
                            vel = 5
                        else:
                            # Not soloed - solid dim (channel 0, low velocity)
                            chan = 0
                            vel = 10
                    else:
                        # No chain - off
                        chan = 0
                        vel = 0
                except:
                    # Error getting chain - turn off LED
                    chan = 0
                    vel = 0
                
                lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)
            
            # Update mute pads (bottom row: 112-119 for tracks 0-7)
            for i in range(8):
                note = 112 + i
                
                try:
                    chain = self.chain_manager.get_chain_by_position(i, midi=False)
                    if chain and hasattr(chain, 'mixer_chan') and chain.mixer_chan is not None and chain.mixer_chan < 17:
                        mixer_chan = chain.mixer_chan
                    else:
                        mixer_chan = None
                    
                    if mixer_chan is not None:
                        is_muted = self.zynmixer.get_mute(mixer_chan)
                        
                        if is_muted:
                            # Muted - solid red (channel 0, very low velocity)
                            chan = 0
                            vel = 5
                        else:
                            # Unmuted - solid green (channel 0, high velocity)
                            chan = 0
                            vel = 64
                    else:
                        # No chain - off
                        chan = 0
                        vel = 0
                except:
                    # Error getting chain - turn off LED
                    chan = 0
                    vel = 0
                
                lib_zyncore.dev_send_note_on(self.idev_out, chan, note, vel)
        except Exception:
            # Silently fail if something goes wrong
            pass

    def midi_event(self, ev):
        evtype = (ev[0] >> 4) & 0x0F
        ev_chan = ev[0] & 0x0F
        
        # Handle note events (note-on and note-off)
        # Only process pad notes (96-119), let regular keyboard notes pass through
        if evtype == 0x9 or evtype == 0x8:
            note = ev[1] & 0x7F
            vel = ev[2] & 0x7F
            
            # Block ALL pad notes (96-119) from reaching synths by consuming the event
            if 96 <= note <= 119:
                # Process solo pads (96-103)
                if 96 <= note <= 103 and evtype == 0x9 and vel > 0:
                    # Top row (96-103): Solo control for tracks 0-7
                    track = note - 96
                    chain = self.chain_manager.get_chain_by_position(track, midi=False)
                    
                    if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                        mixer_chan = chain.mixer_chan
                        current_solo = self.zynmixer.get_solo(mixer_chan)
                        self.zynmixer.set_solo(mixer_chan, 0 if current_solo else 1)
                        self.update_pad_leds()
                
                # Process mute pads (112-119)
                elif 112 <= note <= 119 and evtype == 0x9 and vel > 0:
                    # Bottom row (112-119): Mute control for tracks 0-7
                    track = note - 112
                    chain = self.chain_manager.get_chain_by_position(track, midi=False)
                    
                    if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                        mixer_chan = chain.mixer_chan
                    else:
                        mixer_chan = None
                    
                    if mixer_chan is not None:
                        current_mute = self.zynmixer.get_mute(mixer_chan)
                        self.zynmixer.set_mute(mixer_chan, 0 if current_mute else 1)
                        self.update_pad_leds()
                
                # Block ALL pad notes (96-119, both on and off) from reaching synths
                return True
            
            # All other notes (keyboard) - explicitly route to chains
            else:
                # Keyboard notes: send them through to the MIDI routing system
                lib_zyncore.write_zynmidi(ev)
                return True
        elif evtype == 0xB:
            ccnum = ev[1] & 0x7F
            ccval = ev[2] & 0x7F
            
            # Button mappings for CC-based buttons
            button_commands = {
                106: "PRESET",
                107: "MENU",
                0x66: "ARROW_RIGHT",
                0x67: "ARROW_LEFT",
                104: "BACK"
            }
            
            # Handle buttons 51 and 52 - bank switching normally, up/down with shift
            if ccnum == 51 and ccval > 0:
                if self.shift:
                    # Shift + Button 51: Arrow Up
                    self.state_manager.send_cuia("ARROW_UP")
                else:
                    # Button 51: Previous bank
                    self.knob_bank = (self.knob_bank - 1) % 3  # Cycle through 3 banks
                    self.mixer_synced.clear()  # Reset mixer sync
                    # Update bank indicator LEDs
                    self.update_button_leds()
                return True
            elif ccnum == 52 and ccval > 0:
                if self.shift:
                    # Shift + Button 52: Arrow Down
                    self.state_manager.send_cuia("ARROW_DOWN")
                else:
                    # Button 52: Next bank
                    self.knob_bank = (self.knob_bank + 1) % 3  # Cycle through 3 banks
                    self.mixer_synced.clear()  # Reset mixer sync
                    # Update bank indicator LEDs
                    self.update_button_leds()
                return True
            
            # The Launchkey's physical shift button uses CC 0x3F.
            elif ccnum == 0x3F:
                self.shift = ccval != 0
                return True

            # Handle button 105 as ZYNSWITCH 3 with press/release detection
            elif ccnum == 105:
                if ccval > 0:
                    # Button press: Record the current time
                    self.press_times[ccnum] = time()
                    # Send LED feedback
                    lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, 127)
                else:
                    # Button release: Calculate the duration and send the command
                    if ccnum in self.press_times:
                        duration = time() - self.press_times[ccnum]
                        if duration < 0.5:
                            # Short press
                            self.state_manager.send_cuia("ZYNSWITCH", [3, 'S'])
                        elif duration < 1.5:
                            # Bold press
                            self.state_manager.send_cuia("ZYNSWITCH", [3, 'B'])
                        else:
                            # Long press
                            self.state_manager.send_cuia("ZYNSWITCH", [3, 'L'])
                        del self.press_times[ccnum]
                return True

                
            # Knobs 1-8 - behavior depends on current bank
            elif 20 < ccnum < 29:
                if self.knob_bank == 0:
                    # Bank 0: Knobs 1-6 for mixer, knobs 7-8 unused
                    if 20 < ccnum < 27:
                        # Knobs 1-6 for mixer channels 1-6
                        # Implement soft takeover - only change value once knob crosses current level
                        mixer_channel = ccnum - 20
                        chain = self.chain_manager.get_chain_by_position(mixer_channel - 1, midi=False)
                        if chain and chain.mixer_chan is not None and chain.mixer_chan < 17:
                            mixer_chan = chain.mixer_chan
                            current_level = self.zynmixer.get_level(mixer_chan)
                            new_level = ccval / 127.0
                            
                            # Check if this knob has synced yet
                            if ccnum not in self.mixer_synced:
                                # Not synced - check if knob position is close enough to current level
                                if abs(new_level - current_level) < 0.02:  # Within 2% (about 2-3 CC values)
                                    self.mixer_synced[ccnum] = True
                                    self.zynmixer.set_level(mixer_chan, new_level)
                            else:
                                # Already synced - always update
                                self.zynmixer.set_level(mixer_chan, new_level)
                    # Knobs 7-8 (CC 27-28) do nothing in bank 0
                    return True
                elif self.knob_bank == 1:
                    # Bank 1: Knobs 1-4 for ZYNPOT, 5-8 send CC 20-23
                    if 20 < ccnum < 25:
                        # Knobs 1-4 for ZYNPOT (CC 21-24)
                        # Maps to ZYNPOT 0-3 (the 4 main rotary encoders on Zynthian)
                        # ZYNPOT expects relative delta values, so calculate change from last value
                        zynpot_index = ccnum - 21
                        
                        # Initialize tracking if first time
                        if ccnum not in self.last_zynpot_values:
                            self.last_zynpot_values[ccnum] = ccval
                            return True
                        
                        # Calculate delta
                        last_val = self.last_zynpot_values[ccnum]
                        delta = ccval - last_val
                        
                        # Handle wrap-around (127->0 or 0->127)
                        if delta > 64:
                            delta -= 128
                        elif delta < -64:
                            delta += 128
                        
                        # Send delta if there's movement
                        if delta != 0:
                            self.state_manager.send_cuia("ZYNPOT", [zynpot_index, delta])
                            self.last_zynpot_values[ccnum] = ccval
                        
                        return True
                    else:
                        # Knobs 5-8: Send CC 20-23 (standard MIDI CC)
                        new_ccnum = ccnum - 25 + 20  # Map 25-28 to 20-23
                        lib_zyncore.write_zynmidi([0xB0 | ev_chan, new_ccnum, ccval])
                        return True
            
            # Combined ZynSwitch and Metronome logic
            elif ccnum in [74, 75, 76, 77]:
                # If SHIFT is held and it's the Metronome button (CC 76)
                if self.shift and ccnum == 76:
                    if ccval > 0:
                        self.state_manager.send_cuia("TEMPO")
                    return True
                
                # ZynSwitch logic for button presses and releases
                zynswitch_index = {74: 0, 75: 1, 76: 3, 77: 2}.get(ccnum)
                if ccval > 0:
                    # Button press: Record the current time
                    self.press_times[ccnum] = time()
                else:
                    # Button release: Calculate the duration and send the command
                    if ccnum in self.press_times:
                        duration = time() - self.press_times[ccnum]
                        if duration < 0.5:
                            # Short press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'S'])
                        elif duration < 1.5:
                            # Bold press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'B'])
                        else:
                            # Long press
                            self.state_manager.send_cuia("ZYNSWITCH", [zynswitch_index, 'L'])
                        del self.press_times[ccnum]
                return True

            # Handle the PLAY and RECORD buttons
            elif ccnum == 0x73 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_PLAY")
                else:
                    self.state_manager.send_cuia("TOGGLE_PLAY")
                return True
            elif ccnum == 0x75 and ccval > 0:
                if self.shift:
                    self.state_manager.send_cuia("TOGGLE_MIDI_RECORD")
                else:
                    self.state_manager.send_cuia("TOGGLE_RECORD")
                return True
            
            # Use the dictionary for the remaining buttons and check for press
            elif ccnum in button_commands and ccval > 0:
                # Send LED feedback
                lib_zyncore.dev_send_ccontrol_change(self.idev_out, 0, ccnum, 127)
                self.state_manager.send_cuia(button_commands[ccnum])
                return True
            elif ccnum == 0 or ccval == 0:
                return True

        elif evtype == 0xC:
            val1 = ev[1] & 0x7F
            self.zynseq.select_bank(val1 + 1)
            return True

        # Let unhandled MIDI events pass through
        return False
# ------------------------------------------------------------------------------------------------------------------
