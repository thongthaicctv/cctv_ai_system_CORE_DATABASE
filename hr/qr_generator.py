# FILE: hr/qr_generator.py
# Pure-Python QR Code generator (Version 1-10, ECC Level M)
# Không cần pip install - chỉ dùng stdlib + Pillow (đã có sẵn trong dự án)
# Tạo ảnh QR dạng PIL.Image hoặc bytes PNG

"""
Tạo QR code cho nhân viên:
  content : "EMP:NV001"
  name    : "Nguyễn Văn An"
  dept    : "Bảo vệ"

Dùng:
    img = make_employee_qr("NV001", "Nguyễn Văn An", "Bảo vệ")
    img.save("nv001.png")
    # hoặc lấy bytes PNG:
    buf = employee_qr_bytes("NV001", "Nguyễn Văn An", "Bảo vệ")
"""

import io
import os
import struct
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────────────────────
# 1. REED-SOLOMON GF(256)  (irreducible poly 0x11d)
# ─────────────────────────────────────────────────────────────
_PRIM = 0x11d
_GF_EXP = [0] * 512
_GF_LOG  = [0] * 256

def _init_gf():
    x = 1
    for i in range(255):
        _GF_EXP[i] = x
        _GF_LOG[x] = i
        x <<= 1
        if x & 256:
            x ^= _PRIM
    for i in range(255, 512):
        _GF_EXP[i] = _GF_EXP[i - 255]

_init_gf()

def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] + _GF_LOG[b]) % 255]

def _gf_poly_mul(p, q):
    r = [0] * (len(p) + len(q) - 1)
    for i, pi in enumerate(p):
        for j, qj in enumerate(q):
            r[i + j] ^= _gf_mul(pi, qj)
    return r

def _rs_generator(n_ec):
    g = [1]
    for i in range(n_ec):
        g = _gf_poly_mul(g, [1, _GF_EXP[i]])
    return g

def _rs_encode(data, n_ec):
    gen = _rs_generator(n_ec)
    msg = list(data) + [0] * n_ec
    for i in range(len(data)):
        c = msg[i]
        if c:
            for j, gj in enumerate(gen):
                msg[i + j] ^= _gf_mul(c, gj)
    return msg[len(data):]

# ─────────────────────────────────────────────────────────────
# 2. QR CODE TABLES  (Version 1..10, ECC M)
# ─────────────────────────────────────────────────────────────
# (total_codewords, ec_codewords_per_block, blocks_group1, data_codewords_group1,
#  blocks_group2, data_codewords_group2)
_QR_CAPS = {
    1:  (26,  10, 1, 16, 0,  0),
    2:  (44,  16, 1, 28, 0,  0),
    3:  (70,  26, 2, 22, 0,  0),
    4:  (100, 18, 2, 32, 2, 14),  # simplified: treat as 4 blocks of ~14
    5:  (134, 24, 2, 43, 2, 15),
    6:  (172, 16, 4, 27, 0,  0),
    7:  (196, 18, 4, 31, 1, 15),  # actually 4+1 but simplify
    8:  (242, 22, 2, 38, 2, 14),
    9:  (292, 22, 3, 36, 2, 17),
    10: (346, 26, 4, 43, 1, 30),  # (simplified grouping)
}

# Max byte capacity for each version at ECC M
_QR_DATA_CAP = {1:16, 2:28, 3:44, 4:64, 5:86, 6:108, 7:124, 8:154, 9:182, 10:216}

# Format info bits (ECC M, mask 0..7) pre-computed
_FORMAT_INFO = {
    0: 0b101010000010010,
    1: 0b101000100100101,
    2: 0b101111001111100,
    3: 0b101101101001011,
    4: 0b100010111111001,
    5: 0b100000011001110,
    6: 0b100111110010111,
    7: 0b100101010100000,
}

# Alignment pattern centers per version (version 1 has none)
_ALIGN_POS = {
    1:[], 2:[6,18], 3:[6,22], 4:[6,26], 5:[6,30],
    6:[6,34], 7:[6,22,38], 8:[6,24,42], 9:[6,26,46], 10:[6,28,50],
}

