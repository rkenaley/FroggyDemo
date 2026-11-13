"""
===============================================================================
FROGGY DEMO - 16-BIT MIDI MUSIC COMPOSER & FILE GENERATOR
===============================================================================
This module is a pure-Python Standard MIDI File (SMF Format 1) generator.
It creates rich, multi-section 16-bit retro soundtrack files (.mid) that can be:
  1. Played natively in the game via Pygame's hardware/software MIDI synthesizer.
  2. Opened, inspected, and edited by creators (like your nephew!) in standard
     music production software (DAWs) such as:
       - MuseScore (Free notation editor)
       - FL Studio / Ableton / Reaper
       - Sekaiju (Free retro MIDI sequencer)
       - BandLab / GarageBand

MUSICAL STRUCTURE:
Every song is composed as an extended multi-section arrangement (48 to 64 bars,
~90-135 seconds per loop) with 4-to-8 bar evolving melodic phrases, Intro,
Verse (A/A'), Chorus (B), Bridge / Instrumental Solo (C), Modulated Climax (D),
and Turnaround sections, plus dynamic drum fills and varied bass/arp grooves so
loops feel full, expressive, and never short or repetitive.
===============================================================================
"""

import os
import struct

TICKS_PER_BEAT = 480  # Standard MIDI PPQN (Pulses Per Quarter Note)
BAR_TICKS = TICKS_PER_BEAT * 4


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
        self.events.append(MidiEvent(start_tick, bytes([0x90 | ch, pitch & 0x7F, vel])))
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

        track_bytes += var_len(0) + b'\xFF\x2F\x00'
        return b'MTrk' + struct.pack('>I', len(track_bytes)) + track_bytes


class MidiFile:
    """Represents a standard Format 1 MIDI file containing multiple tracks."""

    def __init__(self, tempo_bpm: float = 120.0):
        self.tempo_bpm = tempo_bpm
        self.tracks = []
        self._setup_conductor_track(tempo_bpm)

    def _setup_conductor_track(self, bpm: float):
        conductor = MidiTrack("Conductor / Tempo")
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
        num_tracks = len(self.tracks)
        header = b'MThd' + struct.pack('>IHHH', 6, 1, num_tracks, TICKS_PER_BEAT)
        with open(filepath, 'wb') as f:
            f.write(header)
            for tr in self.tracks:
                f.write(tr.serialize())
        print(f"[MidiComposer] Exported Standard MIDI File: {filepath}")


# =============================================================================
# SHARED ARRANGEMENT & GROOVE PRIMITIVES
# =============================================================================

def setup_track(midi: MidiFile, name: str, channel: int, patch: int,
                volume: int = 100, pan: int = 64) -> MidiTrack:
    """Creates a track with instrument patch, volume, and stereo pan configured."""
    tr = midi.add_track(name)
    if channel != 9 and patch is not None:
        tr.set_instrument(channel, patch)
    tr.set_volume(channel, volume)
    tr.set_pan(channel, pan)
    return tr


def section_pos(bar: int, boundaries):
    """
    Maps an absolute bar index to (section_name, bar_within_section, is_section_start)
    given ordered (start_bar, section_name) tuples.
    """
    chosen_idx = 0
    for idx, (start_b, _) in enumerate(boundaries):
        if bar >= start_b:
            chosen_idx = idx
    start_b, name = boundaries[chosen_idx]
    return name, bar - start_b, (bar == start_b)


def emit_bar_phrase(track: MidiTrack, channel: int, bar_idx: int, notes,
                    transpose: int = 0, vel_scale: float = 1.0,
                    max_end_bar: int = None):
    """
    Writes a list of (beat_offset, pitch_or_chord, beat_dur, vel) events relative
    to bar_idx, clamping note-offs inside max_end_bar for clean DAW/game loops.
    """
    tpq = TICKS_PER_BEAT
    b_start = bar_idx * BAR_TICKS
    max_tick = (max_end_bar * BAR_TICKS - 12) if max_end_bar is not None else None
    for beat_off, pitch, beat_dur, vel in notes:
        if pitch is None:
            continue
        t0 = b_start + int(round(beat_off * tpq))
        dur = max(20, int(round(beat_dur * tpq)))
        if max_tick is not None:
            if t0 >= max_tick:
                continue
            dur = min(dur, max_tick - t0)
        v = max(1, min(127, int(round(vel * vel_scale))))
        if isinstance(pitch, (tuple, list)):
            for p in pitch:
                track.add_note(channel, p + transpose, t0, dur, velocity=v)
        else:
            track.add_note(channel, pitch + transpose, t0, dur, velocity=v)


def emit_bass_bar(track: MidiTrack, channel: int, bar_idx: int, root: int,
                  chord, style: str, bar_in_phrase: int = 0,
                  vel: int = 104):
    """Generates varied 1-bar bass grooves reactive to section & phrase position."""
    tpq = TICKS_PER_BEAT
    b_start = bar_idx * BAR_TICKS
    third = chord[1] - 12 if len(chord) > 1 and chord[1] - 12 >= 24 else root + 4
    fifth = root + 7
    octave = root + 12

    if style == "reggae_dub":
        pattern = [(0.0, root, 0.85, vel), (1.5, fifth, 0.65, vel - 12),
                   (2.0, root, 0.70, vel - 4), (3.0, octave, 0.45, vel - 14),
                   (3.5, third if bar_in_phrase % 2 == 1 else fifth, 0.42, vel - 16)]
    elif style == "double_kick_metal":
        alt = root + (1 if bar_in_phrase % 4 == 3 else 7)
        pattern = [(i * 0.5, alt if i in (6, 7) else root, 0.38,
                    vel if i % 2 == 0 else vel - 14) for i in range(8)]
    elif style == "gallop":
        pattern = []
        for beat in range(4):
            p = fifth if (beat == 3 and bar_in_phrase % 2 == 1) else root
            pattern.append((beat + 0.0, p, 0.35, vel))
            pattern.append((beat + 0.5, p, 0.18, vel - 18))
            pattern.append((beat + 0.75, octave if beat == 2 else p, 0.18, vel - 16))
    elif style == "mario_bounce":
        mid = fifth if bar_in_phrase % 2 == 0 else third
        pattern = [(0.0, root, 0.72, vel), (1.0, fifth, 0.68, vel - 8),
                   (2.0, octave, 0.72, vel - 4), (3.0, mid, 0.68, vel - 10)]
    elif style == "slap_funk":
        pattern = [(0.0, root, 0.35, vel), (0.75, root, 0.28, vel - 12),
                   (1.5, octave, 0.32, vel - 6), (2.25, fifth, 0.35, vel - 14),
                   (2.75, root, 0.32, vel - 8),
                   (3.5, octave - 2 if bar_in_phrase % 2 else fifth, 0.35, vel - 6)]
    elif style == "walking":
        turn = fifth + 2 if bar_in_phrase % 2 == 1 else fifth - 1
        pattern = [(0.0, root, 0.88, vel), (1.0, third, 0.85, vel - 10),
                   (2.0, fifth, 0.85, vel - 6), (3.0, turn, 0.85, vel - 12)]
    elif style == "sonar_pulse":
        pattern = [(0.0, root, 1.65, vel), (2.0, fifth, 0.85, vel - 16),
                   (3.5, octave, 0.42, vel - 12)]
    else:
        pattern = [(0.0, root, 1.80, vel), (2.0, root, 0.90, vel - 8),
                   (3.0, fifth, 0.85, vel - 10)]

    for off, p, dur, v in pattern:
        track.add_note(channel, p, b_start + int(off * tpq), int(dur * tpq), velocity=v)


def emit_arp_bar(track: MidiTrack, channel: int, bar_idx: int, chord,
                 pattern: str = "up", subdivision: int = 8,
                 octave_shift: int = 0, vel: int = 74):
    """Generates rhythmic arpeggio patterns cleanly across a single bar."""
    b_start = bar_idx * BAR_TICKS
    notes = [p + octave_shift for p in chord]
    if not notes:
        return
    if pattern == "up_down" and len(notes) >= 3:
        seq = notes + list(reversed(notes[1:-1]))
    elif pattern == "down":
        seq = list(reversed(notes))
    else:
        seq = notes

    step_ticks = BAR_TICKS // subdivision
    for i in range(subdivision):
        p = seq[i % len(seq)]
        t0 = b_start + i * step_ticks
        v = vel - (8 if i % 2 == 1 else 0)
        track.add_note(channel, p, t0, int(step_ticks * 0.82), velocity=v)


def emit_drum_bar(track: MidiTrack, bar_idx: int, style: str,
                  bar_in_phrase: int = 0, is_section_start: bool = False,
                  is_fill_bar: bool = False, fill_variant: int = 0,
                  intensity: float = 1.0):
    """
    Channel 9 General MIDI Drum pattern generator with crash transitions on
    section downbeats and varied 4th/8th-bar fills to eliminate loop monotony.
    """
    tpq = TICKS_PER_BEAT
    b_start = bar_idx * BAR_TICKS

    def hit(drum, beat_off, vel, dur_beats=0.22):
        v = max(1, min(127, int(vel * intensity)))
        track.add_note(9, drum, b_start + int(beat_off * tpq), int(dur_beats * tpq), velocity=v)

    if is_section_start:
        hit(49 if fill_variant % 2 == 0 else 57, 0.0, 110, 0.5)

    limit = 3.0 if is_fill_bar else 4.0

    if style == "one_drop_reggae":
        for eighth in range(int(limit * 2)):
            b = eighth * 0.5
            hit(42, b, 84 if eighth % 2 == 0 else 64, 0.16)
            if eighth % 2 == 1:
                hit(60 if eighth in (1, 5) else 61, b, 58, 0.14)
        hit(37, 1.0, 90)
        hit(36, 2.0, 114)
        hit(38, 2.0, 102)
        if not is_fill_bar:
            hit(46, 3.5, 80, 0.3)
    elif style in ("double_kick_metal", "fast_thrash"):
        kick = 35 if style == "double_kick_metal" else 36
        for sixteenth in range(int(limit * 4)):
            hit(kick, sixteenth * 0.25, 112 if sixteenth % 4 == 0 else 92, 0.12)
        for eighth in range(int(limit * 2)):
            hit(51 if style == "double_kick_metal" and bar_in_phrase % 2 else 42,
                eighth * 0.5, 92 if eighth % 2 == 0 else 74, 0.15)
        for b in (1.0, 3.0):
            if b < limit:
                hit(38, b, 116)
    elif style in ("heavy_stomp", "castle_march", "heroic_march"):
        for b in (0.0, 2.0):
            if b < limit:
                hit(36, b, 116)
        if style == "castle_march" and 2.5 < limit:
            hit(36, 2.5, 98)
        for b in (1.0, 3.0):
            if b < limit:
                hit(38, b, 108)
        for eighth in range(int(limit * 2)):
            hit(42 if eighth % 2 == 0 else 44, eighth * 0.5, 82 if eighth % 2 == 0 else 64, 0.16)
    elif style == "deep_breakbeat":
        for b in (0.0, 0.75, 2.25):
            if b < limit:
                hit(36, b, 112)
        for b in (1.0, 2.75):
            if b < limit:
                hit(38, b, 106)
        for sixteenth in range(int(limit * 4)):
            if sixteenth % 2 == 0 or bar_in_phrase % 2 == 1:
                hit(42, sixteenth * 0.25, 76 if sixteenth % 2 == 0 else 54, 0.12)
    elif style == "sky_arcade":
        for beat in range(int(limit)):
            hit(36 if beat in (0, 2) else 38, float(beat), 112)
            hit(42, beat + 0.5, 88)
        if bar_in_phrase % 2 == 1 and 1.75 < limit:
            hit(36, 1.75, 90)
    elif style == "tribal_percussion":
        for beat in range(int(limit)):
            hit(62 if beat % 2 == 0 else 63, float(beat), 88)
            hit(64, beat + 0.5, 78)
        hit(36, 0.0, 102)
        if 2.0 < limit:
            hit(36, 2.0, 96)
    elif style in ("soft_ambient", "sonar_pulse"):
        hit(36, 0.0, 82)
        if 2.5 < limit and style == "sonar_pulse":
            hit(36, 2.5, 74)
        for eighth in range(int(limit * 2)):
            hit(42 if eighth != 7 else 46, eighth * 0.5, 62 if eighth % 2 == 0 else 48, 0.16)
        if 1.0 < limit:
            hit(37, 1.0, 74)
        if 3.0 < limit:
            hit(37, 3.0, 76)
    else:
        for beat in range(int(limit)):
            hit(36 if beat % 2 == 0 else 38, float(beat), 110 if beat % 2 == 0 else 106)
            hit(42, beat + 0.0, 82)
            hit(42, beat + 0.5, 72)

    if is_fill_bar:
        v_mod = fill_variant % 4
        if v_mod == 0:
            for idx, drum in enumerate((38, 48, 45, 43)):
                hit(drum, 3.0 + idx * 0.25, 96 + idx * 5, 0.2)
        elif v_mod == 1:
            hit(38, 3.0, 108)
            hit(36, 3.25, 102)
            hit(38, 3.5, 112)
            hit(46, 3.75, 94, 0.25)
        elif v_mod == 2:
            for idx, drum in enumerate((65, 66, 38, 49)):
                hit(drum, 3.0 + idx * 0.25, 92 + idx * 6, 0.2)
        else:
            for idx in range(4):
                hit(38, 3.0 + idx * 0.25, 78 + idx * 12, 0.18)


