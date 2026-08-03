"""Browser-safe normalization for SVG files produced by legacy wmf2svg."""

from __future__ import annotations

import html
import re
import struct
import xml.etree.ElementTree as ET


TEXT_NODE = re.compile(r"(<text\b[^>]*>)(.*?)(</text>)", re.DOTALL)
ENTITY = re.compile(r"&(?!(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);)")
SYMBOL_HEX = """
0000000100020003000400050006000700080009000A000B000C000D000E000F
0010001100120013001400150016001700180019001A001B001C001D001E001F
0020002122000023220300250026220D002800292217002B002C2212002E002F
0030003100320033003400350036003700380039003A003B003C003D003E003F
22450391039203A70394039503A603930397039903D1039A039B039C039D039F
03A0039803A103A303A403A503C203A9039E03A80396005B2234005D22A5005F
F8E503B103B203C703B403B503C603B303B703B903D503BA03BB03BC03BD03BF
03C003B803C103C303C403C503D603C903BE03C803B6007B007C007D223C007F
0080008100820083008400850086008700880089008A008B008C008D008E008F
0090009100920093009400950096009700980099009A009B009C009D009E009F
000003D2203222642044221E0192266326662665266021942190219121922193
00B000B12033226500D7221D2202202200F72260226122482026F8E6F8E721B5
21352111211C21182297229522052229222A2283228722842282228622082209
2220220700AE00A92122220F221A22C500AC2227222821D421D021D121D221D3
22C42329F8E8F8E9F8EA2211F8EBF8ECF8EDF8EEF8EFF8F0F8F1F8F2F8F3F8F4
F8FF232A222B2320F8F52321F8F6F8F7F8F8F8F9F8FAF8FBF8FCF8FDF8FE0000
""".replace("\n", "")
SYMBOL_TO_UNICODE = tuple(
    int(SYMBOL_HEX[index : index + 4], 16) for index in range(0, len(SYMBOL_HEX), 4)
)

# Adobe Symbol and old MathType equations use Apple's private-use glyphs for
# pieces of tall parentheses, brackets and braces.  Browsers do not have the
# original Symbol font glyphs, so these otherwise appear as a box with an X.
# Unicode's Technical Symbols block provides equivalent, portable pieces.
MATHTYPE_PRIVATE_TO_UNICODE = str.maketrans(
    {
        "\uf8e5": "\u23b7",  # radical symbol bottom
        "\uf8e6": "\u23d0",  # vertical line extension
        "\uf8e7": "\u23af",  # horizontal line extension
        "\uf8e8": "®",
        "\uf8e9": "©",
        "\uf8ea": "™",
        "\uf8eb": "\u239b",  # left parenthesis upper hook
        "\uf8ec": "\u239c",  # left parenthesis extension
        "\uf8ed": "\u239d",  # left parenthesis lower hook
        "\uf8ee": "\u23a1",  # left square bracket upper corner
        "\uf8ef": "\u23a2",  # left square bracket extension
        "\uf8f0": "\u23a3",  # left square bracket lower corner
        "\uf8f1": "\u23a7",  # left curly bracket upper hook
        "\uf8f2": "\u23a8",  # left curly bracket middle piece
        "\uf8f3": "\u23a9",  # left curly bracket lower hook
        "\uf8f4": "\u23aa",  # curly bracket extension
        "\uf8f5": "\u23ae",  # integral extension
        "\uf8f6": "\u239e",  # right parenthesis upper hook
        "\uf8f7": "\u239f",  # right parenthesis extension
        "\uf8f8": "\u23a0",  # right parenthesis lower hook
        "\uf8f9": "\u23a4",  # right square bracket upper corner
        "\uf8fa": "\u23a5",  # right square bracket extension
        "\uf8fb": "\u23a6",  # right square bracket lower corner
        "\uf8fc": "\u23ab",  # right curly bracket upper hook
        "\uf8fd": "\u23ac",  # right curly bracket middle piece
        "\uf8fe": "\u23ad",  # right curly bracket lower hook
    }
)

