"""
===============================================================================
FROGGY DEMO - 16-BIT MIDI MUSIC COMPOSER & FILE GENERATOR
===============================================================================
This module is a pure-Python Standard MIDI File (SMF Format 1) generator.
It creates high quality 16-bit retro soundtrack files (.mid) that can be:
  1. Played natively in the game via Pygame's hardware/software MIDI synthesizer.
  2. Opened, inspected, and edited by creators (like your nephew!) in standard
     music production software (DAWs) such as:
       - MuseScore (Free notation editor)
       - FL Studio / Ableton / Reaper
       - Sekaiju (Free retro MIDI sequencer)
       - BandLab / GarageBand

HOW STANDARD MIDI FILES WORK:
- A MIDI file does not store audio waves; it stores MUSICAL INSTRUCTIONS:
  "At tick 480, play Middle C (note 60) on Channel 0 at volume 100 with Piano."
- Channel 10 (0-indexed channel 9) is dedicated to the General MIDI Drum Kit!
  Kick = 35/36, Rimshot = 37, Snare = 38/40, Closed Hat = 42, Open Hat = 46.
- Tempo is defined in microseconds per quarter note (e.g. 500,000 us = 120 BPM).
===============================================================================
"""

import os
import struct
import math

TICKS_PER_BEAT = 480  # Standard MIDI PPQN (Pulses Per Quarter Note)


def var_len(val: int) -> bytes:
    """Encodes an integer into a MIDI variable-length quantity byte sequence."""
    val = max(0, int(val))
    bytes_arr = bytearray()
    bytes_arr.append(val & 0x7F)
    val >>= 7
    while val > 0:
        bytes_arr.insert(0, (val & 0x7F) | 0x80)
        val >>= 7
    return bytes(bytes_arr)


class MidiEvent:
    def __init__(self, tick: int, data: bytes):
        self.tick = tick
        self.data = data

    def __lt__(self, other):
        return self.tick < other.tick


class MidiTrack:
    """Represents a single independent track in a multi-track MIDI file."""
    def __init__(self, name: str = "Track"):
        self.name = name
        self.events = []

    def set_name(self, name: str):
        data = b'\xFF\x03' + var_len(len(name)) + name.encode('ascii', errors='ignore')
        self.events.append(MidiEvent(0, data))

    def set_instrument(self, channel: int, patch_number: int, tick: int = 0):
        """Sets the General MIDI instrument program for the given channel (0-15)."""
        data = bytes([0xC0 | (channel & 0x0F), patch_number & 0x7F])
        self.events.append(MidiEvent(tick, data))

    def set_volume(self, channel: int, volume: int = 100, tick: int = 0):
        """Sets channel master volume via Control Change 7."""
        data = bytes([0xB0 | (channel & 0x0F), 0x07, volume & 0x7F])
        self.events.append(MidiEvent(tick, data))

    def set_pan(self, channel: int, pan: int = 64, tick: int = 0):
        """Sets stereo pan (0 = hard left, 64 = center, 127 = hard right)."""
        data = bytes([0xB0 | (channel & 0x0F), 0x0A, pan & 0x7F])
        self.events.append(MidiEvent(tick, data))

    def add_note(self, channel: int, pitch: int, start_tick: int, duration_ticks: int, velocity: int = 90):
        """Schedules a Note-On and matching Note-Off event."""
        if pitch < 0 or pitch > 127 or duration_ticks <= 0:
            return
        ch = channel & 0x0F
        vel = max(1, min(127, int(velocity)))
        # Note On
        self.events.append(MidiEvent(start_tick, bytes([0x90 | ch, pitch & 0x7F, vel])))
        # Note Off (velocity 0)
        self.events.append(MidiEvent(start_tick + duration_ticks, bytes([0x80 | ch, pitch & 0x7F, 0])))

    def add_chord(self, channel: int, pitches, start_tick: int, duration_ticks: int, velocity: int = 85):
        """Schedules multiple notes sounding together simultaneously."""
        for p in pitches:
            self.add_note(channel, p, start_tick, duration_ticks, velocity)

    def serialize(self) -> bytes:
        """Encodes all track events into binary MTrk chunk with delta-times."""
        self.events.sort()
        track_bytes = bytearray()
        prev_tick = 0

        for ev in self.events:
            dt = ev.tick - prev_tick
            track_bytes += var_len(dt)
            track_bytes += ev.data
            prev_tick = ev.tick

        # End of Track Meta-Event (0xFF 0x2F 0x00)
        track_bytes += var_len(0) + b'\xFF\x2F\x00'

        # Prepend MTrk header + 32-bit chunk length
        return b'MTrk' + struct.pack('>I', len(track_bytes)) + track_bytes