# =============================================================================
# 17 EXTENDED MULTI-SECTION COMPOSITIONS
# =============================================================================

def compose_jamaican_vivaldi_four_seasons(filepath: str):
    """56-Bar Jamaican Reggae / Dub adaptation of Vivaldi's 'Spring' (F Major)."""
    midi = MidiFile(tempo_bpm=112.0)
    tr_organ = setup_track(midi, "Reggae Organ Skank", 0, 18, 96, 32)
    tr_gtr = setup_track(midi, "Clean Guitar Chop", 1, 27, 88, 96)
    tr_bass = setup_track(midi, "Electric Dub Bass", 2, 33, 112, 64)
    tr_lead = setup_track(midi, "Vivaldi Brass & Flute Lead", 3, 61, 106, 64)
    tr_steel = setup_track(midi, "Steel Drums Harmony", 4, 114, 94, 88)
    tr_harpsi = setup_track(midi, "Baroque Harpsichord", 5, 6, 82, 42)
    tr_drums = setup_track(midi, "One-Drop Reggae Kit", 9, None, 104, 64)

    F_maj, C_maj, Dm, Bb_maj, Gm, Am, A7 = (
        (65, 69, 72), (60, 64, 67), (62, 65, 69), (58, 62, 65),
        (67, 70, 74), (69, 72, 76), (57, 61, 64, 67),
    )
    prog_A = [(41, F_maj), (41, F_maj), (36, C_maj), (41, F_maj), (34, Bb_maj), (41, F_maj), (36, C_maj), (41, F_maj)]
    prog_B = [(41, F_maj), (36, C_maj), (38, Dm), (33, Am), (34, Bb_maj), (31, Gm), (36, C_maj), (41, F_maj)]
    prog_C = [(38, Dm), (31, Gm), (33, A7), (38, Dm), (34, Bb_maj), (36, C_maj), (38, Dm), (33, A7)]
    prog_D = [(38, Dm), (31, Gm), (36, C_maj), (41, F_maj), (34, Bb_maj), (31, Gm), (33, A7), (36, C_maj)]

    spring_4bar = [
        [(0.0, 65, 0.4, 104), (0.5, 69, 0.4, 100), (1.0, 69, 0.4, 102), (1.5, 69, 0.4, 100), (2.0, 65, 0.4, 98), (2.5, 67, 0.4, 98), (3.0, 72, 0.85, 112)],
        [(0.0, 72, 0.4, 108), (0.5, 70, 0.4, 102), (1.0, 69, 0.4, 104), (1.5, 67, 0.4, 100), (2.0, 69, 0.4, 102), (2.5, 70, 0.4, 100), (3.0, 65, 0.85, 108)],
        [(0.0, 74, 0.4, 108), (0.5, 72, 0.4, 104), (1.0, 70, 0.4, 102), (1.5, 69, 0.4, 100), (2.0, 70, 0.4, 102), (2.5, 72, 0.4, 104), (3.0, 69, 0.85, 108)],
        [(0.0, 67, 0.4, 102), (0.5, 69, 0.4, 104), (1.0, 70, 0.4, 106), (1.5, 72, 0.4, 108), (2.0, 69, 0.85, 106), (3.0, 65, 0.85, 110)],
    ]
    birdsong_4bar = [
        [(0.0, 77, 0.22, 98), (0.25, 76, 0.22, 96), (0.5, 77, 0.22, 100), (0.75, 74, 0.22, 96), (1.0, 72, 0.45, 104), (1.5, 74, 0.45, 102), (2.0, 76, 0.45, 100), (2.5, 74, 0.45, 98), (3.0, 72, 0.85, 108)],
        [(0.0, 74, 0.45, 102), (0.5, 76, 0.45, 104), (1.0, 77, 0.45, 106), (1.5, 74, 0.45, 102), (2.0, 72, 0.45, 100), (2.5, 70, 0.45, 98), (3.0, 69, 0.85, 106)],
        [(0.0, 70, 0.45, 102), (0.5, 72, 0.45, 104), (1.0, 74, 0.45, 106), (1.5, 76, 0.45, 108), (2.0, 77, 0.85, 110), (3.0, 74, 0.85, 104)],
        [(0.0, 72, 0.45, 104), (0.5, 70, 0.45, 100), (1.0, 69, 0.45, 102), (1.5, 67, 0.45, 98), (2.0, 69, 0.85, 104), (3.0, 65, 0.85, 108)],
    ]
    dub_4bar = [
        [(0.0, 62, 0.85, 96), (1.0, 65, 0.45, 100), (1.5, 69, 0.85, 104), (2.5, 67, 0.45, 96), (3.0, 65, 0.85, 100)],
        [(0.0, 67, 0.85, 100), (1.0, 70, 0.45, 102), (1.5, 69, 0.85, 98), (2.5, 65, 0.45, 96), (3.0, 64, 0.85, 98)],
        [(0.0, 65, 0.85, 100), (1.0, 67, 0.45, 102), (1.5, 70, 0.85, 106), (2.5, 72, 0.45, 104), (3.0, 69, 0.85, 102)],
        [(0.0, 69, 0.45, 102), (0.5, 67, 0.45, 98), (1.0, 65, 0.85, 100), (2.0, 64, 0.85, 98), (3.0, 62, 0.85, 104)],
    ]
    storm_runs = [
        [(i * 0.25, p, 0.22, 98 + (i % 4) * 4) for i, p in enumerate([74, 72, 70, 69, 67, 69, 70, 72, 74, 76, 77, 76, 74, 72, 70, 69])],
        [(i * 0.25, p, 0.22, 98 + (i % 4) * 4) for i, p in enumerate([77, 76, 74, 72, 70, 72, 74, 76, 77, 79, 81, 79, 77, 76, 74, 72])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (28, "D"), (36, "E"), (44, "F"), (52, "TURN")]
    total_bars = 56
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (41, F_maj) if b_sec in (0, 1, 3) else (36, C_maj)
            emit_bass_bar(tr_bass, 2, bar, root, chord, "reggae_dub", bar, 98)
            emit_arp_bar(tr_harpsi, 5, bar, chord, "up", 8, 0, 78)
            if b_sec >= 2:
                emit_bar_phrase(tr_steel, 4, bar, spring_4bar[b_sec - 2], 12, 0.94, total_bars)
            emit_drum_bar(tr_drums, bar, "one_drop_reggae", b_sec, is_sec, b_sec == 3, bar, 0.88)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_lead, 3, bar, spring_4bar[b_sec % 4], 0, 1.0, total_bars)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_steel, 4, bar, birdsong_4bar[b_sec % 4], 0, 1.0, total_bars)
            emit_bar_phrase(tr_harpsi, 5, bar, spring_4bar[b_sec % 4], 0, 0.78, total_bars)
        elif sec == "C":
            root, chord = prog_C[b_sec % 8]
            emit_bar_phrase(tr_organ, 0, bar, dub_4bar[b_sec % 4], 0, 0.96, total_bars)
            if b_sec % 2 == 1:
                emit_bar_phrase(tr_steel, 4, bar, dub_4bar[b_sec % 4], 12, 0.86, total_bars)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            emit_bar_phrase(tr_harpsi, 5, bar, storm_runs[b_sec % 2], 0, 1.04, total_bars)
            emit_bar_phrase(tr_lead, 3, bar, birdsong_4bar[b_sec % 4], -12 if b_sec >= 4 else 0, 1.0, total_bars)
        elif sec == "E":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_lead, 3, bar, spring_4bar[b_sec % 4], 0, 1.06, total_bars)
            emit_bar_phrase(tr_steel, 4, bar, spring_4bar[b_sec % 4], 4, 0.88, total_bars)
            emit_arp_bar(tr_harpsi, 5, bar, chord, "up_down", 8, 12, 80)
        elif sec == "F":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_steel, 4, bar, storm_runs[b_sec % 2] if b_sec % 2 == 0 else birdsong_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_bar_phrase(tr_lead, 3, bar, spring_4bar[b_sec % 4], 12 if b_sec >= 4 else 0, 0.94, total_bars)
        else:
            t_chords = [(34, Bb_maj), (36, C_maj), (31, Gm), (41, F_maj)]
            root, chord = t_chords[b_sec % 4]
            emit_bar_phrase(tr_lead, 3, bar, spring_4bar[b_sec % 4], 0, 1.0, total_bars)
            emit_bar_phrase(tr_steel, 4, bar, spring_4bar[b_sec % 4], 12, 0.9, total_bars)

        for beat in (1, 3):
            sk_t = bar * BAR_TICKS + beat * TICKS_PER_BEAT
            tr_organ.add_chord(0, chord, sk_t, 120, velocity=86)
            tr_gtr.add_chord(1, chord, sk_t, 95, velocity=80)
            tr_organ.add_chord(0, chord, sk_t + TICKS_PER_BEAT // 2, 100, velocity=64)

        emit_bass_bar(tr_bass, 2, bar, root, chord, "reggae_dub", b_sec, 110)
        emit_drum_bar(tr_drums, bar, "one_drop_reggae", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_boss_mantis(filepath: str):
    """60-Bar Boss Theme 1: Emperor Mantis (High-Speed 16-Bit Prog Metal, 154 BPM)."""
    midi = MidiFile(tempo_bpm=154.0)
    tr_lead = setup_track(midi, "Sawtooth Shred Lead", 0, 81, 106, 56)
    tr_harm = setup_track(midi, "Dual Twin Harmony Lead", 1, 80, 90, 82)
    tr_bass = setup_track(midi, "Slap Mantis Bass", 2, 36, 112, 64)
    tr_gtr = setup_track(midi, "Distortion Guitar", 3, 30, 96, 36)
    tr_harpsi = setup_track(midi, "Royal Mantis Harpsichord", 4, 6, 84, 94)
    tr_drums = setup_track(midi, "Double-Kick Metal Kit", 9, None, 114, 64)

    Dm, Eb, Gm, Cm, A7, Bb, Ebm, Fm, Bb7 = (
        (62, 65, 69), (63, 67, 70), (67, 70, 74), (60, 63, 67),
        (57, 61, 64, 67), (58, 62, 65), (63, 66, 70), (65, 68, 72), (58, 62, 65, 68),
    )
    prog_A = [(38, Dm), (39, Eb), (36, Gm), (33, A7), (38, Dm), (34, Bb), (31, Gm), (33, A7)]
    prog_B = [(31, Gm), (36, Cm), (34, Bb), (38, Dm), (31, Gm), (39, Eb), (36, Cm), (33, A7)]
    prog_D = [(39, Ebm), (41, Fm), (39, Ebm), (34, Bb7), (39, Ebm), (37, Cm), (39, Ebm), (34, Bb7)]

    shred_4bar = [
        [(i * 0.25, p, 0.22, 106) for i, p in enumerate([62, 63, 65, 69, 70, 69, 65, 63, 62, 65, 69, 74, 73, 70, 69, 65])],
        [(i * 0.25, p, 0.22, 108) for i, p in enumerate([74, 73, 70, 69, 67, 65, 63, 62, 69, 67, 65, 63, 62, 61, 62, 65])],
        [(i * 0.25, p, 0.22, 108) for i, p in enumerate([69, 70, 74, 77, 76, 74, 70, 69, 67, 69, 70, 74, 77, 79, 81, 77])],
        [(i * 0.25, p, 0.22, 110) for i, p in enumerate([81, 79, 77, 76, 74, 73, 70, 69, 74, 70, 69, 65, 69, 67, 65, 62])],
    ]
    royal_4bar = [
        [(0.0, 67, 0.7, 104), (0.75, 70, 0.65, 102), (1.5, 74, 0.85, 108), (2.5, 72, 0.45, 100), (3.0, 70, 0.45, 98), (3.5, 69, 0.42, 102)],
        [(0.0, 70, 0.7, 106), (0.75, 74, 0.65, 104), (1.5, 75, 0.85, 110), (2.5, 74, 0.45, 102), (3.0, 72, 0.45, 100), (3.5, 70, 0.42, 102)],
        [(0.0, 74, 0.7, 108), (0.75, 77, 0.65, 106), (1.5, 79, 0.85, 112), (2.5, 77, 0.45, 104), (3.0, 75, 0.45, 102), (3.5, 74, 0.42, 104)],
        [(0.0, 75, 0.45, 106), (0.5, 74, 0.45, 104), (1.0, 72, 0.45, 102), (1.5, 70, 0.45, 100), (2.0, 69, 0.85, 108), (3.0, 67, 0.85, 106)],
    ]
    samurai_solo = [
        [(i * 0.5, p, 0.42, 110) for i, p in enumerate([74, 70, 69, 67, 65, 67, 70, 74])],
        [(i * 0.5, p, 0.42, 112) for i, p in enumerate([75, 74, 72, 70, 69, 70, 74, 77])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "Ap"), (20, "B"), (28, "C"), (36, "D"), (48, "TURN")]
    total_bars = 60
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            emit_bass_bar(tr_bass, 2, bar, 38 + (b_sec if b_sec < 3 else 7), Dm, "gallop", b_sec, 106)
            emit_arp_bar(tr_harpsi, 4, bar, Dm, "up_down", 16, 12, 78 + b_sec * 5)
            if b_sec >= 2:
                emit_bar_phrase(tr_lead, 0, bar, shred_4bar[b_sec - 2], 0, 0.95, total_bars)
            emit_drum_bar(tr_drums, bar, "double_kick_metal", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_lead, 0, bar, shred_4bar[b_sec % 4], 0, 1.0, total_bars)
        elif sec == "Ap":
            root, chord = prog_A[b_sec % 8]
            mel = shred_4bar[b_sec % 4]
            emit_bar_phrase(tr_lead, 0, bar, mel, 0, 1.05, total_bars)
            emit_bar_phrase(tr_harm, 1, bar, mel, 4 if b_sec % 2 == 0 else 7, 0.9, total_bars)
            emit_arp_bar(tr_harpsi, 4, bar, chord, "down", 8, 12, 78)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_lead, 0, bar, royal_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_arp_bar(tr_harpsi, 4, bar, chord, "up_down", 16, 0, 84)
        elif sec == "C":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_harm, 1, bar, samurai_solo[b_sec % 2] if b_sec < 4 else shred_4bar[b_sec % 4], 0, 1.04, total_bars)
            emit_bar_phrase(tr_lead, 0, bar, shred_4bar[b_sec % 4] if b_sec % 2 else royal_4bar[b_sec % 4], -12 if b_sec < 4 else 0, 0.92, total_bars)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            mel = shred_4bar[b_sec % 4]
            emit_bar_phrase(tr_lead, 0, bar, mel, 1, 1.08, total_bars)
            emit_bar_phrase(tr_harm, 1, bar, mel, 5, 0.96, total_bars)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_lead, 0, bar, royal_4bar[b_sec % 4] if b_sec < 8 else shred_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_arp_bar(tr_harpsi, 4, bar, chord, "up", 16, 0, 82)

        for beat in (0, 2):
            tr_gtr.add_chord(3, (root + 12, root + 19, root + 24),
                             bar * BAR_TICKS + beat * TICKS_PER_BEAT, int(TICKS_PER_BEAT * 0.72), 96)
        emit_bass_bar(tr_bass, 2, bar, root, chord, "double_kick_metal", b_sec, 110)
        d_style = "heavy_stomp" if (sec == "C" and b_sec < 4) else "double_kick_metal"
        emit_drum_bar(tr_drums, bar, d_style, b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.02)

    midi.save(filepath)


def compose_boss_hound(filepath: str):
    """64-Bar Boss Theme 2: Dread Hound (Thrash Metal & Inferno Organ, 166 BPM)."""
    midi = MidiFile(tempo_bpm=166.0)
    tr_gtr = setup_track(midi, "Thrash Guitar Riff", 0, 30, 108, 42)
    tr_gtr2 = setup_track(midi, "Harmony Lead Guitar", 1, 29, 94, 86)
    tr_bass = setup_track(midi, "Galloping Pick Bass", 2, 34, 112, 64)
    tr_organ = setup_track(midi, "Hellfire Organ", 3, 18, 92, 92)
    tr_choir = setup_track(midi, "Abyssal Choir", 4, 52, 82, 32)
    tr_drums = setup_track(midi, "Thrash Metal Drums", 9, None, 116, 64)

    Em, C, D, Bm, F, Am, B7, Fm, Db, Eb = (
        (64, 67, 71), (60, 64, 67), (62, 66, 69), (59, 62, 66),
        (65, 69, 72), (69, 72, 76), (59, 63, 66, 69), (65, 68, 72),
        (61, 65, 68), (63, 67, 70),
    )
    prog_A = [(40, Em), (36, C), (38, D), (35, Bm), (40, Em), (41, F), (38, D), (35, B7)]
    prog_B = [(33, Am), (41, F), (38, D), (35, B7), (33, Am), (36, C), (35, Bm), (35, B7)]
    prog_D = [(41, Fm), (37, Db), (39, Eb), (36, C), (41, Fm), (37, Db), (39, Eb), (36, C)]

    thrash_4bar = [
        [(0.0, 64, 0.35, 112), (0.5, 67, 0.35, 108), (1.0, 64, 0.35, 112), (1.5, 69, 0.35, 110), (2.0, 71, 0.35, 114), (2.5, 70, 0.35, 112), (3.0, 67, 0.4, 110), (3.5, 66, 0.4, 106)],
        [(0.0, 64, 0.35, 112), (0.5, 67, 0.35, 108), (1.0, 72, 0.35, 114), (1.5, 71, 0.35, 110), (2.0, 74, 0.35, 116), (2.5, 72, 0.35, 112), (3.0, 71, 0.4, 110), (3.5, 69, 0.4, 108)],
        [(0.0, 71, 0.35, 114), (0.5, 74, 0.35, 110), (1.0, 76, 0.35, 116), (1.5, 74, 0.35, 112), (2.0, 72, 0.35, 110), (2.5, 71, 0.35, 108), (3.0, 69, 0.4, 108), (3.5, 67, 0.4, 106)],
        [(0.0, 66, 0.35, 110), (0.5, 67, 0.35, 110), (1.0, 69, 0.35, 112), (1.5, 71, 0.35, 114), (2.0, 74, 0.7, 116), (2.75, 72, 0.45, 112), (3.25, 71, 0.6, 110)],
    ]
    feint_4bar = [
        [(0.0, 76, 0.25, 116), (0.75, 74, 0.25, 112), (1.5, 72, 0.7, 114), (2.75, 71, 0.25, 112), (3.25, 72, 0.5, 110)],
        [(0.0, 74, 0.25, 114), (0.75, 72, 0.25, 110), (1.5, 69, 0.7, 112), (2.75, 71, 0.25, 110), (3.25, 67, 0.5, 108)],
    ]
    solo_licks = [
        [(i * 0.25, p, 0.22, 108) for i, p in enumerate([76, 74, 72, 71, 69, 71, 72, 74, 76, 79, 81, 79, 76, 74, 72, 71])],
        [(i * 0.25, p, 0.22, 110) for i, p in enumerate([79, 78, 76, 74, 72, 74, 76, 78, 79, 81, 83, 81, 79, 76, 74, 71])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "Ap"), (20, "B"), (28, "C"), (40, "D"), (52, "TURN")]
    total_bars = 64
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (40, Em) if b_sec < 3 else (35, B7)
            emit_bar_phrase(tr_gtr, 0, bar, thrash_4bar[b_sec], -12, 0.96, total_bars)
            emit_bass_bar(tr_bass, 2, bar, root, chord, "gallop", b_sec, 110)
            emit_drum_bar(tr_drums, bar, "fast_thrash", b_sec, is_sec, b_sec == 3, bar, 0.95)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, thrash_4bar[b_sec % 4], 0, 1.0, total_bars)
            tr_organ.add_chord(3, chord, bar * BAR_TICKS, BAR_TICKS - 40, 84)
        elif sec == "Ap":
            root, chord = prog_A[b_sec % 8]
            mel = thrash_4bar[b_sec % 4]
            emit_bar_phrase(tr_gtr, 0, bar, mel, 0, 1.04, total_bars)
            emit_bar_phrase(tr_gtr2, 1, bar, mel, 4 if b_sec % 2 == 0 else 7, 0.92, total_bars)
            emit_arp_bar(tr_organ, 3, bar, chord, "up", 8, 0, 82)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, feint_4bar[b_sec % 2], -12, 1.05, total_bars)
            emit_bar_phrase(tr_organ, 3, bar, feint_4bar[b_sec % 2], 0, 0.92, total_bars)
            tr_choir.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 60, 78)
        elif sec == "C":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_gtr2, 1, bar, solo_licks[b_sec % 2] if b_sec % 2 == 0 else thrash_4bar[b_sec % 4],
                            0 if b_sec < 6 else 12, 1.05, total_bars)
            tr_organ.add_chord(3, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            mel = thrash_4bar[b_sec % 4]
            emit_bar_phrase(tr_gtr, 0, bar, mel, 1, 1.08, total_bars)
            emit_bar_phrase(tr_gtr2, 1, bar, mel, 5, 0.96, total_bars)
            tr_choir.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, thrash_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_bar_phrase(tr_organ, 3, bar, feint_4bar[b_sec % 2], 0, 0.92, total_bars)

        emit_bass_bar(tr_bass, 2, bar, root, chord, "gallop", b_sec, 110)
        d_style = "heavy_stomp" if sec == "B" else "fast_thrash"
        emit_drum_bar(tr_drums, bar, d_style, b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.02)

    midi.save(filepath)


def compose_boss_toad(filepath: str):
    """48-Bar Boss Theme 3: Colossal Gigatoad (Seismic Arena March, 108 BPM)."""
    midi = MidiFile(tempo_bpm=108.0)
    tr_brass = setup_track(midi, "Colossal Brass Section", 0, 61, 108, 64)
    tr_tuba = setup_track(midi, "Gigatoad Tuba Bass", 1, 58, 114, 64)
    tr_strings = setup_track(midi, "Colosseum Strings", 2, 48, 94, 34)
    tr_timp = setup_track(midi, "Timpani Stomp", 3, 47, 110, 90)
    tr_wind = setup_track(midi, "Gladiator Woodwinds", 4, 71, 88, 94)
    tr_drums = setup_track(midi, "Colosseum Siege Kit", 9, None, 114, 64)

    Cm, Ab, Fm, G7, Eb, Bb = (
        (60, 63, 67), (56, 60, 63), (53, 56, 60), (55, 59, 62, 65),
        (63, 67, 70), (58, 62, 65),
    )
    prog_A = [(36, Cm), (32, Ab), (29, Fm), (31, G7), (36, Cm), (39, Eb), (32, Ab), (31, G7)]
    prog_B = [(39, Eb), (34, Bb), (36, Cm), (32, Ab), (29, Fm), (34, Bb), (31, G7), (36, Cm)]

    stomp_4bar = [
        [(0.0, 60, 0.85, 114), (1.0, 63, 0.45, 106), (1.5, 62, 0.42, 104), (2.0, 60, 0.85, 114), (3.0, 67, 0.85, 112)],
        [(0.0, 68, 0.85, 112), (1.0, 67, 0.45, 106), (1.5, 65, 0.42, 104), (2.0, 63, 0.85, 110), (3.0, 62, 0.85, 108)],
        [(0.0, 65, 0.85, 112), (1.0, 68, 0.45, 108), (1.5, 70, 0.42, 106), (2.0, 72, 0.85, 114), (3.0, 67, 0.85, 110)],
        [(0.0, 71, 0.45, 112), (0.5, 69, 0.45, 108), (1.0, 67, 0.85, 112), (2.0, 65, 0.85, 108), (3.0, 62, 0.85, 110)],
    ]
    fanfare_4bar = [
        [(0.0, 67, 0.7, 108), (0.75, 70, 0.45, 104), (1.25, 72, 0.7, 110), (2.0, 75, 0.85, 114), (3.0, 74, 0.85, 108)],
        [(0.0, 70, 0.7, 110), (0.75, 74, 0.45, 106), (1.25, 75, 0.7, 112), (2.0, 77, 0.85, 114), (3.0, 75, 0.85, 108)],
        [(0.0, 72, 0.7, 110), (0.75, 75, 0.45, 108), (1.25, 79, 0.7, 116), (2.0, 77, 0.85, 112), (3.0, 74, 0.85, 108)],
        [(0.0, 75, 0.45, 110), (0.5, 74, 0.45, 106), (1.0, 72, 0.85, 110), (2.0, 71, 0.85, 112), (3.0, 72, 0.85, 114)],
    ]
    woodwind_run = [
        [(i * 0.5, p, 0.42, 92) for i, p in enumerate([72, 74, 75, 77, 79, 80, 79, 77])],
        [(i * 0.5, p, 0.42, 94) for i, p in enumerate([75, 77, 79, 80, 82, 84, 80, 79])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (28, "D"), (40, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (36, Cm) if b_sec < 3 else (31, G7)
            for bt in (0, 2):
                tr_tuba.add_note(1, root, bar * BAR_TICKS + bt * TICKS_PER_BEAT, 400, 116)
                tr_timp.add_note(3, root + 12, bar * BAR_TICKS + bt * TICKS_PER_BEAT, 320, 112)
            if b_sec >= 2:
                emit_bar_phrase(tr_brass, 0, bar, stomp_4bar[b_sec - 2], 0, 0.96, total_bars)
            emit_drum_bar(tr_drums, bar, "heavy_stomp", b_sec, is_sec, b_sec == 3, bar, 0.96)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_brass, 0, bar, stomp_4bar[b_sec % 4], 0, 1.0, total_bars)
            emit_arp_bar(tr_strings, 2, bar, chord, "up", 8, 12, 78)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_brass, 0, bar, fanfare_4bar[b_sec % 4], 0, 1.04, total_bars)
            emit_bar_phrase(tr_wind, 4, bar, woodwind_run[b_sec % 2], 0, 0.9, total_bars)
            tr_strings.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 88)
        elif sec == "C":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_wind, 4, bar, woodwind_run[b_sec % 2], 0 if b_sec < 4 else 12, 0.98, total_bars)
            emit_bar_phrase(tr_brass, 0, bar, stomp_4bar[b_sec % 4], -12, 0.94, total_bars)
            emit_arp_bar(tr_strings, 2, bar, chord, "down", 16, 12, 74)
        elif sec == "D":
            root, chord = (prog_B if b_sec < 8 else prog_A)[b_sec % 8]
            mel = fanfare_4bar[b_sec % 4] if b_sec < 8 else stomp_4bar[b_sec % 4]
            emit_bar_phrase(tr_brass, 0, bar, mel, 0, 1.1, total_bars)
            emit_bar_phrase(tr_strings, 2, bar, woodwind_run[b_sec % 2], 0, 1.0, total_bars)
            emit_bar_phrase(tr_wind, 4, bar, woodwind_run[b_sec % 2], 12, 0.95, total_bars)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_brass, 0, bar, stomp_4bar[b_sec % 4], 0, 1.02, total_bars)
            tr_strings.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86)

        emit_bass_bar(tr_tuba, 1, bar, root, chord, "sustained_drive", b_sec, 112)
        for beat in range(4):
            if beat in (0, 2) or (sec == "D" and beat == 3):
                tr_timp.add_note(3, root + 12, bar * BAR_TICKS + beat * TICKS_PER_BEAT, 260, 108)
        emit_drum_bar(tr_drums, bar, "heavy_stomp", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.02)

    midi.save(filepath)