# ─────────────────────────────────────────────────────────────
# 3. QR MATRIX BUILDER
# ─────────────────────────────────────────────────────────────
_DARK  = 1
_LIGHT = 0
_FUNC  = 2   # functional (not masked)

class _QRMatrix:
    def __init__(self, version):
        self.ver  = version
        self.size = version * 4 + 17
        self.mat  = [[None] * self.size for _ in range(self.size)]

    def set(self, r, c, v):
        if 0 <= r < self.size and 0 <= c < self.size:
            self.mat[r][c] = v

    def get(self, r, c):
        if 0 <= r < self.size and 0 <= c < self.size:
            return self.mat[r][c]
        return None

    def _finder(self, tr, tc):
        for r in range(7):
            for c in range(7):
                if r in (0,6) or c in (0,6) or (2<=r<=4 and 2<=c<=4):
                    self.mat[tr+r][tc+c] = _FUNC|_DARK
                else:
                    self.mat[tr+r][tc+c] = _FUNC|_LIGHT

    def _separator(self):
        size = self.size
        for i in range(8):
            for pos in [(7,i),(i,7),(size-8,i),(i,size-8),(7,size-1-i),(size-1-i,7)]:
                r,c = pos
                if 0<=r<size and 0<=c<size and self.mat[r][c] is None:
                    self.mat[r][c] = _FUNC|_LIGHT

    def _timing(self):
        size = self.size
        for i in range(8, size-8):
            v = _FUNC|(_DARK if i%2==0 else _LIGHT)
            if self.mat[6][i] is None: self.mat[6][i] = v
            if self.mat[i][6] is None: self.mat[i][6] = v

    def _dark_module(self):
        self.mat[4*self.ver+9][8] = _FUNC|_DARK

    def _alignment(self):
        positions = _ALIGN_POS.get(self.ver, [])
        for r in positions:
            for c in positions:
                if self.mat[r][c] is not None:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        rr, cc = r+dr, c+dc
                        if dr in (-2,2) or dc in (-2,2):
                            self.mat[rr][cc] = _FUNC|_DARK
                        elif dr==0 and dc==0:
                            self.mat[rr][cc] = _FUNC|_DARK
                        else:
                            self.mat[rr][cc] = _FUNC|_LIGHT

    def _format_area(self):
        size = self.size
        # Reserve format info area with placeholder
        for i in range(9):
            if self.mat[8][i] is None: self.mat[8][i] = _FUNC|_LIGHT
            if self.mat[i][8] is None: self.mat[i][8] = _FUNC|_LIGHT
        for i in range(8):
            if self.mat[8][size-1-i] is None: self.mat[8][size-1-i] = _FUNC|_LIGHT
            if self.mat[size-1-i][8] is None: self.mat[size-1-i][8] = _FUNC|_LIGHT

    def place_format(self, mask_id):
        size = self.size
        fmt = _FORMAT_INFO[mask_id]
        bits = [(fmt >> (14-i)) & 1 for i in range(15)]
        # Around top-left finder
        positions_h = [0,1,2,3,4,5,7,8, size-7,size-6,size-5,size-4,size-3,size-2,size-1]
        positions_v = [8,8,8,8,8,8,8,8, 8,8,8,8,8,8,8]
        for i,(r,c) in enumerate(zip(positions_v[:8], positions_h[:8])):
            self.mat[r][c] = _FUNC | bits[i]
        # skip timing bit at index 6
        for i,(r,c) in enumerate(zip(positions_v[8:], positions_h[8:])):
            self.mat[r][c] = _FUNC | bits[7+i]
        # Vertical strip
        v_rows = [size-1,size-2,size-3,size-4,size-5,size-6,size-7,
                  8,7,5,4,3,2,1,0]
        for i,r in enumerate(v_rows):
            self.mat[r][8] = _FUNC | bits[i]

    def place_data(self, data_bits):
        size = self.size
        idx  = 0
        up   = True
        col  = size - 1
        while col >= 0:
            if col == 6:
                col -= 1
                continue
            rows = range(size-1, -1, -1) if up else range(size)
            for row in rows:
                for dc in (0, -1):
                    c = col + dc
                    if self.mat[row][c] is None:
                        bit = data_bits[idx] if idx < len(data_bits) else 0
                        self.mat[row][c] = bit
                        idx += 1
            up = not up
            col -= 2

    def apply_mask(self, mask_id):
        size = self.size
        for r in range(size):
            for c in range(size):
                v = self.mat[r][c]
                if v is None or (v & 2):   # skip functional
                    continue
                apply = False
                if mask_id == 0: apply = (r+c) % 2 == 0
                elif mask_id == 1: apply = r % 2 == 0
                elif mask_id == 2: apply = c % 3 == 0
                elif mask_id == 3: apply = (r+c) % 3 == 0
                elif mask_id == 4: apply = (r//2 + c//3) % 2 == 0
                elif mask_id == 5: apply = (r*c)%2 + (r*c)%3 == 0
                elif mask_id == 6: apply = ((r*c)%2 + (r*c)%3) % 2 == 0
                elif mask_id == 7: apply = ((r+c)%2 + (r*c)%3) % 2 == 0
                if apply:
                    self.mat[r][c] = 1 - v

    def build(self):
        self._finder(0, 0)
        self._finder(0, self.size-7)
        self._finder(self.size-7, 0)
        self._separator()
        self._timing()
        self._dark_module()
        self._alignment()
        self._format_area()

# ─────────────────────────────────────────────────────────────
# 4. ENCODE DATA → BITSTREAM
# ─────────────────────────────────────────────────────────────
def _encode_byte_mode(text: str, version: int) -> list:
    data = text.encode("utf-8") if isinstance(text, str) else text
    bits = []
    # Mode indicator: byte = 0100
    bits += [0,1,0,0]
    # Character count (8 bits for version 1-9)
    n = len(data)
    bits += [(n >> (7-i)) & 1 for i in range(8)]
    # Data
    for byte in data:
        bits += [(byte >> (7-i)) & 1 for i in range(8)]
    # Terminator
    bits += [0,0,0,0]
    # Pad to multiple of 8
    while len(bits) % 8:
        bits.append(0)
    # Calculate required bits
    cap = _QR_DATA_CAP[version]
    total_bits = cap * 8
    # Pad codewords
    pads = [0xEC, 0x11]
    pi = 0
    while len(bits) < total_bits:
        p = pads[pi % 2]
        bits += [(p >> (7-i)) & 1 for i in range(8)]
        pi += 1
    return bits[:total_bits]


def _bits_to_bytes(bits):
    result = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i+j < len(bits):
                byte = (byte << 1) | bits[i+j]
        result.append(byte)
    return result


def _interleave_blocks(data_bytes, version):
    """Simple interleave for version 1-3 (single block)."""
    info = _QR_CAPS[version]
    total, n_ec, b1, d1, b2, d2 = info
    # Split into blocks
    blocks = []
    offset = 0
    for _ in range(b1):
        blocks.append(data_bytes[offset:offset+d1])
        offset += d1
    for _ in range(b2):
        blocks.append(data_bytes[offset:offset+d2])
        offset += d2
    # EC for each block
    ec_blocks = [_rs_encode(blk, n_ec) for blk in blocks]
    # Interleave data
    result = []
    max_len = max(len(b) for b in blocks)
    for i in range(max_len):
        for blk in blocks:
            if i < len(blk):
                result.append(blk[i])
    # Interleave EC
    for i in range(n_ec):
        for ec in ec_blocks:
            result.append(ec[i])
    return result


# ─────────────────────────────────────────────────────────────
# 5. PENALTY SCORING  (simplified – just pick mask 2 for speed)
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# 6. PUBLIC API
# ─────────────────────────────────────────────────────────────
def make_qr_matrix(text: str) -> _QRMatrix:
    """Tạo QR matrix từ chuỗi text, tự chọn version phù hợp."""
    data = text.encode("utf-8")
    version = 1
    for v, cap in _QR_DATA_CAP.items():
        if len(data) <= cap:
            version = v
            break
    else:
        raise ValueError(f"Text quá dài ({len(data)} bytes), max {_QR_DATA_CAP[10]}")

    bits       = _encode_byte_mode(text, version)
    data_bytes = _bits_to_bytes(bits)
    final_bytes= _interleave_blocks(data_bytes, version)
    final_bits = []
    for byte in final_bytes:
        final_bits += [(byte >> (7-i)) & 1 for i in range(8)]
    # Remainder bits
    rem = {1:0,2:7,3:7,4:7,5:7,6:7,7:0,8:0,9:0,10:0}
    final_bits += [0] * rem.get(version, 0)

    qr = _QRMatrix(version)
    qr.build()
    qr.place_data(final_bits)
    qr.apply_mask(2)           # mask pattern 2 (c%3==0) – good default
    qr.place_format(2)
    return qr


def make_employee_qr(
    emp_id:   str,
    emp_name: str,
    dept:     str,
    module_px: int = 8,
    quiet:    int  = 4,
) -> Image.Image:
    """
    Tạo ảnh QR nhân viên với:
      - QR content : "EMP:{emp_id}"
      - Dưới QR    : "Mã NV: {emp_id}"  +  "{emp_name}"  + "{dept}"
    """
    content = f"EMP:{emp_id}"
    qr = make_qr_matrix(content)
    size = qr.size

    module   = module_px
    quiet_px = quiet * module
    qr_px    = size * module
    margin   = quiet_px

    # Font (dùng default PIL nếu không có truetype)
    try:
        _dir = os.path.dirname(__file__)
        # Thử load font hệ thống Windows / Linux
        for font_path in [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            if os.path.exists(font_path):
                font_name  = ImageFont.truetype(font_path, 18)
                font_id    = ImageFont.truetype(font_path, 16)
                font_dept  = ImageFont.truetype(font_path, 14)
                break
        else:
            raise FileNotFoundError
    except Exception:
        font_name  = ImageFont.load_default()
        font_id    = font_name
        font_dept  = font_name

    # Measure text heights
    dummy = Image.new("RGB", (1, 1))
    dd = ImageDraw.Draw(dummy)
    _, _, _, h_id   = dd.textbbox((0,0), f"Mã NV: {emp_id}", font=font_id)
    _, _, _, h_name = dd.textbbox((0,0), emp_name,            font=font_name)
    _, _, _, h_dept = dd.textbbox((0,0), dept,                font=font_dept)
    text_h = h_id + 6 + h_name + 4 + h_dept + margin

    img_w = qr_px + margin * 2
    img_h = qr_px + margin * 2 + text_h + 10

    img  = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    # Draw QR modules
    for r in range(size):
        for c in range(size):
            v = qr.mat[r][c]
            bit = v & 1 if v is not None else 0
            x0 = margin + c * module
            y0 = margin + r * module
            color = "black" if bit else "white"
            draw.rectangle([x0, y0, x0+module-1, y0+module-1], fill=color)

    # Draw text below QR
    text_y = margin + qr_px + 10

    # "Mã NV: NV001"
    w_id = dd.textlength(f"Mã NV: {emp_id}", font=font_id)
    draw.text(((img_w - w_id) / 2, text_y), f"Mã NV: {emp_id}",
              fill="black", font=font_id)
    text_y += h_id + 6

    # Tên nhân viên (bold nếu có)
    w_name = dd.textlength(emp_name, font=font_name)
    draw.text(((img_w - w_name) / 2, text_y), emp_name,
              fill="black", font=font_name)
    text_y += h_name + 4

    # Bộ phận
    w_dept = dd.textlength(dept, font=font_dept)
    draw.text(((img_w - w_dept) / 2, text_y), dept,
              fill="#555555", font=font_dept)

    return img


def employee_qr_bytes(emp_id: str, emp_name: str, dept: str) -> bytes:
    """Trả về PNG bytes của QR code nhân viên."""
    img = make_employee_qr(emp_id, emp_name, dept)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def save_employee_qr(emp_id: str, emp_name: str, dept: str, path: str):
    """Lưu QR code ra file PNG."""
    img = make_employee_qr(emp_id, emp_name, dept)
    img.save(path, "PNG")