WMF_CREATE_OBJECTS = {
    0x00F7,  # META_CREATEPALETTE
    0x0142,  # META_DIBCREATEPATTERNBRUSH
    0x01F9,  # META_CREATEPATTERNBRUSH
    0x02FA,  # META_CREATEPENINDIRECT
    0x02FB,  # META_CREATEFONTINDIRECT
    0x02FC,  # META_CREATEBRUSHINDIRECT
    0x02FD,  # META_CREATEBITMAPINDIRECT
    0x06FE,  # META_CREATEBITMAP
    0x06FF,  # META_CREATEREGION
}
WMF_SINGLE_BYTE_CODEPAGES = {
    161: "cp1253",  # GREEK_CHARSET; MathType π is byte F0
    162: "cp1254",
    163: "cp1258",
    177: "cp1255",
    178: "cp1256",
    186: "cp1257",
    204: "cp1251",
    222: "cp874",
    238: "cp1250",
}


def _allocate_wmf_object(objects: list[dict[str, object] | None], value: dict[str, object]) -> None:
    for index, item in enumerate(objects):
        if item is None:
            objects[index] = value
            return
    objects.append(value)


def _decode_wmf_byte(value: int, font: dict[str, object] | None) -> str:
    if font and str(font.get("face", "")).lower() == "symbol":
        codepoint = SYMBOL_TO_UNICODE[value] if value < len(SYMBOL_TO_UNICODE) else 0
        decoded = chr(codepoint) if codepoint else chr(value)
        return decoded.translate(MATHTYPE_PRIVATE_TO_UNICODE)
    charset = int(font.get("charset", 0)) if font else 0
    codepage = WMF_SINGLE_BYTE_CODEPAGES.get(charset)
    if codepage:
        try:
            return bytes([value]).decode(codepage)
        except UnicodeDecodeError:
            pass
    return chr(value)


def _wmf_text_corrections(raw: bytes) -> list[tuple[str, str]]:
    """Return raw/decoded characters in WMF drawing order.

    libwmf preserves the byte but drops LOGFONT's charset when emitting SVG.
    In MathType files this turns Greek-charset byte F0 (π) into Latin-1 ð.
    Tracking selected WMF font objects lets us recover the intended character
    without guessing from formula text.
    """
    if len(raw) < 18:
        return []
    base = 22 if raw[:4] == b"\xd7\xcd\xc6\x9a" else 0
    if len(raw) < base + 18:
        return []
    header_words = struct.unpack_from("<H", raw, base + 2)[0]
    offset = base + header_words * 2
    objects: list[dict[str, object] | None] = []
    selected_font: dict[str, object] | None = None
    result: list[tuple[str, str]] = []

    while offset + 6 <= len(raw):
        size_words, function = struct.unpack_from("<IH", raw, offset)
        if size_words < 3 or offset + size_words * 2 > len(raw):
            break
        params = raw[offset + 6 : offset + size_words * 2]
        if function in WMF_CREATE_OBJECTS:
            if function == 0x02FB and len(params) >= 18:
                face = params[18:50].split(b"\x00", 1)[0].decode("latin-1", errors="ignore")
                value: dict[str, object] = {
                    "kind": "font",
                    "charset": params[13],
                    "face": face,
                }
            else:
                value = {"kind": "other"}
            _allocate_wmf_object(objects, value)
        elif function == 0x012D and len(params) >= 2:  # META_SELECTOBJECT
            object_index = struct.unpack_from("<H", params)[0]
            if object_index < len(objects):
                candidate = objects[object_index]
                if candidate and candidate.get("kind") == "font":
                    selected_font = candidate
        elif function == 0x01F0 and len(params) >= 2:  # META_DELETEOBJECT
            object_index = struct.unpack_from("<H", params)[0]
            if object_index < len(objects):
                if objects[object_index] is selected_font:
                    selected_font = None
                objects[object_index] = None
        elif function == 0x0A32 and len(params) >= 8:  # META_EXTTEXTOUT
            count, options = struct.unpack_from("<HH", params, 4)
            text_start = 16 if options & 0x0006 else 8
            for value in params[text_start : text_start + count]:
                result.append((chr(value), _decode_wmf_byte(value, selected_font)))
        elif function == 0x0521 and len(params) >= 2:  # META_TEXTOUT
            count = struct.unpack_from("<H", params)[0]
            for value in params[2 : 2 + count]:
                result.append((chr(value), _decode_wmf_byte(value, selected_font)))
        offset += size_words * 2
        if function == 0x0000:
            break
    return result