def compose_boss_falo_snowman(filepath: str):
    """52-Bar Boss Theme 4: Frosty Falo Snowman (Glacial Violin & Crystal Synth, 134 BPM)."""
    midi = MidiFile(tempo_bpm=134.0)
    tr_strings = setup_track(midi, "Frost Violin Lead", 0, 40, 106, 48)
    tr_synth = setup_track(midi, "Glacial Square Lead", 1, 80, 96, 80)
    tr_glock = setup_track(midi, "Ice Crystal Glockenspiel", 2, 9, 92, 96)
    tr_bass = setup_track(midi, "Subzero Bass", 3, 39, 108, 64)
    tr_brass = setup_track(midi, "Blizzard Brass", 4, 61, 88, 32)
    tr_drums = setup_track(midi, "Shatter Ice Percussion", 9, None, 108, 64)

    Gm, Cm, D7, Bb, Eb, F, Am, Dm, E7, C = (
        (67, 70, 74), (60, 63, 67), (62, 66, 69, 72), (58, 62, 65),
        (63, 67, 70), (65, 69, 72), (69, 72, 76), (62, 65, 69),
        (64, 68, 71, 74), (60, 64, 67),
    )
    prog_A = [(43, Gm), (36, Cm), (38, D7), (43, Gm), (39, Eb), (41, F), (34, Bb), (38, D7)]
    prog_B = [(34, Bb), (41, F), (43, Gm), (39, Eb), (36, Cm), (41, F), (34, Bb), (38, D7)]
    prog_D = [(45, Am), (38, Dm), (40, E7), (45, Am), (41, F), (43, Gm), (36, C), (40, E7)]

    frost_4bar_a = [
        [(0.0, 74, 0.45, 106), (0.5, 75, 0.45, 102), (1.0, 77, 0.45, 108), (1.5, 79, 0.45, 104), (2.0, 78, 0.85, 110), (3.0, 74, 0.85, 102)],
        [(0.0, 75, 0.45, 106), (0.5, 77, 0.45, 104), (1.0, 79, 0.45, 110), (1.5, 82, 0.45, 106), (2.0, 81, 0.85, 110), (3.0, 78, 0.85, 104)],
        [(0.0, 79, 0.45, 108), (0.5, 77, 0.45, 104), (1.0, 75, 0.45, 102), (1.5, 74, 0.45, 100), (2.0, 72, 0.85, 106), (3.0, 74, 0.85, 104)],
        [(0.0, 75, 0.45, 104), (0.5, 74, 0.45, 102), (1.0, 72, 0.45, 100), (1.5, 70, 0.45, 98), (2.0, 69, 0.85, 104), (3.0, 74, 0.85, 106)],
    ]
    frost_4bar_b = [
        [(0.0, 70, 0.45, 104), (0.5, 72, 0.45, 102), (1.0, 74, 0.85, 108), (2.0, 77, 0.45, 104), (2.5, 75, 0.45, 100), (3.0, 74, 0.85, 104)],
        [(0.0, 75, 0.45, 106), (0.5, 77, 0.45, 104), (1.0, 79, 0.85, 110), (2.0, 82, 0.45, 108), (2.5, 81, 0.45, 104), (3.0, 79, 0.85, 106)],
    ]
    blizzard_16ths = [
        [(i * 0.25, p, 0.22, 98 + (i % 4) * 5) for i, p in enumerate([79, 77, 75, 74, 72, 74, 75, 77, 79, 82, 81, 79, 77, 75, 74, 72])],
        [(i * 0.25, p, 0.22, 100 + (i % 4) * 5) for i, p in enumerate([82, 81, 79, 77, 75, 77, 79, 81, 82, 84, 86, 84, 82, 81, 79, 78])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (43, Gm) if b_sec < 3 else (38, D7)
            emit_arp_bar(tr_glock, 2, bar, chord, "up_down", 8, 12, 86)
            if b_sec >= 2:
                emit_bar_phrase(tr_strings, 0, bar, frost_4bar_a[b_sec - 2], 0, 0.94, total_bars)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "sustained_drive", b_sec, 100)
            emit_drum_bar(tr_drums, bar, "ice_march", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_strings, 0, bar, frost_4bar_a[b_sec % 4], 0, 1.0, total_bars)
            emit_arp_bar(tr_glock, 2, bar, chord, "up", 8, 12, 84)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_synth, 1, bar, frost_4bar_b[b_sec % 2], 0, 1.0, total_bars)
            emit_bar_phrase(tr_strings, 0, bar, frost_4bar_b[b_sec % 2], 12 if b_sec >= 4 else 0, 0.88, total_bars)
            emit_arp_bar(tr_glock, 2, bar, chord, "up_down", 8, 12, 88)
            tr_brass.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 82)
        elif sec == "C":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_synth if b_sec % 2 == 0 else tr_strings, 1 if b_sec % 2 == 0 else 0,
                            bar, blizzard_16ths[b_sec % 2], 0, 1.02, total_bars)
            emit_arp_bar(tr_glock, 2, bar, chord, "down", 16, 12, 86)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            emit_bar_phrase(tr_strings, 0, bar, frost_4bar_a[b_sec % 4] if b_sec % 2 == 0 else blizzard_16ths[b_sec % 2],
                            2, 1.06, total_bars)
            emit_bar_phrase(tr_synth, 1, bar, frost_4bar_b[b_sec % 2], 2, 0.96, total_bars)
            tr_brass.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 88)
            emit_arp_bar(tr_glock, 2, bar, chord, "up_down", 16, 12, 90)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_strings, 0, bar, frost_4bar_a[b_sec % 4], 0, 1.0, total_bars)
            emit_arp_bar(tr_glock, 2, bar, chord, "up", 8, 12, 86)

        emit_bass_bar(tr_bass, 3, bar, root, chord, "double_kick_metal" if sec == "D" else "mario_bounce", b_sec, 108)
        emit_drum_bar(tr_drums, bar, "double_kick_metal" if sec == "D" else "heroic_march",
                      b_sec, is_sec, (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_boss_shark(filepath: str):
    """52-Bar Boss Theme 5: Abyssal Demon Shark (F minor Leviathan Chase, 136 BPM)."""
    midi = MidiFile(tempo_bpm=136.0)
    tr_bass = setup_track(midi, "Abyssal Slap Shark Bass", 0, 36, 114, 64)
    tr_synth = setup_track(midi, "Trench Saw Lead", 1, 81, 104, 52)
    tr_strings = setup_track(midi, "Sunken Leviathan Strings", 2, 48, 96, 86)
    tr_crystal = setup_track(midi, "Deep Sonar Crystal", 3, 98, 86, 32)
    tr_brass = setup_track(midi, "Trench War Horns", 4, 61, 90, 96)
    tr_drums = setup_track(midi, "Depth Charge Breakbeat", 9, None, 112, 64)

    Fm, Db, Eb, C7, Ab, Bbm, Fsm, D, E, Cs7 = (
        (65, 68, 72), (61, 65, 68), (63, 67, 70), (60, 64, 67, 70),
        (68, 72, 75), (58, 61, 65), (66, 69, 73), (62, 66, 69),
        (64, 68, 71), (61, 65, 68, 71),
    )
    prog_A = [(41, Fm), (37, Db), (39, Eb), (36, C7), (41, Fm), (34, Bbm), (39, Eb), (36, C7)]
    prog_B = [(44, Ab), (39, Eb), (41, Fm), (37, Db), (34, Bbm), (39, Eb), (36, C7), (41, Fm)]
    prog_D = [(42, Fsm), (38, D), (40, E), (37, Cs7), (42, Fsm), (38, D), (40, E), (37, Cs7)]

    jaws_4bar = [
        [(0.0, 65, 0.45, 112), (0.5, 66, 0.45, 110), (1.0, 65, 0.45, 110), (1.5, 66, 0.45, 108), (2.0, 65, 0.4, 112), (2.5, 68, 0.4, 110), (3.0, 72, 0.85, 114)],
        [(0.0, 73, 0.45, 110), (0.5, 72, 0.45, 108), (1.0, 70, 0.45, 108), (1.5, 68, 0.45, 106), (2.0, 67, 0.85, 110), (3.0, 64, 0.85, 108)],
        [(0.0, 65, 0.45, 112), (0.5, 68, 0.45, 110), (1.0, 72, 0.45, 114), (1.5, 73, 0.45, 112), (2.0, 75, 0.85, 116), (3.0, 72, 0.85, 110)],
        [(0.0, 70, 0.45, 108), (0.5, 68, 0.45, 106), (1.0, 67, 0.85, 110), (2.0, 64, 0.85, 108), (3.0, 65, 0.85, 112)],
    ]
    whirlpool_2bar = [
        [(0.0, 75, 0.7, 106), (0.75, 72, 0.45, 102), (1.25, 73, 0.65, 104), (2.0, 70, 0.85, 104), (3.0, 72, 0.85, 108)],
        [(0.0, 77, 0.7, 108), (0.75, 75, 0.45, 104), (1.25, 73, 0.65, 106), (2.0, 72, 0.85, 106), (3.0, 75, 0.85, 110)],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (41, Fm) if b_sec < 3 else (36, C7)
            emit_bar_phrase(tr_strings, 2, bar, jaws_4bar[b_sec], -12, 0.94, total_bars)
            emit_arp_bar(tr_crystal, 3, bar, chord, "up", 4, 12, 78)
            emit_bass_bar(tr_bass, 0, bar, root, chord, "sonar_pulse", b_sec, 110)
            emit_drum_bar(tr_drums, bar, "sonar_pulse", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_synth, 1, bar, jaws_4bar[b_sec % 4], 0, 1.0, total_bars)
            emit_arp_bar(tr_crystal, 3, bar, chord, "up_down", 8, 12, 78)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_strings, 2, bar, whirlpool_2bar[b_sec % 2], 0, 1.04, total_bars)
            emit_bar_phrase(tr_brass, 4, bar, whirlpool_2bar[b_sec % 2], -12, 0.92, total_bars)
            emit_arp_bar(tr_crystal, 3, bar, chord, "up", 16, 12, 82)
        elif sec == "C":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_synth, 1, bar, jaws_4bar[b_sec % 4] if b_sec % 2 == 0 else whirlpool_2bar[b_sec % 2], 0, 0.96, total_bars)
            tr_strings.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 84)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            emit_bar_phrase(tr_synth, 1, bar, jaws_4bar[b_sec % 4], 1, 1.08, total_bars)
            emit_bar_phrase(tr_strings, 2, bar, whirlpool_2bar[b_sec % 2], 1, 1.0, total_bars)
            tr_brass.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 90)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_synth, 1, bar, jaws_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_arp_bar(tr_crystal, 3, bar, chord, "down", 8, 12, 80)

        emit_bass_bar(tr_bass, 0, bar, root, chord, "double_kick_metal" if sec == "D" else "slap_funk", b_sec, 112)
        emit_drum_bar(tr_drums, bar, "deep_breakbeat", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.02)

    midi.save(filepath)


