from pathlib import Path
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ============================================================
# Civ V Singleplayer -> Hotseat Scenario Converter
#
# Based on:
#   - GMR CivSaveLib section logic
#   - civ5-save-parser's Civ/player header parsing
#   - byte comparisons of genuine 1-human/1-AI and 2-human
#     Civilization V hotseat saves.
#
# Tested conversion pattern:
#   * visible game type -> Hotseat
#   * internal game type -> Hotseat
#   * selected civ player type -> Human in both duplicated arrays
#   * selected civ difficulty -> Prince in both duplicated arrays
#   * selected local-human participation bytes enabled
#   * selected human player names populated in both duplicated arrays
# ============================================================

HOTSEAT = 2
AI = 1
DEAD = 2
HUMAN = 3
MISSING = 4
PRINCE = 3

DELIM = b"\x40\x00\x00\x00"

# GMR save-layout constants
BYTES_TO_SKIP_IN_BEGINNING = 56
SECTION_DELIMITER = 0x40
GAME_TYPE_SECTION_NUMBER = 15
GAME_TYPE_HEADER_LOCATION = 0x2C
MYSTERIOUS_DISAPPEARING_SECTION = 17

SECTIONS_TO_SKIP = {
    2: 0x100,   # Primary player-name section
    12: 0x100,  # Passwords
    15: 0x12A,  # Game type
    18: 0x112,  # Map script
    21: 0x100,  # Secondary player-name section
}

BYTES_FOR_LUA = b"lua"
BYTES_FOR_MAP = b"Map"
DISAPPEARING_SECTION_LAST_BLOCK = b"\xFF\xFF\x00\x00"

# "Simple chunk" indexes used by civ5-save-parser and confirmed
# against genuine saves. These are zero-based.
PRIMARY_NAME_CHUNK = 1
PRIMARY_TYPE_CHUNK = 2
PRIMARY_DIFFICULTY_CHUNK = 5

SECONDARY_DIFFICULTY_CHUNK = 15
SECONDARY_NAME_CHUNK = 21
LOCAL_PLAYER_FLAGS_CHUNK = 24
SECONDARY_TYPE_CHUNK = 26

CIV_NAME_CHUNK = 6
LEADER_NAME_CHUNK = 7


# ============================================================
# Basic helpers
# ============================================================

def read_u32(buf, pos):
    if pos + 4 > len(buf):
        raise ValueError("Unexpected end of save data.")
    return struct.unpack_from("<I", buf, pos)[0], pos + 4


def read_lp_string(buf, pos):
    """Read Civ V 4-byte-length-prefixed string."""
    length, pos = read_u32(buf, pos)

    if length > 1_000_000:
        raise ValueError("Invalid string length while parsing save.")

    if pos + length > len(buf):
        raise ValueError("String runs beyond end of save section.")

    raw = buf[pos:pos + length]
    pos += length
    return raw.decode("utf-8", errors="replace"), pos


