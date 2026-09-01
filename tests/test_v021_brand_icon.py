import base64
import hashlib
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "laufapp" / "app" / "static"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _validate_png_bytes(payload: bytes, expected_size: tuple[int, int]) -> None:
    assert payload.startswith(PNG_SIGNATURE)
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    idat = []
    saw_iend = False
    while offset < len(payload):
        assert offset + 12 <= len(payload)
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        crc_end = chunk_data_end + 4
        assert crc_end <= len(payload)
        chunk_data = payload[chunk_data_start:chunk_data_end]
        expected_crc = struct.unpack(">I", payload[chunk_data_end:crc_end])[0]
        assert zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF == expected_crc
        if chunk_type == b"IHDR":
            assert length == 13
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat.append(chunk_data)
        elif chunk_type == b"IEND":
            assert length == 0
            saw_iend = True
            offset = crc_end
            break
        offset = crc_end
    assert saw_iend and offset == len(payload)
    assert (width, height) == expected_size
    assert interlace == 0
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    decoded = zlib.decompress(b"".join(idat))
    assert len(decoded) == height * (row_bytes + 1)


def test_header_uses_approved_inline_png_without_separate_asset_request():
    index = (STATIC / "index.html").read_text()
    match = re.search(r'<span class="brand-mark"><img src="data:image/png;base64,([A-Za-z0-9+/=]+)"', index)
    assert match, "Header brand icon must be an inline PNG data URI"
    payload = base64.b64decode(match.group(1), validate=True)
    _validate_png_bytes(payload, (192, 192))
    assert hashlib.sha256(payload).hexdigest() == "68c8333c04ba96acdbf021f24992457ce31888d3be9e3c14158b4aa4b7461ff4"
    assert '<span class="brand-mark"><img src="icon-192.png' not in index


def test_referenced_png_assets_are_structurally_decodable():
    for name, size in {
        "icon-192.png": (192, 192),
        "apple-touch-icon.png": (180, 180),
    }.items():
        _validate_png_bytes((STATIC / name).read_bytes(), size)
    assert not (STATIC / "icon-512.png").exists()


def test_pwa_svg_is_self_contained_and_matches_brand_palette():
    svg_path = STATIC / "icon.svg"
    svg = svg_path.read_text()
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 512 512"
    assert '#000' in svg and '#b9ff16' in svg
    assert svg.count('M112 183h70') == 1
    assert svg.count('M95 251h72') == 1
    assert svg.count('M82 319h72') == 1
    assert 'href=' not in svg and 'http://' not in svg.replace('http://www.w3.org/2000/svg', '')
    manifest = (STATIC / "manifest.webmanifest").read_text()
    assert '"src":"icon.svg?v=0.2.21","sizes":"any","type":"image/svg+xml"' in manifest
    assert 'icon-512.png' not in manifest