def compose_glacial_hot_springs(filepath: str):
    """48-Bar Ethereal Aquatic Ambience: Glacial Hot Springs (86 BPM, F Major)."""
    midi = MidiFile(tempo_bpm=86.0)
    tr_pad = setup_track(midi, "Crystal Aura Pad", 0, 98, 92, 34)
    tr_flute = setup_track(midi, "Geothermal Pan Flute", 1, 75, 102, 64)
    tr_ep = setup_track(midi, "Rhodes Chill Chords", 2, 4, 88, 86)
    tr_bass = setup_track(midi, "Fretless Warm Bass", 3, 35, 100, 64)
    tr_strings = setup_track(midi, "Glacial Warm Strings", 4, 49, 86, 46)
    tr_drums = setup_track(midi, "Soft Glacial Brush", 9, None, 72, 64)

    Fmaj7, Am7, Bbmaj7, Dm7, Gm7, C9, Edim7, A7 = (
        (65, 69, 72, 76), (69, 72, 76, 79), (58, 62, 65, 69), (62, 65, 69, 72),
        (67, 70, 74, 77), (60, 64, 67, 70, 74), (64, 67, 70, 73), (57, 61, 64, 67),
    )
    prog_A = [(41, Fmaj7), (33, Am7), (34, Bbmaj7), (36, C9), (38, Dm7), (33, Am7), (31, Gm7), (36, C9)]
    prog_B = [(34, Bbmaj7), (33, Am7), (38, Dm7), (31, Gm7), (34, Bbmaj7), (40, Edim7), (33, A7), (38, Dm7)]

    mel_4bar = [
        [(0.0, 72, 1.4, 94), (1.5, 76, 0.9, 98), (2.5, 77, 0.7, 100), (3.25, 76, 0.65, 92)],
        [(0.0, 74, 1.2, 92), (1.5, 72, 0.9, 90), (2.5, 69, 1.35, 96)],
        [(0.0, 77, 1.1, 96), (1.25, 79, 0.85, 98), (2.25, 81, 0.85, 100), (3.25, 77, 0.65, 94)],
        [(0.0, 76, 0.9, 94), (1.0, 74, 0.9, 92), (2.0, 72, 1.8, 96)],
    ]
    flute_c = [
        [(0.0, 79, 0.9, 96), (1.0, 77, 0.9, 94), (2.0, 76, 0.9, 92), (3.0, 74, 0.85, 90)],
        [(0.0, 76, 0.9, 96), (1.0, 74, 0.9, 94), (2.0, 72, 0.9, 92), (3.0, 69, 0.85, 92)],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "Ap"), (20, "B"), (28, "C"), (36, "D"), (44, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = prog_A[b_sec]
            emit_arp_bar(tr_pad, 0, bar, chord, "up_down", 8, 12, 76)
            tr_ep.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 78)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "sonar_pulse", b_sec, 92)
            emit_drum_bar(tr_drums, bar, "soft_ambient", b_sec, is_sec, False, bar, 0.85)
            continue

        prog = prog_B if sec in ("B", "C") else prog_A
        root, chord = prog[b_sec % 8]
        tr_ep.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 82)
        emit_arp_bar(tr_pad, 0, bar, chord, "up_down" if bar % 2 == 0 else "down", 8, 12, 78)
        if sec in ("Ap", "B", "C", "D", "TURN"):
            tr_strings.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 50, 86 if sec == "D" else 76)

        if sec in ("A", "Ap"):
            emit_bar_phrase(tr_flute, 1, bar, mel_4bar[b_sec % 4], 0, 1.0, total_bars)
        elif sec in ("B", "C"):
            emit_bar_phrase(tr_flute, 1, bar, flute_c[b_sec % 2] if b_sec % 2 == 0 else mel_4bar[b_sec % 4], 0, 1.0, total_bars)
        else:
            emit_bar_phrase(tr_flute, 1, bar, mel_4bar[b_sec % 4], 12 if (sec == "D" and b_sec >= 4) else 0, 1.04, total_bars)

        emit_bass_bar(tr_bass, 3, bar, root, chord, "walking" if sec in ("B", "C") else "sonar_pulse", b_sec, 98)
        emit_drum_bar(tr_drums, bar, "soft_ambient", b_sec, is_sec,
                      (b_sec % 8 == 7) or bar == total_bars - 1, bar, 0.9)

    midi.save(filepath)