def encode_lp_string(text):
    raw = text.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def pretty(text):
    if not text:
        return "Unknown"

    for prefix in (
        "CIVILIZATION_",
        "LEADER_",
        "TXT_KEY_CIV_",
        "TXT_KEY_",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    return text.replace("_", " ").title()


# ============================================================
# Simple 0x40 00 00 00 chunks (used by civ5-save-parser)
# ============================================================

def get_simple_chunks(buf):
    chunks = []

    p = buf.find(DELIM)
    while p != -1:
        q = buf.find(DELIM, p + 4)
        if q == -1:
            break

        chunks.append((p + 4, q))
        p = q

    if len(chunks) < 27:
        raise ValueError(
            f"Save does not contain enough recognizable Civ V chunks "
            f"(found {len(chunks)}, expected at least 27)."
        )

    return chunks


def replace_simple_chunk(data, chunk_index, new_bytes):
    chunks = get_simple_chunks(data)
    start, end = chunks[chunk_index]
    data[start:end] = new_bytes


def get_simple_chunk_bytes(data, chunk_index):
    chunks = get_simple_chunks(data)
    start, end = chunks[chunk_index]
    return bytes(data[start:end])


# ============================================================
# GMR's robust section locating logic
# ============================================================

def preceding_section_is_disappearing_one(buf, read_index):
    return bytes(buf[read_index - 4:read_index]) == DISAPPEARING_SECTION_LAST_BLOCK


def blocks_to_skip(section_count):
    return SECTIONS_TO_SKIP.get(section_count, 0)


def get_gmr_section_bounds(buf, section_number):
    section_count = 0
    read_index = BYTES_TO_SKIP_IN_BEGINNING

    # Find the first real section delimiter after the LUA/MAP marker.
    while read_index < len(buf):
        if buf[read_index] == SECTION_DELIMITER:
            found_text = True

            for i in range(3):
                previous = buf[read_index - (3 - i)]
                found_text &= (
                    previous == BYTES_FOR_LUA[i]
                    or previous == BYTES_FOR_MAP[i]
                )

            if found_text:
                break

        read_index += 1

    if read_index >= len(buf):
        raise ValueError("Could not locate Civ V save sections.")

    while read_index < len(buf):
        if buf[read_index] == SECTION_DELIMITER:
            section_count += 1

            if section_count == section_number:
                section_start = read_index + 1
                read_index += 1
                break

            if section_count == MYSTERIOUS_DISAPPEARING_SECTION + 1:
                if not preceding_section_is_disappearing_one(buf, read_index):
                    read_index += blocks_to_skip(
                        MYSTERIOUS_DISAPPEARING_SECTION + 1
                    )
                    section_count += 1

            read_index += blocks_to_skip(section_count)

        read_index += 1
    else:
        raise ValueError(f"Could not locate Civ V section {section_number}.")

    section_index = 0
    section_limit = SECTIONS_TO_SKIP.get(section_count, 0)

    while (
        read_index < len(buf)
        and (
            buf[read_index] != SECTION_DELIMITER
            or section_index < section_limit
        )
    ):
        read_index += 1
        section_index += 1

    return section_start, read_index


def set_full_hotseat_game_type(data):
    """
    Reproduce GMR's SetGameTypeInSaveFileBytes():
      1) visible header byte at 0x2C
      2) internal game-type byte nine bytes from end of section 15
    """
    if len(data) <= GAME_TYPE_HEADER_LOCATION:
        raise ValueError("File is too small to be a Civ V save.")

    data[GAME_TYPE_HEADER_LOCATION] = HOTSEAT

    start, end = get_gmr_section_bounds(data, GAME_TYPE_SECTION_NUMBER)

    if end - start < 9:
        raise ValueError("Internal game-type section is unexpectedly short.")

    data[end - 9] = HOTSEAT


# ============================================================
# Civ/player parsing
# ============================================================

def parse_civs(data):
    chunks = get_simple_chunks(data)

    # Primary player/civ status array.
    type_start, type_end = chunks[PRIMARY_TYPE_CHUNK]
    type_bytes = bytes(data[type_start:type_end])

    if len(type_bytes) % 4 != 0:
        raise ValueError("Player type section has unexpected length.")

    statuses = [
        struct.unpack_from("<I", type_bytes, i)[0]
        for i in range(0, len(type_bytes), 4)
    ]

    # Civilization names.
    civ_buf = get_simple_chunk_bytes(data, CIV_NAME_CHUNK)
    civ_names = []
    pos = 0

    for _ in range(len(statuses)):
        if pos >= len(civ_buf):
            civ_names.append("")
            continue

        try:
            text, pos = read_lp_string(civ_buf, pos)
        except Exception:
            civ_names.append("")
            break

        civ_names.append(text)

    while len(civ_names) < len(statuses):
        civ_names.append("")

    # Leader names.
    leader_buf = get_simple_chunk_bytes(data, LEADER_NAME_CHUNK)
    leaders = []
    pos = 0

    for _ in range(len(statuses)):
        if pos >= len(leader_buf):
            leaders.append("")
            continue

        try:
            text, pos = read_lp_string(leader_buf, pos)
        except Exception:
            leaders.append("")
            break

        leaders.append(text)

    while len(leaders) < len(statuses):
        leaders.append("")

    civs = []

    for i, status in enumerate(statuses):
        raw_civ = civ_names[i]
        raw_leader = leaders[i]

        # Hide unused slots and barbarian pseudo-players.
        if status == MISSING:
            continue

        if not raw_civ:
            continue

        if raw_leader == "LEADER_BARBARIAN":
            continue

        civs.append({
            "slot": i,
            "status": status,
            "civ_raw": raw_civ,
            "leader_raw": raw_leader,
            "civ": pretty(raw_civ),
            "leader": pretty(raw_leader),
        })

    return civs


# ============================================================
# Player-name arrays
# ============================================================

def parse_64_names(chunk_bytes):
    names = []
    pos = 0

    for _ in range(64):
        if pos + 4 > len(chunk_bytes):
            names.append("")
            continue

        length = struct.unpack_from("<I", chunk_bytes, pos)[0]
        pos += 4

        if pos + length > len(chunk_bytes):
            raise ValueError("Malformed player-name section.")

        raw = chunk_bytes[pos:pos + length]
        pos += length
        names.append(raw.decode("utf-8", errors="replace"))

    # Preserve anything following the 64-name table.
    remainder = chunk_bytes[pos:]
    return names, remainder


def build_64_names(names, remainder=b""):
    while len(names) < 64:
        names.append("")

    out = bytearray()

    for name in names[:64]:
        out += encode_lp_string(name)

    out += remainder
    return bytes(out)


def set_human_names(data, selected_slots):
    # Work from the later chunk first so resizing it does not disturb
    # the earlier chunk's index before we recalculate.
    for chunk_index in (SECONDARY_NAME_CHUNK, PRIMARY_NAME_CHUNK):
        old = get_simple_chunk_bytes(data, chunk_index)
        names, remainder = parse_64_names(old)

        for slot in selected_slots:
            if 0 <= slot < 64:
                names[slot] = f"Player {slot + 1}"

        replace_simple_chunk(
            data,
            chunk_index,
            build_64_names(names, remainder)
        )


# ============================================================
# Human/player arrays
# ============================================================

def set_u32_slot_in_chunk(data, chunk_index, slot, value):
    chunks = get_simple_chunks(data)
    start, end = chunks[chunk_index]

    offset = start + slot * 4

    if offset + 4 > end:
        raise ValueError(
            f"Player slot {slot} is outside chunk {chunk_index}."
        )

    struct.pack_into("<I", data, offset, value)


def set_player_control_arrays(data, civs, selected_slots):
    active_slots = {
        c["slot"]
        for c in civs
        if c["status"] not in (DEAD, MISSING)
    }

    # First/secondary player-type arrays:
    # selected -> Human; other active slots -> AI.
    for slot in active_slots:
        new_type = HUMAN if slot in selected_slots else AI

        set_u32_slot_in_chunk(
            data, PRIMARY_TYPE_CHUNK, slot, new_type
        )
        set_u32_slot_in_chunk(
            data, SECONDARY_TYPE_CHUNK, slot, new_type
        )

    # In genuine Hotseat saves, human player slots are assigned
    # a human difficulty value (Prince = 3) in both duplicated
    # difficulty arrays. Leave AI difficulty values untouched.
    for slot in selected_slots:
        set_u32_slot_in_chunk(
            data, PRIMARY_DIFFICULTY_CHUNK, slot, PRINCE
        )
        set_u32_slot_in_chunk(
            data, SECONDARY_DIFFICULTY_CHUNK, slot, PRINCE
        )

    # Genuine 2-human Hotseat comparison showed an additional
    # per-local-player byte array here:
    #
    # Player 1 is the initial/current local player and remains 0.
    # Additional selected local Hotseat players are enabled with 1.
    chunks = get_simple_chunks(data)
    start, end = chunks[LOCAL_PLAYER_FLAGS_CHUNK]

    for slot in range(1, 64):
        pos = start + slot

        if pos >= end:
            break

        # Only touch slots represented by actual civs.
        if slot in active_slots:
            data[pos] = 1 if slot in selected_slots else 0


# ============================================================
# Conversion
# ============================================================

def convert_save(src, selected_slots):
    data = bytearray(src.read_bytes())

    if data[:4] != b"CIV5":
        raise ValueError("Selected file does not begin with CIV5.")

    civs = parse_civs(data)

    if not selected_slots:
        raise ValueError("Select at least one human civilization.")

    # Verify selected slots still exist in this save.
    valid_slots = {c["slot"] for c in civs}
    bad = selected_slots - valid_slots

    if bad:
        raise ValueError(
            "One or more selected civilization slots could not be found "
            "in the save."
        )

    # 1) Populate player names before changing game type/state.
    set_human_names(data, selected_slots)

    # 2) Human/AI + human difficulty + local participant arrays.
    set_player_control_arrays(data, civs, selected_slots)

    # 3) FULL Hotseat conversion — both header and internal field.
    # This is the crucial piece that makes Civ V actually perform
    # local sequential Hotseat handoffs rather than "Waiting for Players".
    set_full_hotseat_game_type(data)

    output_dir = Path.home() / "Documents" / "My Games" / "Sid Meier's Civilization 5" / "Saves" / "hotseat"
    output_dir.mkdir(parents=True, exist_ok=True)

    dst = output_dir / (src.stem + "_HOTSEAT" + src.suffix)
    dst.write_bytes(data)

    return dst


# ============================================================
# GUI
# ============================================================

class CivSelector:
    def __init__(self, root, src, civs):
        self.root = root
        self.src = src
        self.civs = civs
        self.vars = {}

        root.title("Civilization V Singleplayer → Hotseat Converter")
        root.geometry("760x680")
        root.minsize(650, 500)

        ttk.Label(
            root,
            text="Civilization V Hotseat Converter",
            font=("Segoe UI", 17, "bold")
        ).pack(pady=(16, 4))

        ttk.Label(
            root,
            text=(
                "Check every civilization that should be controlled by a human.\n"
                "Unchecked active civilizations will remain AI."
            ),
            justify="center"
        ).pack(pady=(0, 12))

        path_label = ttk.Label(
            root,
            text=str(src),
            wraplength=700,
            justify="center"
        )
        path_label.pack(padx=20, pady=(0, 10))

        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True, padx=16, pady=6)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            outer, orient="vertical", command=canvas.yview
        )
        inner = ttk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window(
            (0, 0), window=inner, anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for civ in civs:
            slot = civ["slot"]

            row = ttk.Frame(inner)
            row.pack(fill="x", padx=8, pady=4)

            var = tk.BooleanVar(
                value=(civ["status"] == HUMAN)
            )
            self.vars[slot] = var

            cb = ttk.Checkbutton(row, variable=var)
            cb.pack(side="left", padx=(0, 10))

            status = {
                AI: "AI",
                DEAD: "DEAD",
                HUMAN: "HUMAN",
                MISSING: "MISSING",
            }.get(civ["status"], str(civ["status"]))

            label = (
                f"Slot {slot + 1}: {civ['civ']}"
                + (
                    f" — {civ['leader']}"
                    if civ["leader"] != "Unknown"
                    else ""
                )
                + f"   [{status}]"
            )

            ttk.Label(row, text=label).pack(side="left")

            if civ["status"] == DEAD:
                cb.state(["disabled"])

        footer = ttk.Frame(root)
        footer.pack(fill="x", padx=16, pady=16)

        ttk.Button(
            footer,
            text="Cancel",
            command=root.destroy
        ).pack(side="right", padx=5)

        ttk.Button(
            footer,
            text="Convert to Hotseat",
            command=self.convert
        ).pack(side="right", padx=5)

    def convert(self):
        selected = {
            slot
            for slot, var in self.vars.items()
            if var.get()
        }

        if not selected:
            messagebox.showwarning(
                "No humans selected",
                "Select at least one civilization."
            )
            return

        try:
            dst = convert_save(self.src, selected)

            messagebox.showinfo(
                "Conversion complete",
                (
                    "Hotseat save created successfully.\n\n"
                    f"{dst}\n\n"
                    "The original save was not modified.\n\n"
                    "Load the new save from Civ V's Multiplayer → "
                    "Hot Seat → Load Game menu."
                )
            )

            self.root.destroy()

        except Exception as exc:
            messagebox.showerror(
                "Conversion failed",
                str(exc)
            )


def main():
    root = tk.Tk()
    root.withdraw()

    selected = filedialog.askopenfilename(
        title="Choose a Civilization V singleplayer save",
        filetypes=[
            ("Civilization V Save", "*.Civ5Save"),
            ("All files", "*.*"),
        ],
    )

    if not selected:
        root.destroy()
        return

    src = Path(selected)

    try:
        data = bytearray(src.read_bytes())

        if data[:4] != b"CIV5":
            raise ValueError(
                "The selected file does not appear to be a Civ V save."
            )

        civs = parse_civs(data)

        if not civs:
            raise ValueError(
                "No playable civilizations could be identified."
            )

    except Exception as exc:
        messagebox.showerror(
            "Could not read save",
            str(exc)
        )
        root.destroy()
        return

    root.deiconify()
    CivSelector(root, src, civs)
    root.mainloop()


if __name__ == "__main__":
    main()
