"""Read bounded PNG text chunks without image decoding or third-party packages."""
from pathlib import Path
import struct
import zlib

MAX_TEXT = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_CHUNKS = 100000


def inflate(data):
    dec = zlib.decompressobj()
    try:
        value = dec.decompress(data, MAX_TEXT + 1)
    except zlib.error as exc:
        raise ValueError('Invalid compressed PNG text') from exc
    if len(value) > MAX_TEXT or dec.unconsumed_tail:
        raise ValueError('PNG compressed text exceeds 4 MiB limit')
    if not dec.eof:
        raise ValueError('Truncated compressed PNG text')
    return value


def decode_text(kind, data):
    key, rest = data.split(b'\0', 1)
    if not 1 <= len(key) <= 79:
        raise ValueError('Invalid PNG text keyword')
    if kind == b'tEXt':
        value = rest.decode('latin-1')
    elif kind == b'zTXt':
        if not rest or rest[0] != 0:
            raise ValueError('Unsupported zTXt compression')
        value = inflate(rest[1:]).decode('latin-1')
    else:
        if len(rest) < 4 or rest[0] not in (0, 1) or rest[1] != 0:
            raise ValueError('Invalid iTXt compression header')
        content = rest[2:].split(b'\0', 2)
        if len(content) != 3:
            raise ValueError('Invalid iTXt language/translation fields')
        payload = inflate(content[2]) if rest[0] else content[2]
        value = payload.decode('utf-8')
    return key.decode('latin-1'), value


def read_png_metadata(path):
    text, warnings = {}, []
    total = 0
    with Path(path).open('rb') as stream:
        if stream.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Input is not a PNG file')
        size = Path(path).stat().st_size
        for index in range(MAX_CHUNKS):
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError('Truncated PNG or missing IEND')
            length, kind = struct.unpack('>I4s', header)
            if length > 0x7fffffff or stream.tell() + length + 4 > size:
                raise ValueError('Invalid or truncated PNG chunk')
            if index == 0 and (kind != b'IHDR' or length != 13):
                raise ValueError('PNG missing initial IHDR')
            if kind in (b'tEXt', b'zTXt', b'iTXt'):
                if length > MAX_TEXT:
                    raise ValueError('PNG text chunk exceeds 4 MiB limit')
                data = stream.read(length)
                crc = struct.unpack('>I', stream.read(4))[0]
                if zlib.crc32(kind + data) != crc:
                    raise ValueError('PNG text chunk CRC mismatch')
                key, value = decode_text(kind, data)
                total += len(value.encode('utf-8'))
                if total > MAX_TOTAL:
                    raise ValueError('PNG metadata exceeds 16 MiB limit')
                if key in text:
                    warnings.append(f'Duplicate metadata key {key}; kept first value')
                else:
                    text[key] = value
            else:
                # Pixel chunks can be large; no allocation or decoding is necessary.
                stream.seek(length + 4, 1)
            if kind == b'IEND':
                if length != 0:
                    raise ValueError('Invalid IEND')
                return {'text': text, 'warnings': warnings}
        raise ValueError('Too many PNG chunks')
