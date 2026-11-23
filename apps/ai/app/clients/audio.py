"""
Small audio conversions some providers need, in pure Python (no ffmpeg):

  webm_to_ogg(data)   the browser records WebM/Opus (MediaRecorder); Gradium STT wants Ogg/Opus. Same Opus packets,
                      new container: we copy them out of the WebM blocks into Ogg pages (no re-encoding, ~1 ms).
  Mp3Encoder          Gradium TTS gives raw PCM; the web player streams mp3 (MediaSource "audio/mpeg"), so we encode
                      each PCM chunk as it arrives (lameenc, LAME bindings) to keep the first byte early.
"""

import struct

import lameenc

# ── WebM (Matroska/EBML) → Ogg, Opus only ──

_SEGMENT, _CLUSTER, _TRACKS, _TRACK_ENTRY, _BLOCK_GROUP = 0x18538067, 0x1F43B675, 0x1654AE6B, 0xAE, 0xA0
_CONTAINERS = {_SEGMENT, _CLUSTER, _TRACKS, _TRACK_ENTRY, _BLOCK_GROUP}  # we walk into these, skip everything else
_CODEC_ID, _CODEC_PRIVATE, _SIMPLE_BLOCK, _BLOCK = 0x86, 0x63A2, 0xA3, 0xA1


class AudioFormatError(ValueError):
    """The recording is not in a format we can convert."""


def _vint(data: bytes, pos: int, keep_marker: bool) -> tuple[int, int]:
    """An EBML variable-length integer at pos → (value, next pos). IDs keep their length marker, sizes don't."""
    first = data[pos]
    length = 1
    while length <= 8 and not first & (0x80 >> (length - 1)):
        length += 1
    if length > 8 or pos + length > len(data):
        raise AudioFormatError("not a WebM file")
    value = first if keep_marker else first & (0xFF >> length)
    for b in data[pos + 1 : pos + length]:
        value = (value << 8) | b
    unknown = not keep_marker and value == (1 << (7 * length)) - 1  # "size unknown" (live recordings)
    return (-1 if unknown else value), pos + length


def webm_opus_packets(data: bytes) -> tuple[bytes, list[bytes]]:
    """(OpusHead from CodecPrivate, Opus packets in order) of a single-track WebM/Opus recording."""
    codec, head, packets = "", b"", []
    pos = 0
    while pos < len(data):
        eid, pos = _vint(data, pos, keep_marker=True)
        size, pos = _vint(data, pos, keep_marker=False)
        if eid in _CONTAINERS:
            continue  # descend: its children follow
        end = len(data) if size < 0 else pos + size
        payload = data[pos:end]
        if eid == _CODEC_ID:
            codec = payload.decode("ascii", "replace")
        elif eid == _CODEC_PRIVATE:
            head = payload
        elif eid in (_SIMPLE_BLOCK, _BLOCK):
            _, p = _vint(payload, 0, keep_marker=False)  # track number
            if payload[p + 2] & 0x06:  # lacing (never used by MediaRecorder for audio)
                raise AudioFormatError("laced WebM blocks are not supported")
            packets.append(payload[p + 3 :])  # skip timecode (2) + flags (1)
        pos = end
    if codec and codec != "A_OPUS":
        raise AudioFormatError(f"WebM codec {codec} is not Opus")
    if not head.startswith(b"OpusHead"):
        raise AudioFormatError("WebM without an Opus header")
    return head, packets


def opus_samples(packet: bytes) -> int:
    """Samples (at 48 kHz) in one Opus packet, from its TOC byte (RFC 6716 §3.1)."""
    if not packet:
        return 0
    config, code = packet[0] >> 3, packet[0] & 3
    if config < 12:
        frame = (480, 960, 1920, 2880)[config % 4]  # SILK 10/20/40/60 ms
    elif config < 16:
        frame = (480, 960)[config % 2]  # hybrid 10/20 ms
    else:
        frame = (120, 240, 480, 960)[config % 4]  # CELT 2.5/5/10/20 ms
    frames = 1 if code == 0 else 2 if code in (1, 2) else (packet[1] & 0x3F if len(packet) > 1 else 0)
    return frame * frames


def _crc_table() -> list[int]:
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
        table.append(r & 0xFFFFFFFF)
    return table


_CRC = _crc_table()


def ogg_crc(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC[((crc >> 24) & 0xFF) ^ b]
    return crc


def ogg_page(packet: bytes, granule: int, seq: int, flags: int, serial: int = 0x564F4943) -> bytes:
    """One Ogg page holding one whole packet (lacing: 255-byte segments + remainder)."""
    lacing = bytes([255] * (len(packet) // 255) + [len(packet) % 255])
    if len(lacing) > 255:
        raise AudioFormatError("Opus packet too large for one Ogg page")
    header = struct.pack("<4sBBqIIIB", b"OggS", 0, flags, granule, serial, seq, 0, len(lacing)) + lacing
    crc = ogg_crc(header + packet)
    return header[:22] + struct.pack("<I", crc) + header[26:] + packet


def webm_to_ogg(data: bytes) -> bytes:
    """WebM/Opus (MediaRecorder) → Ogg/Opus (RFC 7845), packets copied as they are."""
    head, packets = webm_opus_packets(data)
    tags = b"OpusTags" + struct.pack("<I", 9) + b"voice-erp" + struct.pack("<I", 0)
    pages = [ogg_page(head, 0, 0, 0x02), ogg_page(tags, 0, 1, 0)]  # 0x02 = beginning of stream
    granule = 0
    for i, packet in enumerate(packets):
        granule += opus_samples(packet)
        pages.append(ogg_page(packet, granule, i + 2, 0x04 if i == len(packets) - 1 else 0))  # 0x04 = end of stream
    return b"".join(pages)


# ── PCM → mp3 ──


class Mp3Encoder:
    """16-bit mono PCM chunks in, mp3 bytes out, as they come (one encoder per sentence)."""

    def __init__(self, sample_rate: int, kbps: int = 64):
        self.enc = lameenc.Encoder()
        self.enc.set_in_sample_rate(sample_rate)
        self.enc.set_channels(1)
        self.enc.set_bit_rate(kbps)
        self.enc.set_quality(7)  # 2 = best, 7 = fastest; speech at 64 kbps sounds the same
        self.odd = b""  # a chunk cut in the middle of a sample

    def encode(self, pcm: bytes) -> bytes:
        pcm = self.odd + pcm
        cut = len(pcm) - len(pcm) % 2
        self.odd = pcm[cut:]
        return bytes(self.enc.encode(pcm[:cut])) if cut else b""

    def flush(self) -> bytes:
        return bytes(self.enc.flush())