class MidiFile:
    """Represents a standard Format 1 MIDI file containing multiple tracks."""
    def __init__(self, tempo_bpm: float = 120.0):
        self.tempo_bpm = tempo_bpm
        self.tracks = []
        self._setup_conductor_track(tempo_bpm)

    def _setup_conductor_track(self, bpm: float):
        conductor = MidiTrack("Conductor / Tempo")
        # Tempo Meta-Event: 0xFF 0x51 0x03 <3 bytes microseconds per beat>
        us_per_beat = int(round(60_000_000.0 / bpm))
        b0 = (us_per_beat >> 16) & 0xFF
        b1 = (us_per_beat >> 8) & 0xFF
        b2 = us_per_beat & 0xFF
        conductor.events.append(MidiEvent(0, bytes([0xFF, 0x51, 0x03, b0, b1, b2])))
        self.tracks.append(conductor)

    def add_track(self, name: str) -> MidiTrack:
        tr = MidiTrack(name)
        tr.set_name(name)
        self.tracks.append(tr)
        return tr

    def save(self, filepath: str):
        """Serializes and writes the MIDI file to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        # Header: Format 1, num_tracks, division
        num_tracks = len(self.tracks)
        header = b'MThd' + struct.pack('>IHHH', 6, 1, num_tracks, TICKS_PER_BEAT)
        with open(filepath, 'wb') as f:
            f.write(header)
            for tr in self.tracks:
                f.write(tr.serialize())
        print(f"[MidiComposer] Exported Standard MIDI File: {filepath}")


# =============================================================================
# MUSICAL COMPOSITION ROUTINES (16-BIT RETRO SOUNDTRACK)
# =============================================================================

def compose_jamaican_vivaldi_four_seasons(filepath: str):
    """
    Composes a 16-bit Jamaican Reggae / Dub adaptation of Antonio Vivaldi's
    'The Four Seasons' - Concerto No. 1 in E major, Op. 8, RV 269 ('Spring / Allegro').
    
    Arranged in F Major (bright, cheerful, and sunny):
      - Channel 0: Reggae Organ Skank (Offbeat syncopated bubble)
      - Channel 1: Clean Electric Guitar Skank (Chop on upbeats 2 & 4)
      - Channel 2: Heavy Electric Dub Bass (Warm, syncopated walking bass)
      - Channel 3: Caribbean Steel Drums / Lead (Plays Vivaldi's Spring melody)
      - Channel 4: Brass Section Horn Stabs (Reggae horns answering phrases)
      - Channel 9: General MIDI Drum Kit (Reggae One-Drop & Steppers groove)
    """
    bpm = 108.0  # Classic relaxed, bouncy reggae tempo
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_skank = midi.add_track("Reggae Organ & Guitar Skank")
    tr_bass = midi.add_track("Walking Dub Bass")
    tr_lead = midi.add_track("Vivaldi Spring Lead (Steel Drums / Flute)")
    tr_horns = midi.add_track("Reggae Horn Section")
    tr_drums = midi.add_track("Drums (One-Drop Reggae Kit)")

    # Set Instruments
    tr_skank.set_instrument(0, 16)   # Drawbar Organ
    tr_skank.set_instrument(1, 27)   # Clean Electric Guitar
    tr_bass.set_instrument(2, 33)    # Electric Bass (Finger)
    tr_lead.set_instrument(3, 114)   # Steel Drums (or Marimba)
    tr_horns.set_instrument(4, 61)   # Brass Section

    # Volumes and Stereo Panning
    tr_skank.set_volume(0, 92); tr_skank.set_pan(0, 42)
    tr_skank.set_volume(1, 88); tr_skank.set_pan(1, 86)
    tr_bass.set_volume(2, 108); tr_bass.set_pan(2, 64)
    tr_lead.set_volume(3, 112); tr_lead.set_pan(3, 64)
    tr_horns.set_volume(4, 94); tr_horns.set_pan(4, 76)
    tr_drums.set_volume(9, 104)

    # Chord progression in F Major:
    # Bars 1-2: F major  (F - A - C)
    # Bars 3-4: C major  (C - E - G) -> F major
    # Bars 5-6: Bb major (Bb - D - F) -> F major
    # Bars 7-8: C7 (C - E - G - Bb) -> F major
    chords_per_bar = [
        ([53, 57, 60, 65], "F"),   # Bar 0
        ([53, 57, 60, 65], "F"),   # Bar 1
        ([55, 60, 64, 67], "C"),   # Bar 2
        ([53, 57, 60, 65], "F"),   # Bar 3
        ([50, 58, 62, 65], "Bb"),  # Bar 4
        ([53, 57, 60, 65], "F"),   # Bar 5
        ([55, 58, 60, 64], "C7"),  # Bar 6
        ([53, 57, 60, 65], "F"),   # Bar 7
    ] * 2  # 16-bar complete loop!

    total_bars = len(chords_per_bar)

    # 1. Reggae Skank Rhythm (Organ & Guitar hitting on upbeats)
    for bar_idx, (chord, name) in enumerate(chords_per_bar):
        bar_start = bar_idx * bar_len
        # In reggae, the skank chops on beats 2 and 4, or offbeats "and of 1, 2, and of 3, 4"
        for beat in range(4):
            # Upbeat sixteenths
            t_on = bar_start + beat * tpq + int(tpq * 0.5)
            dur = int(tpq * 0.42)
            tr_skank.add_chord(0, chord, t_on, dur, velocity=82)
            tr_skank.add_chord(1, chord, t_on, dur, velocity=78)

    # 2. Walking Reggae Bassline (Syncopated, heavy roots on offbeats)
    for bar_idx, (chord, name) in enumerate(chords_per_bar):
        bar_start = bar_idx * bar_len
        root = chord[0] - 12  # Drop down to low octave (F1, C2, Bb1)
        fifth = root + 7
        octave = root + 12

        # Characteristic reggae bass pattern:
        # Rest on beat 1, drop on 1-and, walk on 2-and, heavy on beat 3!
        tr_bass.add_note(2, root, bar_start + int(tpq * 0.5), int(tpq * 0.45), velocity=106)
        tr_bass.add_note(2, fifth, bar_start + int(tpq * 1.5), int(tpq * 0.45), velocity=98)
        tr_bass.add_note(2, root, bar_start + int(tpq * 2.0), int(tpq * 0.85), velocity=112)
        tr_bass.add_note(2, octave, bar_start + int(tpq * 3.5), int(tpq * 0.45), velocity=100)

    # 3. Drums (Reggae One-Drop & Rolling Hi-Hat)
    # Channel 9 (GM Drums): 36 = Kick, 37 = Side Stick, 38 = Snare, 42 = Closed Hat, 46 = Open Hat
    for bar_idx in range(total_bars):
        bar_start = bar_idx * bar_len

        # Hi-hat 8th note / 16th note swing
        for step in range(8):
            t_hat = bar_start + int(step * (tpq / 2))
            is_open = (step == 3 or step == 7) and (bar_idx % 2 == 1)
            hat_pitch = 46 if is_open else 42
            tr_drums.add_note(9, hat_pitch, t_hat, int(tpq * 0.25), velocity=76 if step % 2 == 1 else 94)

        # Reggae "One Drop": Beat 3 has BOTH the Kick (36) and the Snare / Rimshot (37 / 38)!
        # Beat 1 has NO heavy kick - that is the classic reggae space!
        t_drop = bar_start + 2 * tpq
        tr_drums.add_note(9, 36, t_drop, int(tpq * 0.6), velocity=110)  # Heavy kick on beat 3
        tr_drums.add_note(9, 37, t_drop, int(tpq * 0.4), velocity=115)  # Snappy rimshot
        tr_drums.add_note(9, 38, t_drop, int(tpq * 0.4), velocity=95)   # Acoustic snare body

        # Light kick on beat 1 every other bar
        if bar_idx % 2 == 0:
            tr_drums.add_note(9, 36, bar_start, int(tpq * 0.35), velocity=75)

        # Crash cymbal on bar 1 and bar 9 turnaround
        if bar_idx in (0, 8):
            tr_drums.add_note(9, 49, bar_start, int(tpq * 1.5), velocity=105)

    # 4. Melodic Lead: Vivaldi's Spring (La Primavera) with Calypso / Reggae Swing
    # In F Major:
    # Motif A: C5 (8th) | A4 (8th) A4 A4 (G4 F4) | C5 (half)
    # Echo:    C5 (8th) | A4 (8th) A4 A4 (G4 F4) | C5 (half)
    # Motif B: C5 (8th) Bb4 (8th) A4 (8th) G4 (8th) | F4 (dotted quarter) G4 (8th) A4 (half)
    # Motif C: Bb4 A4 G4 F4 | E4 G4 C5...
    def add_vivaldi_phrase(start_bar: int):
        base = start_bar * bar_len
        # Phrase 1: The Spring Arrival Call
        # Beat 1: C5 (72)
        tr_lead.add_note(3, 72, base + 0, int(tpq * 0.45), velocity=105)
        # Beat 2: A4 (69)
        tr_lead.add_note(3, 69, base + int(tpq * 0.5), int(tpq * 0.4), velocity=100)
        # Beat 3: A4 (69), A4 (69)
        tr_lead.add_note(3, 69, base + tpq, int(tpq * 0.4), velocity=102)
        tr_lead.add_note(3, 69, base + int(tpq * 1.5), int(tpq * 0.4), velocity=102)
        # Beat 4: G4 (67) -> F4 (65)
        tr_lead.add_note(3, 67, base + tpq * 2, int(tpq * 0.45), velocity=95)
        tr_lead.add_note(3, 65, base + int(tpq * 2.5), int(tpq * 0.45), velocity=95)
        # Resolve to high C5
        tr_lead.add_note(3, 72, base + tpq * 3, int(tpq * 1.6), velocity=110)

        # Phrase 2: Echo with steel drum shimmer (Bar 2)
        b2 = base + bar_len
        tr_lead.add_note(3, 72, b2 + 0, int(tpq * 0.45), velocity=85)
        tr_lead.add_note(3, 69, b2 + int(tpq * 0.5), int(tpq * 0.4), velocity=80)
        tr_lead.add_note(3, 69, b2 + tpq, int(tpq * 0.4), velocity=82)
        tr_lead.add_note(3, 69, b2 + int(tpq * 1.5), int(tpq * 0.4), velocity=82)
        tr_lead.add_note(3, 67, b2 + tpq * 2, int(tpq * 0.45), velocity=78)
        tr_lead.add_note(3, 65, b2 + int(tpq * 2.5), int(tpq * 0.45), velocity=78)
        tr_lead.add_note(3, 72, b2 + tpq * 3, int(tpq * 1.6), velocity=90)

        # Phrase 3: Ascending Reggae Run (Bar 3)
        b3 = base + bar_len * 2
        tr_lead.add_note(3, 72, b3 + 0, int(tpq * 0.4), velocity=100)
        tr_lead.add_note(3, 70, b3 + int(tpq * 0.5), int(tpq * 0.4), velocity=95)  # Bb4
        tr_lead.add_note(3, 69, b3 + tpq, int(tpq * 0.4), velocity=95)            # A4
        tr_lead.add_note(3, 67, b3 + int(tpq * 1.5), int(tpq * 0.4), velocity=95)  # G4
        tr_lead.add_note(3, 65, b3 + tpq * 2, int(tpq * 0.8), velocity=105)        # F4
        tr_lead.add_note(3, 67, b3 + tpq * 3, int(tpq * 0.8), velocity=100)        # G4

        # Phrase 4: Triumphant Bar 4 Resolution
        b4 = base + bar_len * 3
        tr_lead.add_note(3, 69, b4 + 0, int(tpq * 1.2), velocity=110)            # A4
        tr_lead.add_note(3, 67, b4 + int(tpq * 1.5), int(tpq * 0.5), velocity=95) # G4
        tr_lead.add_note(3, 65, b4 + tpq * 2, int(tpq * 1.8), velocity=115)       # F4 (Tonic resolution)

        # Reggae Brass Horn Stabs answering the melody in Bar 4
        tr_horns.add_chord(4, [65, 69, 72], b4 + int(tpq * 2.5), int(tpq * 0.4), velocity=95)
        tr_horns.add_chord(4, [65, 69, 72], b4 + int(tpq * 3.5), int(tpq * 0.4), velocity=100)

    # Add Vivaldi theme for both 8-bar cycles (Bars 0-7 and Bars 8-15)
    add_vivaldi_phrase(0)
    add_vivaldi_phrase(8)

    # Save to disk
    midi.save(filepath)


def compose_boss_mantis(filepath: str):
    """
    Composes a frantic, driving 16-bit Gothic boss track for Emperor Mantis.
    Gothic Pipe Organ (Patch 19) + Heavy Distortion Bass + Frantic Harpsichord Arpeggios.
    """
    bpm = 144.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_organ = midi.add_track("Gothic Organ")
    tr_bass = midi.add_track("Thrash Bass")
    tr_lead = midi.add_track("Harpsichord Arp")
    tr_drums = midi.add_track("Battle Drums")

    tr_organ.set_instrument(0, 19)   # Church Organ
    tr_bass.set_instrument(1, 38)    # Synth Bass 1
    tr_lead.set_instrument(2, 6)     # Harpsichord
    tr_drums.set_volume(9, 115)

    # D Minor fast diminished battle progression
    # Dm -> Bb -> Gm -> A7 -> Edim -> A7
    chords = [
        [50, 53, 57, 62],  # Dm
        [46, 50, 53, 58],  # Bb
        [43, 46, 50, 55],  # Gm
        [45, 49, 52, 57],  # A7
        [40, 43, 46, 52],  # Edim
        [45, 49, 52, 57],  # A7
        [50, 53, 57, 62],  # Dm
        [50, 53, 57, 65],  # Dm/F
    ]

    for bar_idx, ch in enumerate(chords * 2):
        b_start = bar_idx * bar_len
        # Heavy organ pedal on beat 1 & 3
        tr_organ.add_chord(0, ch, b_start, int(tpq * 1.8), velocity=108)
        tr_organ.add_chord(0, ch, b_start + tpq * 2, int(tpq * 1.8), velocity=112)

        # Driving 16th note bassline
        root = ch[0] - 12
        for s in range(8):
            tr_bass.add_note(1, root if s % 2 == 0 else root + 7, b_start + int(s * (tpq / 2)), int(tpq * 0.4), velocity=102)

        # Harpsichord 16th note arpeggios
        for s in range(16):
            note = ch[s % len(ch)] + 12
            tr_lead.add_note(2, note, b_start + int(s * (tpq / 4)), int(tpq * 0.22), velocity=92)

        # Rock Drum Beat: Kick on 1 & 3, Snare on 2 & 4, continuous hats
        tr_drums.add_note(9, 36, b_start, int(tpq * 0.5), velocity=120)
        tr_drums.add_note(9, 38, b_start + tpq, int(tpq * 0.4), velocity=118)
        tr_drums.add_note(9, 36, b_start + tpq * 2, int(tpq * 0.5), velocity=120)
        tr_drums.add_note(9, 38, b_start + tpq * 3, int(tpq * 0.4), velocity=120)
        for h in range(8):
            tr_drums.add_note(9, 42, b_start + int(h * (tpq / 2)), int(tpq * 0.2), velocity=88)

    midi.save(filepath)


def compose_boss_hound(filepath: str):
    """
    Composes an industrial cybernetic boss track for THE DREAD HOUND.
    Overdriven synth brass, pounding metal percussion, and frantic diminished slides.
    """
    bpm = 152.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_brass = midi.add_track("Cyber Brass")
    tr_bass = midi.add_track("Distorted Sub Bass")
    tr_synth = midi.add_track("Saw Lead")
    tr_drums = midi.add_track("Industrial Drums")

    tr_brass.set_instrument(0, 62)   # Synth Brass 1
    tr_bass.set_instrument(1, 39)    # Synth Bass 2
    tr_synth.set_instrument(2, 81)   # Lead 2 (Sawtooth)
    tr_drums.set_volume(9, 120)

    # C Minor / Tritone industrial riff (C -> F# -> G -> Eb)
    scale_steps = [
        (36, [48, 51, 55]),  # C
        (36, [48, 54, 55]),  # C (F# tritone)
        (34, [46, 50, 53]),  # Bb
        (31, [43, 47, 50]),  # G
    ] * 4

    for bar_idx, (b_note, ch) in enumerate(scale_steps):
        b_start = bar_idx * bar_len
        tr_bass.add_note(1, b_note, b_start, int(tpq * 1.2), velocity=118)
        tr_bass.add_note(1, b_note + 12, b_start + int(tpq * 1.5), int(tpq * 0.4), velocity=105)
        tr_bass.add_note(1, b_note, b_start + tpq * 2, int(tpq * 0.8), velocity=115)
        tr_bass.add_note(1, b_note + 6, b_start + int(tpq * 3.0), int(tpq * 0.8), velocity=110)

        # Aggressive brass hits
        tr_brass.add_chord(0, ch, b_start + tpq, int(tpq * 0.4), velocity=110)
        tr_brass.add_chord(0, ch, b_start + int(tpq * 2.5), int(tpq * 0.4), velocity=108)

        # Fast saw squeal
        lead_note = ch[0] + 24
        tr_synth.add_note(2, lead_note, b_start + int(tpq * 0.5), int(tpq * 0.35), velocity=96)
        tr_synth.add_note(2, lead_note + 3, b_start + int(tpq * 1.5), int(tpq * 0.35), velocity=102)

        # Double-kick metal drums
        for k in (0, 0.5, 2.0, 2.5):
            tr_drums.add_note(9, 36, b_start + int(k * tpq), int(tpq * 0.3), velocity=122)
        tr_drums.add_note(9, 40, b_start + tpq, int(tpq * 0.35), velocity=124)      # Electric snare
        tr_drums.add_note(9, 40, b_start + tpq * 3, int(tpq * 0.35), velocity=124)
        for h in range(8):
            tr_drums.add_note(9, 42, b_start + int(h * (tpq / 2)), int(tpq * 0.2), velocity=95)

    midi.save(filepath)


def compose_boss_toad(filepath: str):
    """
    Composes a heavy funk heavyweight brawler colosseum track for GIGA TOAD.
    Slap Bass + Funky Horn Stabs + Punchy Breakbeat.
    """
    bpm = 118.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_slap = midi.add_track("Slap Bass")
    tr_horns = midi.add_track("Funky Horn Stabs")
    tr_clav = midi.add_track("Clavinet Funk")
    tr_drums = midi.add_track("Punchy Funk Kit")

    tr_slap.set_instrument(0, 36)    # Slap Bass 1
    tr_horns.set_instrument(1, 61)   # Brass Section
    tr_clav.set_instrument(2, 7)     # Clavinet
    tr_drums.set_volume(9, 112)

    # E Minor Heavyweight Funk Groove
    for bar in range(8):
        b_start = bar * bar_len

        # Slap Bass Groove: Thump, pop, slide
        tr_slap.add_note(0, 40, b_start, int(tpq * 0.4), velocity=124)             # E1 thump
        tr_slap.add_note(0, 52, b_start + int(tpq * 0.5), int(tpq * 0.25), velocity=115) # E2 pop
        tr_slap.add_note(0, 43, b_start + int(tpq * 1.5), int(tpq * 0.35), velocity=110) # G1
        tr_slap.add_note(0, 45, b_start + tpq * 2, int(tpq * 0.4), velocity=118)         # A1
        tr_slap.add_note(0, 46, b_start + int(tpq * 2.5), int(tpq * 0.25), velocity=112) # Bb1
        tr_slap.add_note(0, 47, b_start + tpq * 3, int(tpq * 0.6), velocity=122)         # B1

        # Brass punches
        tr_horns.add_chord(1, [64, 67, 71], b_start + int(tpq * 1.5), int(tpq * 0.35), velocity=112)
        tr_horns.add_chord(1, [64, 67, 71], b_start + int(tpq * 3.5), int(tpq * 0.35), velocity=115)

        # Funk drum groove
        tr_drums.add_note(9, 36, b_start, int(tpq * 0.4), velocity=118)
        tr_drums.add_note(9, 38, b_start + tpq, int(tpq * 0.35), velocity=122)
        tr_drums.add_note(9, 36, b_start + int(tpq * 1.75), int(tpq * 0.3), velocity=105)
        tr_drums.add_note(9, 36, b_start + tpq * 2, int(tpq * 0.4), velocity=115)
        tr_drums.add_note(9, 38, b_start + tpq * 3, int(tpq * 0.35), velocity=122)
        for h in range(16):
            tr_drums.add_note(9, 42, b_start + int(h * (tpq / 4)), int(tpq * 0.15), velocity=80 if h % 2 == 1 else 95)

    midi.save(filepath)


def compose_boss_falo_snowman(filepath: str):
    """
    Composes a frantic winter blizzard boss track for FALO THE EVIL SNOWMAN.
    Icy Glockenspiel/Marimba + Shivering Synth + Galloping Blizzard Drums.
    """
    bpm = 156.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_bells = midi.add_track("Icy Bells / Glockenspiel")
    tr_bass = midi.add_track("Frost Bass")
    tr_synth = midi.add_track("Blizzard Synth Lead")
    tr_drums = midi.add_track("Gallop Drums")

    tr_bells.set_instrument(0, 9)    # Glockenspiel
    tr_bass.set_instrument(1, 38)    # Synth Bass 1
    tr_synth.set_instrument(2, 80)   # Lead 1 (Square)
    tr_drums.set_volume(9, 116)

    # A Minor / D# Diminished winter gallop
    progression = [
        ([57, 60, 64], 45),   # Am
        ([57, 60, 64], 45),   # Am
        ([54, 57, 60], 42),   # F#dim (D#)
        ([52, 56, 59], 40),   # E7
    ] * 4

    for bar_idx, (chord, bass_root) in enumerate(progression):
        b_start = bar_idx * bar_len
        # Chilling glockenspiel arpeggio
        for s in range(8):
            pitch = chord[s % len(chord)] + 24
            tr_bells.add_note(0, pitch, b_start + int(s * (tpq / 2)), int(tpq * 0.35), velocity=98)

        # Driving bass gallop (dotted-eighth + sixteenth)
        for step in (0, 0.75, 1.0, 1.75, 2.0, 2.75, 3.0, 3.75):
            tr_bass.add_note(1, bass_root, b_start + int(step * tpq), int(tpq * 0.22), velocity=105)

        # Winter gallop snare & kick
        for beat in range(4):
            tr_drums.add_note(9, 36, b_start + beat * tpq, int(tpq * 0.3), velocity=115)
            tr_drums.add_note(9, 38, b_start + beat * tpq + int(tpq * 0.5), int(tpq * 0.25), velocity=108)

    midi.save(filepath)


def compose_glacial_hot_springs(filepath: str):
    """
    Composes a serene yet chilly atmospheric melody for the Glacial Hot Springs.
    Warm steamy pads, crystal glockenspiel, and gentle syncopated Caribbean steelpan.
    """
    bpm = 96.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_pad = midi.add_track("Warm Steamy Pad")
    tr_steel = midi.add_track("Hot Springs Steelpan")
    tr_bass = midi.add_track("Deep Water Bass")
    tr_drums = midi.add_track("Soft Percussion")

    tr_pad.set_instrument(0, 89)     # Pad 2 (Warm)
    tr_steel.set_instrument(1, 114)  # Steel Drums
    tr_bass.set_instrument(2, 35)    # Fretless Bass
    tr_drums.set_volume(9, 88)

    # G Major / E Minor peaceful steaming progression
    peace_chords = [
        ([55, 59, 62], 43),   # G
        ([52, 55, 59], 40),   # Em
        ([53, 57, 60], 41),   # C
        ([50, 54, 57], 38),   # D
    ] * 2

    for bar_idx, (chord, bass_root) in enumerate(peace_chords):
        b_start = bar_idx * bar_len
        # Warm sustaining chords
        tr_pad.add_chord(0, chord, b_start, int(bar_len * 0.95), velocity=80)
        # Deep warm bass
        tr_bass.add_note(2, bass_root, b_start, int(tpq * 2.8), velocity=92)
        tr_bass.add_note(2, bass_root + 7, b_start + tpq * 3, int(tpq * 0.9), velocity=85)

        # Gentle steelpan melody
        for step in (0.5, 1.5, 2.5, 3.25):
            pitch = chord[(int(step * 3)) % len(chord)] + 12
            tr_steel.add_note(1, pitch, b_start + int(step * tpq), int(tpq * 0.4), velocity=90)

        # Soft water percussion
        tr_drums.add_note(9, 42, b_start, int(tpq * 0.2), velocity=70)
        tr_drums.add_note(9, 42, b_start + tpq, int(tpq * 0.2), velocity=75)
        tr_drums.add_note(9, 37, b_start + tpq * 2, int(tpq * 0.2), velocity=82)  # Soft rim tap
        tr_drums.add_note(9, 42, b_start + tpq * 3, int(tpq * 0.2), velocity=75)

    midi.save(filepath)


def compose_title_theme(filepath: str):
    """
    Composes a triumphant 16-bit tropical title screen theme at 124 BPM.
    """
    bpm = 124.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_lead = midi.add_track("Fanfare Lead")
    tr_bass = midi.add_track("Slap Bass")
    tr_chords = midi.add_track("Brass Chords")
    tr_drums = midi.add_track("Title Drums")

    tr_lead.set_instrument(0, 12)    # Marimba
    tr_bass.set_instrument(1, 33)    # Fingered Bass
    tr_chords.set_instrument(2, 61)  # Brass Section
    tr_drums.set_volume(9, 110)

    # C - F - G - C Triumphant fanfare
    bars = [
        ([60, 64, 67], 36),  # C
        ([57, 60, 65], 41),  # F
        ([59, 62, 67], 43),  # G
        ([60, 64, 67], 36),  # C
    ] * 2

    for bar_idx, (chord, bass_root) in enumerate(bars):
        b_start = bar_idx * bar_len
        tr_chords.add_chord(2, chord, b_start + int(tpq * 0.5), int(tpq * 0.45), velocity=96)
        tr_chords.add_chord(2, chord, b_start + int(tpq * 1.5), int(tpq * 0.45), velocity=102)

        tr_bass.add_note(1, bass_root, b_start, int(tpq * 1.8), velocity=108)
        tr_bass.add_note(1, bass_root + 7, b_start + tpq * 2, int(tpq * 1.8), velocity=105)

        # Marimba fanfare arpeggio
        for s in range(4):
            tr_lead.add_note(0, chord[s % len(chord)] + 12, b_start + s * tpq, int(tpq * 0.4), velocity=105)

        tr_drums.add_note(9, 36, b_start, int(tpq * 0.5), velocity=115)
        tr_drums.add_note(9, 38, b_start + tpq, int(tpq * 0.4), velocity=118)
        tr_drums.add_note(9, 36, b_start + tpq * 2, int(tpq * 0.5), velocity=115)
        tr_drums.add_note(9, 38, b_start + tpq * 3, int(tpq * 0.4), velocity=118)

    midi.save(filepath)


def compose_volcanic_magma(filepath: str):
    """
    Composes an intense 16-bit Volcanic Magma Chasm theme at 136 BPM.
    Features E Phrygian Dominant overdrive guitar riffs, slap bass ostinatos,
    and tribal tom/snare rhythms evoking molten subterranean caverns.
    """
    bpm = 136.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_lead = midi.add_track("Molten Overdrive Lead")
    tr_bass = midi.add_track("Volcanic Slap Bass")
    tr_pad = midi.add_track("Magma Choir Pad")
    tr_drums = midi.add_track("Tribal Forge Drums")

    tr_lead.set_instrument(0, 29)    # Overdriven Guitar
    tr_bass.set_instrument(1, 36)    # Slap Bass 1
    tr_pad.set_instrument(2, 52)     # Choir Aahs
    tr_drums.set_volume(9, 114)

    # E Phrygian Dominant progression: E -> F -> G -> F
    progression = [
        ([52, 56, 59], 40),   # E Major / Phrygian
        ([53, 57, 60], 41),   # F Major
        ([55, 59, 62], 43),   # G Major
        ([53, 57, 60], 41),   # F Major turnaround
    ] * 2

    for bar_idx, (chord, bass_root) in enumerate(progression):
        b_start = bar_idx * bar_len
        tr_pad.add_chord(2, chord, b_start, int(bar_len * 0.92), velocity=84)

        # Driving 8th-note volcanic bass pulse
        for s in range(8):
            pitch = bass_root if s % 2 == 0 else bass_root + 12
            tr_bass.add_note(1, pitch, b_start + int(s * (tpq / 2)), int(tpq * 0.38), velocity=106)

        # Phrygian melodic lead motif
        motif = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[1] + 12, chord[0] + 13, chord[0] + 12]
        for idx, note in enumerate(motif):
            tr_lead.add_note(0, note, b_start + int(idx * (tpq * 0.66)), int(tpq * 0.5), velocity=102)

        # Heavy tribal tom & double-kick groove
        for beat in range(4):
            t_b = b_start + beat * tpq
            tr_drums.add_note(9, 36, t_b, int(tpq * 0.35), velocity=115)
            tr_drums.add_note(9, 45 if beat % 2 == 0 else 47, t_b + int(tpq * 0.5), int(tpq * 0.3), velocity=100)
            if beat in (1, 3):
                tr_drums.add_note(9, 38, t_b, int(tpq * 0.35), velocity=112)

    midi.save(filepath)


def compose_sunken_grotto(filepath: str):
    """
    Composes a dreamy, crystalline 16-bit Sunken Submarine Grotto theme at 98 BPM.
    Inspired by Donkey Kong Country's 'Aquatic Ambience' — featuring lush Rhodes
    electric piano chords, shimmering vibraphone/celesta arpeggios, and deep fretless bass.
    """
    bpm = 98.0
    midi = MidiFile(tempo_bpm=bpm)
    tpq = TICKS_PER_BEAT
    bar_len = tpq * 4

    tr_epiano = midi.add_track("Submarine Electric Piano")
    tr_vibes = midi.add_track("Bioluminescent Vibraphone Arpeggio")
    tr_bass = midi.add_track("Abyssal Fretless Bass")
    tr_drums = midi.add_track("Submerged Echo Percussion")

    tr_epiano.set_instrument(0, 5)   # Electric Piano 2 (DX7 Rhodes)
    tr_vibes.set_instrument(1, 11)   # Vibraphone
    tr_bass.set_instrument(2, 35)    # Fretless Bass
    tr_drums.set_volume(9, 82)

    # D Dorian aquatic progression: Dm7 -> G/D -> Cmaj7 -> Am7
    aqua_chords = [
        ([50, 53, 57, 60], 38),  # Dm7
        ([50, 55, 59, 62], 43),  # G/D
        ([48, 52, 55, 59], 36),  # Cmaj7
        ([45, 52, 55, 60], 33),  # Am7
    ] * 2

    for bar_idx, (chord, bass_root) in enumerate(aqua_chords):
        b_start = bar_idx * bar_len
        tr_epiano.add_chord(0, chord, b_start, int(bar_len * 0.95), velocity=82)
        tr_bass.add_note(2, bass_root, b_start, int(tpq * 2.5), velocity=94)
        tr_bass.add_note(2, bass_root + 7, b_start + int(tpq * 2.5), int(tpq * 1.4), velocity=86)

        # Flowing 16th-note underwater arpeggio
        for s in range(8):
            note = chord[s % len(chord)] + 12
            tr_vibes.add_note(1, note, b_start + int(s * (tpq / 2)), int(tpq * 0.45), velocity=88)

        # Gentle submerged hi-hat & soft rim echo
        for beat in range(4):
            tr_drums.add_note(9, 42, b_start + beat * tpq, int(tpq * 0.2), velocity=64)
        tr_drums.add_note(9, 36, b_start, int(tpq * 0.4), velocity=84)
        tr_drums.add_note(9, 37, b_start + tpq * 2, int(tpq * 0.3), velocity=76)

    midi.save(filepath)


def build_all_midi_soundtrack():
    """Generates all Standard MIDI soundtrack files into assets/music/."""
    music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "music")
    os.makedirs(music_dir, exist_ok=True)
    print(f"[MidiComposer] Generating complete 16-bit MIDI soundtrack into {music_dir}...")

    compose_jamaican_vivaldi_four_seasons(os.path.join(music_dir, "jungle_vivaldi_reggae.mid"))
    compose_boss_mantis(os.path.join(music_dir, "boss_mantis.mid"))
    compose_boss_hound(os.path.join(music_dir, "boss_hound.mid"))
    compose_boss_toad(os.path.join(music_dir, "boss_toad.mid"))
    compose_boss_falo_snowman(os.path.join(music_dir, "boss_snowman.mid"))
    compose_glacial_hot_springs(os.path.join(music_dir, "ice_hot_springs.mid"))
    compose_title_theme(os.path.join(music_dir, "title_theme.mid"))
    compose_volcanic_magma(os.path.join(music_dir, "volcanic_magma.mid"))
    compose_sunken_grotto(os.path.join(music_dir, "sunken_grotto.mid"))

    print("[MidiComposer] All 9 Standard MIDI soundtrack files successfully composed and saved!")


if __name__ == "__main__":
    build_all_midi_soundtrack()