def compose_title_theme(filepath: str):
    """52-Bar Heroic Adventure Title Theme (124 BPM, G Major -> Bb Bridge -> G Climax)."""
    midi = MidiFile(tempo_bpm=124.0)
    tr_brass = setup_track(midi, "Heroic Adventure Brass", 0, 61, 108, 64)
    tr_lead = setup_track(midi, "16-Bit Square Hero Lead", 1, 80, 102, 76)
    tr_strings = setup_track(midi, "Grand Canopy Strings", 2, 48, 92, 34)
    tr_bass = setup_track(midi, "Heroic Walking Bass", 3, 33, 110, 64)
    tr_flute = setup_track(midi, "Adventure Counter Flute", 4, 73, 90, 92)
    tr_drums = setup_track(midi, "Adventure March Drums", 9, None, 110, 64)

    G, D, Em, Bm, C, Am, Bb, F, Gm, Dm, Eb = (
        (67, 71, 74), (62, 66, 69), (64, 67, 71), (59, 62, 66),
        (60, 64, 67), (69, 72, 76), (58, 62, 65), (65, 69, 72),
        (67, 70, 74), (62, 65, 69), (63, 67, 70),
    )
    prog_A = [(43, G), (38, D), (40, Em), (35, Bm), (36, C), (43, G), (33, Am), (38, D)]
    prog_B = [(40, Em), (36, C), (38, D), (43, G), (33, Am), (35, Bm), (36, C), (38, D)]
    prog_C = [(34, Bb), (41, F), (43, Gm), (38, Dm), (39, Eb), (34, Bb), (36, C), (38, D)]

    anthem_4bar = [
        [(0.0, 74, 0.85, 110), (1.0, 79, 0.85, 114), (2.0, 78, 0.45, 106), (2.5, 79, 0.45, 108), (3.0, 81, 0.85, 116)],
        [(0.0, 83, 0.85, 112), (1.0, 79, 0.45, 104), (1.5, 78, 0.45, 102), (2.0, 76, 0.85, 104), (3.0, 74, 0.85, 108)],
        [(0.0, 76, 0.7, 108), (0.75, 79, 0.45, 106), (1.25, 83, 0.7, 114), (2.0, 84, 0.85, 116), (3.0, 83, 0.85, 110)],
        [(0.0, 81, 0.45, 108), (0.5, 79, 0.45, 106), (1.0, 78, 0.85, 108), (2.0, 76, 0.85, 106), (3.0, 74, 0.85, 110)],
    ]
    flute_counter = [
        [(i * 0.5, p, 0.42, 90) for i, p in enumerate([79, 81, 83, 81, 79, 78, 76, 74])],
        [(i * 0.5, p, 0.42, 92) for i, p in enumerate([83, 84, 86, 84, 83, 81, 79, 78])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = prog_A[b_sec % 4]
            tr_brass.add_chord(0, chord, bar * BAR_TICKS, BAR_TICKS - 40, 96)
            emit_arp_bar(tr_strings, 2, bar, chord, "up", 8, 12, 82)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce", b_sec, 104)
            emit_drum_bar(tr_drums, bar, "heroic_march", b_sec, is_sec, b_sec == 3, bar, 0.95)
            continue

        if sec == "A":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_lead, 1, bar, anthem_4bar[b_sec % 4], 0, 1.0, total_bars)
            tr_brass.add_chord(0, chord, bar * BAR_TICKS, 400, 96)
        elif sec == "B":
            root, chord = prog_B[b_sec % 8]
            emit_bar_phrase(tr_flute, 4, bar, flute_counter[b_sec % 2], 0, 1.0, total_bars)
            emit_bar_phrase(tr_lead, 1, bar, anthem_4bar[b_sec % 4], 0, 0.94, total_bars)
            emit_arp_bar(tr_strings, 2, bar, chord, "up_down", 8, 12, 84)
        elif sec == "C":
            idx = b_sec % 8
            root, chord = prog_C[idx]
            emit_bar_phrase(tr_brass, 0, bar, anthem_4bar[b_sec % 4], 3 if idx < 6 else 0, 1.04, total_bars)
            emit_arp_bar(tr_strings, 2, bar, chord, "up", 16, 12, 84)
        elif sec == "D":
            root, chord = prog_A[b_sec % 8]
            mel = anthem_4bar[b_sec % 4]
            emit_bar_phrase(tr_brass, 0, bar, mel, 0, 1.08, total_bars)
            emit_bar_phrase(tr_lead, 1, bar, mel, 12, 0.98, total_bars)
            emit_bar_phrase(tr_flute, 4, bar, flute_counter[b_sec % 2], 0, 0.92, total_bars)
            tr_strings.add_chord(2, chord, bar * BAR_TICKS, BAR_TICKS - 40, 92)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_brass, 0, bar, anthem_4bar[b_sec % 4], 0, 1.02, total_bars)
            emit_arp_bar(tr_strings, 2, bar, chord, "up", 8, 12, 86)

        emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce" if sec != "D" else "walking", b_sec, 110)
        emit_drum_bar(tr_drums, bar, "heroic_march", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_volcanic_magma(filepath: str):
    """52-Bar Fiery Volcanic Magma Cavern (128 BPM, D minor -> E minor Climax)."""
    midi = MidiFile(tempo_bpm=128.0)
    tr_gtr = setup_track(midi, "Magma Overdrive Guitar", 0, 29, 108, 44)
    tr_brass = setup_track(midi, "Volcanic Synth Brass", 1, 62, 98, 86)
    tr_bass = setup_track(midi, "Caldera Sub Bass", 2, 38, 112, 64)
    tr_tom = setup_track(midi, "Magma Kettle Drums", 3, 117, 94, 96)
    tr_pad = setup_track(midi, "Ember Choir Pad", 4, 91, 80, 32)
    tr_drums = setup_track(midi, "Industrial Lava Kit", 9, None, 112, 64)

    Dm, Bb, Gm, A7, C, F, Em, Am, B7 = (
        (62, 65, 69), (58, 62, 65), (67, 70, 74), (57, 61, 64, 67),
        (60, 64, 67), (65, 69, 72), (64, 67, 71), (69, 72, 76), (59, 63, 66, 69),
    )
    prog_A = [(38, Dm), (34, Bb), (31, Gm), (33, A7), (38, Dm), (36, C), (34, Bb), (33, A7)]
    prog_B = [(31, Gm), (38, Dm), (34, Bb), (36, C), (41, F), (38, Dm), (31, Gm), (33, A7)]
    prog_D = [(40, Em), (36, C), (33, Am), (35, B7), (40, Em), (36, C), (33, Am), (35, B7)]

    lava_4bar = [
        [(0.0, 62, 0.42, 110), (0.5, 62, 0.42, 104), (1.0, 65, 0.42, 108), (1.5, 69, 0.42, 110), (2.0, 68, 0.85, 112), (3.0, 65, 0.85, 106)],
        [(0.0, 67, 0.42, 110), (0.5, 70, 0.42, 108), (1.0, 69, 0.42, 106), (1.5, 67, 0.42, 104), (2.0, 65, 0.85, 108), (3.0, 64, 0.85, 106)],
        [(0.0, 65, 0.42, 108), (0.5, 69, 0.42, 110), (1.0, 72, 0.42, 112), (1.5, 70, 0.42, 108), (2.0, 69, 0.85, 110), (3.0, 67, 0.85, 106)],
        [(0.0, 69, 0.42, 110), (0.5, 67, 0.42, 106), (1.0, 65, 0.42, 104), (1.5, 64, 0.42, 104), (2.0, 61, 0.85, 108), (3.0, 62, 0.85, 110)],
    ]
    ember_2bar = [
        [(i * 0.5, p, 0.42, 104) for i, p in enumerate([74, 72, 70, 69, 67, 69, 70, 74])],
        [(i * 0.5, p, 0.42, 106) for i, p in enumerate([77, 76, 74, 72, 70, 69, 67, 69])],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (38, Dm) if b_sec < 3 else (33, A7)
            emit_bass_bar(tr_bass, 2, bar, root, chord, "gallop", b_sec, 106)
            tr_tom.add_note(3, 50 - b_sec * 2, bar * BAR_TICKS, 400, 96)
            tr_tom.add_note(3, 45, bar * BAR_TICKS + 960, 400, 92)
            emit_drum_bar(tr_drums, bar, "heavy_stomp", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        if sec in ("A", "B"):
            root, chord = (prog_A if sec == "A" else prog_B)[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, lava_4bar[b_sec % 4] if b_sec % 2 == 0 else ember_2bar[b_sec % 2], 0, 1.0, total_bars)
            tr_brass.add_chord(1, chord, bar * BAR_TICKS, 400, 92)
        elif sec == "C":
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_brass, 1, bar, ember_2bar[b_sec % 2], 0, 1.02, total_bars)
            tr_pad.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 82)
            emit_arp_bar(tr_gtr, 0, bar, chord, "up", 8, -12, 86)
        elif sec == "D":
            root, chord = prog_D[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, lava_4bar[b_sec % 4], 2, 1.08, total_bars)
            emit_bar_phrase(tr_brass, 1, bar, ember_2bar[b_sec % 2], 2, 1.0, total_bars)
            tr_pad.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86)
        else:
            root, chord = prog_A[b_sec % 8]
            emit_bar_phrase(tr_gtr, 0, bar, lava_4bar[b_sec % 4], 0, 1.02, total_bars)

        tr_tom.add_note(3, root + 12, bar * BAR_TICKS + 480, 300, 90)
        tr_tom.add_note(3, root + 19, bar * BAR_TICKS + 1440, 300, 88)
        emit_bass_bar(tr_bass, 2, bar, root, chord, "gallop" if sec == "D" else "double_kick_metal", b_sec, 110)
        emit_drum_bar(tr_drums, bar, "rock_drive", b_sec, is_sec, (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_sunken_grotto(filepath: str):
    """48-Bar Deep Underwater Sunken Grotto (98 BPM, A minor Submarine Mystique)."""
    midi = MidiFile(tempo_bpm=98.0)
    tr_crystal = setup_track(midi, "Deep Sonar Crystal", 0, 98, 92, 34)
    tr_flute = setup_track(midi, "Sunken Reef Flute", 1, 75, 102, 72)
    tr_bass = setup_track(midi, "Fretless Tide Bass", 2, 35, 110, 64)
    tr_marimba = setup_track(midi, "Kelp Bed Marimba", 3, 12, 88, 90)
    tr_pad = setup_track(midi, "Abyssal Swell Choir", 4, 89, 80, 48)
    tr_drums = setup_track(midi, "Sonar Bubble Groove", 9, None, 82, 64)

    Am9, Fmaj7, Dm9, E7, Cmaj7, G6 = (
        (69, 72, 76, 83), (65, 69, 72, 76), (62, 65, 69, 76),
        (64, 68, 71, 74), (60, 64, 67, 71), (67, 71, 74, 76),
    )
    prog_A = [(45, Am9), (41, Fmaj7), (38, Dm9), (40, E7), (45, Am9), (43, G6), (41, Fmaj7), (40, E7)]
    prog_B = [(36, Cmaj7), (43, G6), (45, Am9), (40, E7), (41, Fmaj7), (38, Dm9), (40, E7), (45, Am9)]

    sonar_4bar = [
        [(0.0, 76, 0.9, 98), (1.0, 79, 0.45, 96), (1.5, 81, 0.85, 102), (2.5, 79, 0.45, 94), (3.0, 76, 0.85, 96)],
        [(0.0, 77, 0.9, 98), (1.0, 76, 0.45, 94), (1.5, 74, 0.85, 96), (2.5, 72, 0.45, 92), (3.0, 71, 0.85, 96)],
        [(0.0, 74, 0.9, 96), (1.0, 76, 0.45, 98), (1.5, 79, 0.85, 102), (2.5, 81, 0.45, 100), (3.0, 83, 0.85, 104)],
        [(0.0, 81, 0.45, 100), (0.5, 79, 0.45, 96), (1.0, 76, 0.85, 98), (2.0, 74, 0.85, 96), (3.0, 76, 0.85, 100)],
    ]
    trench_solo = [(i * 0.5, p, 0.42, 94) for i, p in enumerate([81, 79, 76, 74, 72, 74, 76, 79])]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (28, "D"), (40, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        prog = prog_B if sec in ("B", "C") else prog_A
        root, chord = prog[b_sec % 8]

        emit_arp_bar(tr_crystal, 0, bar, chord, "up_down", 8, 0, 76)
        emit_arp_bar(tr_marimba, 3, bar, chord, "down", 8, 12, 68 if sec == "INTRO" else 78)
        if sec not in ("INTRO", "A"):
            tr_pad.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86 if sec == "D" else 76)
        if sec != "INTRO":
            emit_bar_phrase(tr_flute, 1, bar,
                            trench_solo if (sec == "C" and b_sec % 2 == 0) else sonar_4bar[b_sec % 4],
                            12 if (sec == "D" and b_sec % 4 == 2) else 0, 1.0, total_bars)

        emit_bass_bar(tr_bass, 2, bar, root, chord, "slap_funk" if sec in ("B", "C") else "sonar_pulse", b_sec, 108)
        emit_drum_bar(tr_drums, bar, "sonar_pulse", b_sec, is_sec,
                      (b_sec % 8 == 7) or bar == total_bars - 1, bar, 0.94)

    midi.save(filepath)


def compose_temple_ruins(filepath: str):
    """52-Bar Ancient Mayan Temple Ruins (118 BPM, E Dorian Pan Flute & Marimba)."""
    midi = MidiFile(tempo_bpm=118.0)
    tr_marimba = setup_track(midi, "Ancient Stone Marimba", 0, 12, 102, 42)
    tr_flute = setup_track(midi, "Temple Pan Flute", 1, 75, 106, 68)
    tr_bass = setup_track(midi, "Temple Acoustic Bass", 2, 32, 108, 64)
    tr_pizz = setup_track(midi, "Pizzicato Echo", 3, 45, 92, 90)
    tr_kalimba = setup_track(midi, "Shrine Kalimba", 4, 108, 86, 28)
    tr_drums = setup_track(midi, "Tribal Shrine Drums", 9, None, 98, 64)

    Em, G, A, D, C, Bm, Fsm = (
        (64, 67, 71), (67, 71, 74), (69, 73, 76), (62, 66, 69),
        (60, 64, 67), (59, 62, 66), (66, 69, 73),
    )
    prog_A = [(40, Em), (43, G), (33, A), (40, Em), (40, Em), (38, D), (35, Bm), (40, Em)]
    prog_B = [(36, C), (38, D), (40, Em), (35, Bm), (36, C), (33, A), (35, Bm), (40, Em)]
    prog_D = [(42, Fsm), (33, A), (35, Bm), (42, Fsm), (38, D), (33, A), (35, Bm), (40, Em)]

    pan_4bar = [
        [(0.0, 76, 0.7, 104), (0.75, 79, 0.45, 100), (1.25, 81, 0.7, 106), (2.0, 78, 0.85, 100), (3.0, 76, 0.85, 102)],
        [(0.0, 79, 0.7, 106), (0.75, 81, 0.45, 104), (1.25, 83, 0.7, 108), (2.0, 81, 0.85, 104), (3.0, 79, 0.85, 102)],
        [(0.0, 78, 0.7, 104), (0.75, 76, 0.45, 100), (1.25, 74, 0.7, 102), (2.0, 76, 0.85, 104), (3.0, 78, 0.85, 102)],
        [(0.0, 79, 0.45, 104), (0.5, 78, 0.45, 102), (1.0, 76, 0.85, 106), (2.0, 74, 0.85, 100), (3.0, 76, 0.85, 104)],
    ]
    shrine_solo = [(i * 0.5, p, 0.42, 102) for i, p in enumerate([76, 78, 79, 81, 83, 81, 79, 78])]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (40, Em)
            emit_arp_bar(tr_marimba, 0, bar, chord, "up_down", 8, 0, 86)
            emit_arp_bar(tr_kalimba, 4, bar, chord, "up", 8, 12, 78)
            emit_bass_bar(tr_bass, 2, bar, root, chord, "sonar_pulse", b_sec, 100)
            emit_drum_bar(tr_drums, bar, "tribal_percussion", b_sec, is_sec, False, bar, 0.9)
            continue

        prog = prog_B if sec == "B" else (prog_D if sec == "D" else prog_A)
        idx = b_sec % 8
        root, chord = prog[idx]
        tr_shift = 2 if (sec == "D" and idx < 6) else 0
        emit_arp_bar(tr_marimba, 0, bar, chord, "up_down", 8, 0, 92)
        emit_arp_bar(tr_pizz, 3, bar, chord, "down", 8, 12, 82)
        emit_arp_bar(tr_kalimba, 4, bar, chord, "up", 16 if sec == "D" else 8, 12, 76)
        emit_bar_phrase(tr_flute, 1, bar,
                        shrine_solo if (sec == "C" and b_sec % 2 == 1) else pan_4bar[b_sec % 4],
                        tr_shift, 1.0, total_bars)
        emit_bass_bar(tr_bass, 2, bar, root, chord, "mario_bounce" if sec == "D" else "walking", b_sec, 106)
        emit_drum_bar(tr_drums, bar, "tribal_percussion", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_bioluminescent_cavern(filepath: str):
    """48-Bar Crystal Bioluminescent Cavern (104 BPM, B minor -> D Major Shimmer)."""
    midi = MidiFile(tempo_bpm=104.0)
    tr_celesta = setup_track(midi, "Bioluminescent Celesta", 0, 8, 98, 38)
    tr_bell = setup_track(midi, "Spore Bell Lead", 1, 9, 104, 68)
    tr_harp = setup_track(midi, "Crystal Harp Arpeggios", 2, 46, 94, 88)
    tr_bass = setup_track(midi, "Subterranean Warm Bass", 3, 33, 106, 64)
    tr_pad = setup_track(midi, "Glowing Spore Choir", 4, 88, 84, 50)
    tr_drums = setup_track(midi, "Cave Crystal Pulses", 9, None, 86, 64)

    Bm, Gmaj7, Em7, Fsm7, D, A = (
        (59, 62, 66), (67, 71, 74, 78), (64, 67, 71, 74), (66, 70, 73, 76),
        (62, 66, 69), (69, 73, 76),
    )
    prog_A = [(35, Bm), (43, Gmaj7), (40, Em7), (42, Fsm7), (35, Bm), (45, A), (43, Gmaj7), (42, Fsm7)]
    prog_B = [(38, D), (45, A), (35, Bm), (42, Fsm7), (43, Gmaj7), (38, D), (40, Em7), (45, A)]

    spore_4bar = [
        [(0.0, 71, 0.9, 98), (1.0, 74, 0.45, 96), (1.5, 78, 0.85, 102), (2.5, 76, 0.45, 94), (3.0, 74, 0.85, 98)],
        [(0.0, 73, 0.9, 98), (1.0, 74, 0.45, 96), (1.5, 76, 0.85, 100), (2.5, 74, 0.45, 94), (3.0, 73, 0.85, 98)],
        [(0.0, 74, 0.9, 100), (1.0, 78, 0.45, 98), (1.5, 81, 0.85, 104), (2.5, 79, 0.45, 96), (3.0, 78, 0.85, 100)],
        [(0.0, 76, 0.45, 98), (0.5, 74, 0.45, 96), (1.0, 73, 0.85, 98), (2.0, 71, 0.85, 96), (3.0, 74, 0.85, 100)],
    ]
    lake_solo = [(i * 0.5, p, 0.42, 96) for i, p in enumerate([74, 78, 81, 83, 81, 78, 76, 74])]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (28, "D"), (40, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        prog = prog_B if sec in ("B", "C") else prog_A
        root, chord = prog[b_sec % 8]

        emit_arp_bar(tr_harp, 2, bar, chord, "up_down", 8, 12, 82)
        emit_arp_bar(tr_celesta, 0, bar, chord, "up", 16 if sec in ("C", "D") else 8, 12, 80)
        if sec not in ("INTRO", "A"):
            tr_pad.add_chord(4, chord, bar * BAR_TICKS, BAR_TICKS - 40, 78)
        if sec != "INTRO":
            emit_bar_phrase(tr_bell, 1, bar,
                            lake_solo if (sec == "C" and b_sec % 2 == 0) else spore_4bar[b_sec % 4],
                            12 if (sec == "D" and b_sec % 4 == 2) else 0, 1.0, total_bars)
        emit_bass_bar(tr_bass, 3, bar, root, chord, "walking" if sec in ("B", "C") else "sonar_pulse", b_sec, 102)
        emit_drum_bar(tr_drums, bar, "soft_ambient", b_sec, is_sec,
                      (b_sec % 8 == 7) or bar == total_bars - 1, bar, 0.94)

    midi.save(filepath)


def compose_sanctum_mystery(filepath: str):
    """48-Bar Dramatic Sanctum Sanctuary (94 BPM, G# minor Organ & Choir)."""
    midi = MidiFile(tempo_bpm=94.0)
    tr_organ = setup_track(midi, "Cathedral Church Organ", 0, 19, 102, 54)
    tr_choir = setup_track(midi, "Sanctum Choir Voices", 1, 52, 96, 76)
    tr_harpsi = setup_track(midi, "Sacred Harpsichord", 2, 6, 88, 32)
    tr_bass = setup_track(midi, "Pedal Organ Sub Bass", 3, 33, 110, 64)
    tr_bell = setup_track(midi, "Tubular Relic Bells", 4, 14, 92, 92)
    tr_drums = setup_track(midi, "Cathedral Timpani & Kit", 9, None, 98, 64)

    Gsm, E, Csm, Ds7, B, Fs, Am, F, Dm, E7 = (
        (68, 71, 75), (64, 68, 71), (61, 64, 68), (63, 67, 70, 73),
        (59, 63, 66), (66, 70, 73), (69, 72, 76), (65, 69, 72),
        (62, 65, 69), (64, 68, 71, 74),
    )
    prog_A = [(44, Gsm), (40, E), (37, Csm), (39, Ds7), (44, Gsm), (42, Fs), (40, E), (39, Ds7)]
    prog_B = [(35, B), (42, Fs), (44, Gsm), (37, Csm), (40, E), (35, B), (37, Csm), (39, Ds7)]
    prog_D = [(45, Am), (41, F), (38, Dm), (40, E7), (45, Am), (38, Dm), (40, E7), (39, Ds7)]

    fugue_4bar = [
        [(0.0, 75, 0.9, 104), (1.0, 76, 0.45, 98), (1.5, 78, 0.45, 100), (2.0, 79, 0.85, 106), (3.0, 75, 0.85, 100)],
        [(0.0, 76, 0.9, 102), (1.0, 75, 0.45, 98), (1.5, 73, 0.45, 96), (2.0, 71, 0.85, 102), (3.0, 70, 0.85, 100)],
        [(0.0, 73, 0.9, 104), (1.0, 75, 0.45, 100), (1.5, 76, 0.45, 102), (2.0, 78, 0.85, 106), (3.0, 80, 0.85, 104)],
        [(0.0, 78, 0.45, 104), (0.5, 76, 0.45, 100), (1.0, 75, 0.85, 102), (2.0, 73, 0.85, 100), (3.0, 75, 0.85, 104)],
    ]
    toccata_16ths = [(i * 0.25, p, 0.22, 90 + (i % 4) * 5) for i, p in enumerate(
        [75, 73, 75, 71, 75, 70, 75, 68, 75, 76, 78, 76, 75, 73, 71, 70])]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (42, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = prog_A[b_sec]
            tr_organ.add_chord(0, chord, bar * BAR_TICKS, BAR_TICKS - 40, 96)
            tr_bell.add_note(4, chord[2] + 12, bar * BAR_TICKS, 800, 92)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "sustained_drive", b_sec, 102)
            emit_drum_bar(tr_drums, bar, "castle_march", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        prog = prog_B if sec == "B" else (prog_D if sec == "D" else prog_A)
        idx = b_sec % 8
        root, chord = prog[idx]
        tr_organ.add_chord(0, chord, bar * BAR_TICKS, BAR_TICKS - 40, 94)
        emit_arp_bar(tr_harpsi, 2, bar, chord, "up_down", 16 if sec in ("C", "D") else 8, 12, 82)
        emit_bar_phrase(tr_choir, 1, bar,
                        toccata_16ths if (sec == "C" and b_sec % 2 == 1) else fugue_4bar[b_sec % 4],
                        1 if (sec == "D" and idx < 7) else 0, 1.0, total_bars)
        if b_sec % 2 == 0:
            tr_bell.add_note(4, chord[0] + 12, bar * BAR_TICKS, 720, 90)
        emit_bass_bar(tr_bass, 3, bar, root, chord, "sustained_drive", b_sec, 108)
        emit_drum_bar(tr_drums, bar, "castle_march", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 0.98)

    midi.save(filepath)


def compose_hound_palace(filepath: str):
    """52-Bar Hound Crimson Castle Sanctuary (114 BPM, D minor Dark Baroque)."""
    midi = MidiFile(tempo_bpm=114.0)
    tr_harpsi = setup_track(midi, "Palace Harpsichord", 0, 6, 102, 42)
    tr_strings = setup_track(midi, "Crimson Castle Strings", 1, 48, 98, 82)
    tr_bass = setup_track(midi, "Fortress Sub Bass", 2, 38, 110, 64)
    tr_brass = setup_track(midi, "Fortress Horns", 3, 61, 92, 34)
    tr_bell = setup_track(midi, "Watchtower Bells", 4, 14, 86, 94)
    tr_drums = setup_track(midi, "Castle March Drums", 9, None, 106, 64)

    Dm, Gm, C, F, Bb, A7, Ebm, Bb7 = (
        (62, 65, 69), (67, 70, 74), (60, 64, 67), (65, 69, 72),
        (58, 62, 65), (57, 61, 64, 67), (63, 66, 70), (58, 62, 65, 68),
    )
    prog_A = [(38, Dm), (31, Gm), (36, C), (41, F), (34, Bb), (31, Gm), (33, A7), (38, Dm)]
    prog_B = [(41, F), (36, C), (38, Dm), (33, A7), (34, Bb), (41, F), (31, Gm), (33, A7)]
    prog_D = [(39, Ebm), (34, Bb7), (39, Ebm), (34, Bb7), (38, Dm), (31, Gm), (33, A7), (38, Dm)]

    castle_4bar = [
        [(0.0, 69, 0.45, 104), (0.5, 70, 0.45, 100), (1.0, 74, 0.85, 108), (2.0, 73, 0.45, 104), (2.5, 74, 0.45, 102), (3.0, 69, 0.85, 106)],
        [(0.0, 70, 0.45, 104), (0.5, 72, 0.45, 102), (1.0, 74, 0.85, 108), (2.0, 72, 0.45, 102), (2.5, 70, 0.45, 100), (3.0, 69, 0.85, 104)],
        [(0.0, 74, 0.45, 108), (0.5, 76, 0.45, 106), (1.0, 77, 0.85, 112), (2.0, 76, 0.45, 106), (2.5, 74, 0.45, 104), (3.0, 72, 0.85, 106)],
        [(0.0, 70, 0.45, 106), (0.5, 69, 0.45, 102), (1.0, 67, 0.85, 104), (2.0, 69, 0.85, 106), (3.0, 62, 0.85, 108)],
    ]
    duel_runs = [(i * 0.25, p, 0.22, 94) for i, p in enumerate(
        [74, 72, 70, 69, 67, 69, 70, 72, 74, 76, 77, 76, 74, 72, 70, 69])]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (44, "TURN")]
    total_bars = 52
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (38, Dm) if b_sec < 3 else (33, A7)
            emit_arp_bar(tr_harpsi, 0, bar, chord, "up_down", 16, 0, 92)
            tr_strings.add_chord(1, chord, bar * BAR_TICKS, BAR_TICKS - 40, 86)
            emit_bass_bar(tr_bass, 2, bar, root, chord, "sustained_drive", b_sec, 104)
            emit_drum_bar(tr_drums, bar, "castle_march", b_sec, is_sec, b_sec == 3, bar, 0.92)
            continue

        prog = prog_B if sec == "B" else (prog_D if sec == "D" else prog_A)
        idx = b_sec % 8
        root, chord = prog[idx]
        tr_shift = 1 if (sec == "D" and idx < 4) else 0
        emit_arp_bar(tr_harpsi, 0, bar, chord, "up_down", 16 if bar % 2 == 0 else 8, 12, 90)
        emit_bar_phrase(tr_strings, 1, bar,
                        duel_runs if (sec == "C" and b_sec % 2 == 1) else castle_4bar[b_sec % 4],
                        tr_shift, 1.0, total_bars)
        tr_brass.add_chord(3, chord, bar * BAR_TICKS, 420, 88)
        if b_sec % 4 == 0:
            tr_bell.add_note(4, chord[2] + 12, bar * BAR_TICKS, 800, 86)
        emit_bass_bar(tr_bass, 2, bar, root, chord, "gallop" if sec == "D" else "mario_bounce", b_sec, 108)
        emit_drum_bar(tr_drums, bar, "castle_march", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_victory_sanctuary(filepath: str):
    """48-Bar Sacred Lilypad Victory Sanctuary (120 BPM, C Major -> Eb Lift -> C Finale)."""
    midi = MidiFile(tempo_bpm=120.0)
    tr_trumpet = setup_track(midi, "Victory Sanctuary Trumpet", 0, 56, 108, 64)
    tr_strings = setup_track(midi, "Triumphant Strings", 1, 48, 96, 36)
    tr_harp = setup_track(midi, "Golden Lilypad Harp", 2, 46, 94, 88)
    tr_bass = setup_track(midi, "Regal Sanctuary Bass", 3, 33, 106, 64)
    tr_bells = setup_track(midi, "Sanctuary Victory Chimes", 4, 14, 92, 92)
    tr_drums = setup_track(midi, "Ceremonial Fanfare Drums", 9, None, 102, 64)

    C, G, Am, Em, F, Dm7, Eb, Bb, Cm, Gm, Ab = (
        (60, 64, 67), (67, 71, 74), (69, 72, 76), (64, 67, 71),
        (65, 69, 72), (62, 65, 69, 72), (63, 67, 70), (58, 62, 65),
        (60, 63, 67), (67, 70, 74), (56, 60, 63),
    )
    prog_A = [(36, C), (43, G), (45, Am), (40, Em), (41, F), (36, C), (38, Dm7), (43, G)]
    prog_B = [(45, Am), (40, Em), (41, F), (36, C), (38, Dm7), (43, G), (36, C), (43, G)]
    prog_C = [(39, Eb), (34, Bb), (36, Cm), (43, Gm), (44, Ab), (39, Eb), (41, F), (43, G)]

    fanfare_4bar = [
        [(0.0, 72, 0.7, 108), (0.75, 76, 0.45, 104), (1.25, 79, 0.7, 112), (2.0, 84, 0.9, 116), (3.0, 83, 0.85, 108)],
        [(0.0, 81, 0.7, 108), (0.75, 79, 0.45, 104), (1.25, 77, 0.7, 106), (2.0, 76, 0.9, 108), (3.0, 74, 0.85, 104)],
        [(0.0, 76, 0.7, 108), (0.75, 79, 0.45, 106), (1.25, 81, 0.7, 110), (2.0, 83, 0.9, 114), (3.0, 84, 0.85, 112)],
        [(0.0, 83, 0.45, 110), (0.5, 81, 0.45, 106), (1.0, 79, 0.85, 108), (2.0, 77, 0.85, 104), (3.0, 79, 0.85, 108)],
    ]
    peace_2bar = [
        [(0.0, 81, 0.9, 102), (1.0, 79, 0.9, 100), (2.0, 76, 0.9, 98), (3.0, 79, 0.85, 104)],
        [(0.0, 77, 0.9, 102), (1.0, 76, 0.9, 100), (2.0, 74, 0.9, 98), (3.0, 72, 0.85, 102)],
    ]

    sections = [(0, "INTRO"), (4, "A"), (12, "B"), (20, "C"), (30, "D"), (42, "TURN")]
    total_bars = 48
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = prog_A[b_sec % 4]
            emit_arp_bar(tr_harp, 2, bar, chord, "up", 8, 12, 86)
            tr_trumpet.add_chord(0, chord, bar * BAR_TICKS, 700, 102)
            tr_bells.add_note(4, chord[2] + 12, bar * BAR_TICKS, 800, 90)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "sustained_drive", b_sec, 102)
            emit_drum_bar(tr_drums, bar, "heroic_march", b_sec, is_sec, b_sec == 3, bar, 0.92)
            continue

        prog = prog_B if sec == "B" else (prog_C if sec == "C" else prog_A)
        idx = b_sec % 8
        root, chord = prog[idx]
        tr_shift = 3 if (sec == "C" and idx < 6) else 0
        emit_arp_bar(tr_harp, 2, bar, chord, "up_down", 8, 12, 86)
        tr_strings.add_chord(1, chord, bar * BAR_TICKS, BAR_TICKS - 40, 96 if sec == "D" else 88)
        emit_bar_phrase(tr_trumpet, 0, bar,
                        peace_2bar[b_sec % 2] if sec == "B" else fanfare_4bar[b_sec % 4],
                        tr_shift, 1.0, total_bars)
        if b_sec % 2 == 0 or sec == "D":
            tr_bells.add_note(4, chord[0] + 12, bar * BAR_TICKS, 720, 90)
        emit_bass_bar(tr_bass, 3, bar, root, chord, "walking" if sec in ("B", "C") else "mario_bounce", b_sec, 106)
        emit_drum_bar(tr_drums, bar, "heroic_march", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_l2_tree_ascent(filepath: str):
    """56-Bar Level 2-1: Ancient World Tree Ascent (134 BPM, D Major -> F -> E Climax)."""
    midi = MidiFile(tempo_bpm=134.0)
    tr_flute = setup_track(midi, "Canopy Pan Flute Lead", 0, 75, 106, 64)
    tr_marimba = setup_track(midi, "Woodland Marimba", 1, 12, 98, 36)
    tr_harp = setup_track(midi, "Leaf Breeze Harp", 2, 46, 92, 90)
    tr_bass = setup_track(midi, "World Tree Bounce Bass", 3, 33, 110, 64)
    tr_pizz = setup_track(midi, "Vine Pizzicato Counter", 4, 45, 90, 92)
    tr_drums = setup_track(midi, "Breezy Canopy Percussion", 9, None, 102, 64)

    D, A, Bm, Fsm, G, Em7, F, C, Dm, Am, Bb, E, B, Csm, Gsm = (
        (62, 66, 69), (69, 73, 76), (59, 62, 66), (66, 69, 73),
        (67, 71, 74), (64, 67, 71, 74), (65, 69, 72), (60, 64, 67),
        (62, 65, 69), (69, 72, 76), (58, 62, 65), (64, 68, 71),
        (59, 63, 66), (61, 64, 68), (68, 71, 75),
    )
    prog_A = [(38, D), (45, A), (35, Bm), (42, Fsm), (43, G), (38, D), (40, Em7), (45, A)]
    prog_B = [(35, Bm), (42, Fsm), (43, G), (38, D), (40, Em7), (42, Fsm), (43, G), (45, A)]
    prog_C = [(41, F), (36, C), (38, Dm), (45, Am), (34, Bb), (41, F), (43, G), (45, A)]
    prog_D = [(40, E), (35, B), (37, Csm), (44, Gsm), (45, A), (40, E), (42, Fsm), (35, B)]

    climb_4bar = [
        [(0.0, 74, 0.45, 104), (0.5, 76, 0.45, 100), (1.0, 78, 0.45, 106), (1.5, 81, 0.45, 108), (2.0, 79, 0.45, 102), (2.5, 78, 0.45, 100), (3.0, 74, 0.85, 106)],
        [(0.0, 78, 0.45, 106), (0.5, 81, 0.45, 104), (1.0, 83, 0.45, 108), (1.5, 86, 0.45, 110), (2.0, 85, 0.45, 106), (2.5, 81, 0.45, 104), (3.0, 78, 0.85, 106)],
        [(0.0, 79, 0.45, 108), (0.5, 78, 0.45, 104), (1.0, 76, 0.45, 102), (1.5, 74, 0.45, 100), (2.0, 76, 0.45, 102), (2.5, 78, 0.45, 104), (3.0, 81, 0.85, 108)],
        [(0.0, 83, 0.45, 110), (0.5, 81, 0.45, 106), (1.0, 79, 0.45, 104), (1.5, 78, 0.45, 102), (2.0, 76, 0.85, 104), (3.0, 74, 0.85, 108)],
    ]
    loop_motif = [(i * 0.5, p, 0.42, 100) for i, p in enumerate([74, 78, 81, 86, 83, 81, 78, 74])]

    sections = [(0, "INTRO"), (4, "A"), (12, "Ap"), (20, "B"), (28, "C"), (38, "D"), (50, "TURN")]
    total_bars = 56
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = (38, D) if b_sec < 3 else (45, A)
            emit_arp_bar(tr_harp, 2, bar, chord, "up", 8, 12, 86)
            emit_arp_bar(tr_marimba, 1, bar, chord, "up_down", 8, 0, 88)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce", b_sec, 102)
            emit_drum_bar(tr_drums, bar, "tribal_percussion", b_sec, is_sec, b_sec == 3, bar, 0.9)
            continue

        prog = prog_B if sec == "B" else (prog_C if sec == "C" else (prog_D if sec == "D" else prog_A))
        idx = b_sec % 8
        root, chord = prog[idx]
        tr_shift = 3 if (sec == "C" and idx < 6) else (2 if sec == "D" else 0)
        emit_arp_bar(tr_marimba, 1, bar, chord, "up_down", 8, 0, 90)
        emit_arp_bar(tr_harp, 2, bar, chord, "up", 16 if sec == "D" else 8, 12, 84)
        emit_arp_bar(tr_pizz, 4, bar, chord, "down", 8, 12, 80)
        emit_bar_phrase(tr_flute, 0, bar,
                        loop_motif if (sec in ("Ap", "B") and b_sec % 2 == 1) else climb_4bar[b_sec % 4],
                        tr_shift, 1.0, total_bars)
        emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce", b_sec, 108)
        emit_drum_bar(tr_drums, bar, "sky_arcade" if sec not in ("A", "TURN") else "tribal_percussion",
                      b_sec, is_sec, (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.0)

    midi.save(filepath)


def compose_l2_skyfrog(filepath: str):
    """60-Bar Level 2-2/2-3: Skyfrog Nimbus Platforming (144 BPM, C Major -> D Climax!)."""
    midi = MidiFile(tempo_bpm=144.0)
    tr_lead = setup_track(midi, "Skyfrog Synth Lead", 0, 80, 106, 64)
    tr_brass = setup_track(midi, "Nimbus Fanfare Brass", 1, 61, 98, 36)
    tr_glock = setup_track(midi, "Cloud Sparkle Glock", 2, 9, 94, 92)
    tr_bass = setup_track(midi, "Skyfrog Bounce Bass", 3, 33, 112, 64)
    tr_harm = setup_track(midi, "Skyline Harmony Lead", 4, 81, 88, 86)
    tr_drums = setup_track(midi, "Upbeat Platformer Drums", 9, None, 112, 64)

    C, Am, F, G, Em, Dm, Bb, D, Bm, A, Fsm = (
        (60, 64, 67), (69, 72, 76), (65, 69, 72), (67, 71, 74),
        (64, 67, 71), (62, 65, 69), (58, 62, 65), (62, 66, 69),
        (59, 62, 66), (69, 73, 76), (66, 69, 73),
    )
    prog_A = [(36, C), (45, Am), (41, F), (43, G), (36, C), (40, Em), (38, Dm), (43, G)]
    prog_B = [(41, F), (43, G), (40, Em), (45, Am), (38, Dm), (43, G), (36, C), (43, G)]
    prog_C = [(45, Am), (40, Em), (41, F), (36, C), (38, Dm), (34, Bb), (43, G), (43, G)]
    prog_D = [(38, D), (35, Bm), (43, G), (45, A), (38, D), (42, Fsm), (35, Bm), (45, A)]

    sky_4bar = [
        [(0.0, 76, 0.45, 108), (0.5, 79, 0.45, 106), (1.0, 84, 0.45, 114), (1.5, 83, 0.45, 106), (2.0, 79, 0.45, 104), (2.5, 76, 0.45, 102), (3.0, 72, 0.85, 108)],
        [(0.0, 74, 0.45, 106), (0.5, 76, 0.45, 104), (1.0, 79, 0.45, 110), (1.5, 81, 0.45, 112), (2.0, 83, 0.45, 110), (2.5, 81, 0.45, 106), (3.0, 79, 0.85, 108)],
        [(0.0, 84, 0.45, 112), (0.5, 83, 0.45, 108), (1.0, 81, 0.45, 106), (1.5, 79, 0.45, 104), (2.0, 77, 0.45, 106), (2.5, 76, 0.45, 104), (3.0, 74, 0.85, 106)],
        [(0.0, 76, 0.45, 106), (0.5, 77, 0.45, 108), (1.0, 79, 0.45, 110), (1.5, 83, 0.45, 112), (2.0, 84, 0.85, 114), (3.0, 79, 0.85, 110)],
    ]
    cloud_2bar = [
        [(0.0, 77, 0.45, 106), (0.5, 81, 0.45, 108), (1.0, 84, 0.45, 112), (1.5, 83, 0.45, 106), (2.0, 79, 0.45, 104), (2.5, 74, 0.45, 100), (3.0, 76, 0.85, 106)],
        [(0.0, 79, 0.45, 108), (0.5, 83, 0.45, 110), (1.0, 86, 0.45, 114), (1.5, 84, 0.45, 108), (2.0, 81, 0.45, 106), (2.5, 79, 0.45, 104), (3.0, 72, 0.85, 108)],
    ]
    solo_trade = [(i * 0.5, p, 0.42, 106) for i, p in enumerate([84, 83, 81, 79, 77, 79, 81, 84])]

    sections = [(0, "INTRO"), (4, "A"), (12, "Ap"), (20, "B"), (28, "C"), (38, "D"), (52, "TURN")]
    total_bars = 60
    for bar in range(total_bars):
        sec, b_sec, is_sec = section_pos(bar, sections)
        if sec == "INTRO":
            root, chord = prog_A[b_sec % 4]
            emit_bar_phrase(tr_glock, 2, bar, solo_trade if b_sec % 2 == 0 else sky_4bar[b_sec],
                            12 if b_sec % 2 else 0, 0.95, total_bars)
            emit_bar_phrase(tr_brass, 1, bar, sky_4bar[b_sec], -12, 0.92, total_bars)
            emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce", b_sec, 106)
            emit_drum_bar(tr_drums, bar, "sky_arcade", b_sec, is_sec, b_sec == 3, bar, 0.94)
            continue

        prog = prog_B if sec == "B" else (prog_C if sec == "C" else (prog_D if sec == "D" else prog_A))
        root, chord = prog[b_sec % 8]
        tr_shift = 2 if sec == "D" else 0
        if sec == "B":
            mel = cloud_2bar[b_sec % 2]
        elif sec == "C" and b_sec % 2 == 1:
            mel = solo_trade
        else:
            mel = sky_4bar[b_sec % 4]

        emit_bar_phrase(tr_lead, 0, bar, mel, tr_shift, 1.0, total_bars)
        if sec != "A":
            emit_bar_phrase(tr_harm, 4, bar, mel, tr_shift + (4 if b_sec % 2 == 0 else -12), 0.86, total_bars)
        emit_arp_bar(tr_glock, 2, bar, chord, "up_down", 8, 12, 86)
        for beat in range(4):
            tr_brass.add_chord(1, chord, bar * BAR_TICKS + beat * TICKS_PER_BEAT + 240, 160, 88)
        emit_bass_bar(tr_bass, 3, bar, root, chord, "mario_bounce", b_sec, 112)
        emit_drum_bar(tr_drums, bar, "sky_arcade", b_sec, is_sec,
                      (b_sec % 4 == 3) or bar == total_bars - 1, bar, 1.02)

    midi.save(filepath)


def build_all_midi_soundtrack():
    """Generates all 17 extended Standard MIDI soundtrack files into assets/music/."""
    music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "music")
    os.makedirs(music_dir, exist_ok=True)
    print(f"[MidiComposer] Generating complete 16-bit MIDI soundtrack into {music_dir}...")

    compose_jamaican_vivaldi_four_seasons(os.path.join(music_dir, "jungle_vivaldi_reggae.mid"))
    compose_boss_mantis(os.path.join(music_dir, "boss_mantis.mid"))
    compose_boss_hound(os.path.join(music_dir, "boss_hound.mid"))
    compose_boss_toad(os.path.join(music_dir, "boss_toad.mid"))
    compose_boss_falo_snowman(os.path.join(music_dir, "boss_snowman.mid"))
    compose_boss_shark(os.path.join(music_dir, "boss_shark.mid"))
    compose_glacial_hot_springs(os.path.join(music_dir, "ice_hot_springs.mid"))
    compose_title_theme(os.path.join(music_dir, "title_theme.mid"))
    compose_volcanic_magma(os.path.join(music_dir, "volcanic_magma.mid"))
    compose_sunken_grotto(os.path.join(music_dir, "sunken_grotto.mid"))
    compose_temple_ruins(os.path.join(music_dir, "temple_ruins.mid"))
    compose_bioluminescent_cavern(os.path.join(music_dir, "bioluminescent_cavern.mid"))
    compose_sanctum_mystery(os.path.join(music_dir, "sanctum_mystery.mid"))
    compose_hound_palace(os.path.join(music_dir, "hound_palace.mid"))
    compose_victory_sanctuary(os.path.join(music_dir, "victory_sanctuary.mid"))
    compose_l2_tree_ascent(os.path.join(music_dir, "l2_tree_ascent.mid"))
    compose_l2_skyfrog(os.path.join(music_dir, "l2_skyfrog.mid"))

    print("[MidiComposer] All 17 extended Standard MIDI soundtrack files successfully composed and saved!")


if __name__ == "__main__":
    build_all_midi_soundtrack()