def _escape_content(content: str, *, symbol_font: bool) -> str:
    decoded = html.unescape(content)
    if symbol_font:
        decoded = "".join(
            chr(SYMBOL_TO_UNICODE[ord(character)])
            if ord(character) < len(SYMBOL_TO_UNICODE) and SYMBOL_TO_UNICODE[ord(character)]
            else character
            for character in decoded
        )
    decoded = decoded.translate(MATHTYPE_PRIVATE_TO_UNICODE)
    return ENTITY.sub("&amp;", decoded).replace("<", "&lt;")


def browser_safe_svg_bytes(raw: bytes, *, source_wmf: bytes | None = None) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    text = "".join(
        character for character in text
        if character in "\t\n\r" or ord(character) >= 0x20
    )
    # libwmf emits CSS declarations such as `font-size:149.333344`.
    # Unitless non-zero font sizes are invalid CSS, so browsers fall back to a
    # tiny default font while retaining the original MathType coordinates. That
    # separates multi-part delimiters and makes formula spacing look collapsed
    # or overlapping after the image is scaled inline. Preserve the WMF metric
    # by making the intended pixel unit explicit.
    text = re.sub(
        r"(font-size\s*:\s*)(-?(?:\d+(?:\.\d*)?|\.\d+))(?=\s*;)",
        r"\1\2px",
        text,
        flags=re.I,
    )
    # MathType coordinates are calculated with Times New Roman metrics. On this
    # Linux browser stack the legacy CSS family `Times` resolves to Nimbus Roman,
    # whose glyph widths differ enough to make adjacent letters touch. Liberation
    # Serif is metric-compatible with Times New Roman and preserves those x
    # positions without inventing extra spacing.
    text = re.sub(
        r"font-family\s*:\s*Times(?=\s*;)",
        "font-family:Liberation Serif,Times New Roman,serif",
        text,
        flags=re.I,
    )

    corrections = _wmf_text_corrections(source_wmf) if source_wmf else []
    svg_character_count = sum(
        len(html.unescape(match.group(2))) for match in TEXT_NODE.finditer(text)
    )
    if len(corrections) != svg_character_count:
        corrections = []
    correction_index = 0

    def escape_text(match: re.Match[str]) -> str:
        nonlocal correction_index
        decoded_content = html.unescape(match.group(2))
        if corrections:
            corrected: list[str] = []
            for character in decoded_content:
                raw_character, intended_character = corrections[correction_index]
                correction_index += 1
                corrected.append(
                    intended_character
                    if character in {raw_character, intended_character}
                    else character
                )
            decoded_content = "".join(corrected)
        symbol_font = bool(re.search(r"font-family\s*:\s*Symbol\b", match.group(1), re.I))
        technical_math = bool(
            re.search(r"[\ue000-\uf8ff\u239b-\u23bf]", decoded_content)
        )
        content = _escape_content(decoded_content, symbol_font=symbol_font)
        opening = match.group(1)
        if symbol_font or technical_math:
            opening = re.sub(
                r"font-family\s*:\s*[^;]+",
                "font-family:Noto Sans Math,DejaVu Sans,serif",
                opening,
                flags=re.I,
            )
        return f"{opening}{content}{match.group(3)}"

    text = TEXT_NODE.sub(escape_text, text)
    if re.search(r"<svg\b(?![^>]*\bxmlns=)", text):
        text = re.sub(
            r"<svg\b", '<svg xmlns="http://www.w3.org/2000/svg"', text, count=1
        )
    repaired = text.encode("utf-8")
    ET.fromstring(repaired)
    return repaired
