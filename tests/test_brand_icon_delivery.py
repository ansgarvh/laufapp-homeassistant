import binascii
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _validate_png(data: bytes, expected_size: tuple[int, int]) -> None:
    assert data.startswith(PNG_SIGNATURE)
    pos = len(PNG_SIGNATURE)
    idat = bytearray()
    size = None
    saw_iend = False
    while pos < len(data):
        assert pos + 12 <= len(data)
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk_start = pos + 8
        chunk_end = chunk_start + length
        crc_end = chunk_end + 4
        assert crc_end <= len(data)
        chunk = data[chunk_start:chunk_end]
        stored_crc = struct.unpack(">I", data[chunk_end:crc_end])[0]
        actual_crc = binascii.crc32(chunk_type + chunk) & 0xFFFFFFFF
        assert stored_crc == actual_crc
        if chunk_type == b"IHDR":
            size = struct.unpack(">II", chunk[:8])
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            saw_iend = True
            pos = crc_end
            break
        pos = crc_end
    assert size == expected_size
    assert idat
    assert zlib.decompress(bytes(idat))
    assert saw_iend
    assert pos == len(data)


def test_header_brand_icon_is_reachable_over_the_exact_browser_url(client):
    page = client.get("/")
    assert page.status_code == 200
    assert 'src="icon-192.png?v=0.2.21"' in page.text

    response = client.get("/icon-192.png?v=0.2.21")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert "immutable" in response.headers.get("cache-control", "")
    _validate_png(response.content, (192, 192))


def test_pwa_512_icon_route_is_reachable_and_decodable(client):
    response = client.get("/icon-512.png?v=0.2.20")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    _validate_png(response.content, (512, 512))


def test_existing_apple_touch_icon_route_remains_available(client):
    response = client.get("/apple-touch-icon.png?v=0.2.20")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    _validate_png(response.content, (192, 192))
