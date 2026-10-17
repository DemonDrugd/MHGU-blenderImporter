bl_info = {
    "name": "MHGU-blenderImporter",
    "author": "DemonDrug",
    "version": (1, 3, 0),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "description": "Import Monster Hunter Generations Ultimate .mod and .lmt files",
    "doc_url": "https://github.com/DemonDrugd/MHGU-blenderImporter",
    "tracker_url": "https://github.com/DemonDrugd/MHGU-blenderImporter/issues",
    "category": "Import-Export"
}

# MHGU MTFramework tools for Blender (v1.3.0)
# GitHub: https://github.com/DemonDrugd/MHGU-blenderImporter

import bpy
import bmesh
import struct
import math
import mathutils
import os
import zlib


def dequantize_quat14(value):
    if value > 8191:
        value = -(16383 - value)
    return value * 0.000244156

def unpack_quat_14(b, endian='<'):
    val = struct.unpack(endian + 'Q', b)[0]
    w_raw = val & 0x3fff
    z_raw = (val >> 14) & 0x3fff
    y_raw = (val >> 28) & 0x3fff
    x_raw = (val >> 42) & 0x3fff
    relframe = (val >> 56) & 0xff
    return (dequantize_quat14(x_raw), dequantize_quat14(y_raw), dequantize_quat14(z_raw), dequantize_quat14(w_raw)), relframe

def unpack_quat_11(b, bounds=None):
    i1, i2, i3 = struct.unpack('<HHH', b[:6])

    x_raw = i1 & 0x7FF
    y_raw = (i2 & 0x3F) | (((i1 & 0xF800) >> 5) & 0x7FF)
    z_raw = (i3 & 1) | (((i2 & 0xFFC0) >> 5) & 0x7FF)
    w_raw = (i3 & 0xFFE) >> 1
    relframe = (i3 & 0xF000) >> 12

    x = x_raw / 2047.0
    y = y_raw / 2047.0
    z = z_raw / 2047.0
    w = w_raw / 2047.0

    if bounds:
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_quat_9(b, bounds=None):
    x_raw = (b[1] & 1) | (b[0] << 1)
    y_raw = (b[2] & 3) | ((b[1] & 0xFE) << 1)
    z_raw = (b[3] & 7) | ((b[2] & 0xFC) << 1)
    w_raw = (b[4] & 0xF) | ((b[3] & 0xF8) << 1)
    relframe = (b[4] & 0xF0) >> 4

    x = x_raw / 511.0
    y = y_raw / 511.0
    z = z_raw / 511.0
    w = w_raw / 511.0

    if bounds:
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_vec3_8(i1, bounds=None):
    bitmask = 0xff
    x = float(i1 & bitmask)
    y = float((i1 >> 8) & bitmask)
    z = float((i1 >> 16) & bitmask)
    relframe = (i1 >> 24) & 0xff
    if bounds:
        add, mult = bounds
        x = (x / 255.0) * mult[0] + add[0]
        y = (y / 255.0) * mult[1] + add[1]
        z = (z / 255.0) * mult[2] + add[2]
    return (x, y, z), relframe

def dequantize_quat32(value):
    return (value - 8) * 0.0089285718

def unpack_quat_7(b, bounds=None):
    ivalue = struct.unpack('<I', b[:4])[0]

    w_raw = ivalue & 0x7F
    z_raw = (ivalue >> 7) & 0x7F
    y_raw = (ivalue >> 14) & 0x7F
    x_raw = (ivalue >> 21) & 0x7F
    relframe = (ivalue >> 28) & 0xF

    x = x_raw / 127.0
    y = y_raw / 127.0
    z = z_raw / 127.0
    w = w_raw / 127.0

    if bounds:
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_quat_xw(ivalue, bounds=None):
    bitmask = 0x3fff
    x_raw = ivalue & bitmask
    w_raw = (ivalue >> 14) & bitmask
    relframe = (ivalue >> 28) & 0xf
    x = x_raw
    y = 0.0
    z = 0.0
    w = w_raw
    if not bounds:
        w *= 0.000244141
        if x > (bitmask * 0.5):
            x = -(bitmask - x)
        x *= 0.000122085
    else:
        x *= 0.000061039
        w *= 0.000061039
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_quat_yw(ivalue, bounds=None):
    bitmask = 0x3fff
    y_raw = ivalue & bitmask
    w_raw = (ivalue >> 14) & bitmask
    relframe = (ivalue >> 28) & 0xf
    x = 0.0
    y = y_raw
    z = 0.0
    w = w_raw
    if not bounds:
        w *= 0.000244141
        if y > (bitmask * 0.5):
            y = -(bitmask - y)
        y *= 0.000122085
    else:
        y *= 0.000061039
        w *= 0.000061039
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_quat_zw(ivalue, bounds=None):
    bitmask = 0x3fff
    z_raw = ivalue & bitmask
    w_raw = (ivalue >> 14) & bitmask
    relframe = (ivalue >> 28) & 0xf
    x = 0.0
    y = 0.0
    z = z_raw
    w = w_raw
    if not bounds:
        w *= 0.000244141
        if z > (bitmask * 0.5):
            z = -(bitmask - z)
        z *= 0.000122085
    else:
        z *= 0.000061039
        w *= 0.000061039
        add, mult = bounds
        x = x * mult[0] + add[0]
        y = y * mult[1] + add[1]
        z = z * mult[2] + add[2]
        w = w * mult[3] + add[3]
    return (x, y, z, w), relframe

def unpack_vec3_16(i1, i2, i3, i4, bounds=None):
    x, y, z = float(i1), float(i2), float(i3)
    relframe = i4
    if bounds:
        add, mult = bounds
        x = (x / 65535.0) * mult[0] + add[0]
        y = (y / 65535.0) * mult[1] + add[1]
        z = (z / 65535.0) * mult[2] + add[2]
    return (x, y, z), relframe

class LMTDecoder:
    def __init__(self, data):
        self.data = data
        self.anims = []
        self.parse()
        
    def read_uint(self, offset):
        return struct.unpack('<I', self.data[offset:offset+4])[0]
        
    def read_float(self, offset):
        return struct.unpack('<f', self.data[offset:offset+4])[0]
        
    def parse(self):
        magic = self.data[0:4]
        if magic != b'LMT\x00':
            return
        self.version, animCount = struct.unpack('<HH', self.data[4:8])
        anim_offsets = [self.read_uint(8 + i * 4) for i in range(animCount)]
        
        for i, offset in enumerate(anim_offsets):
            if offset == 0:
                continue
            anim = self.parse_anim(offset, i)
            self.anims.append(anim)
            
    def parse_anim(self, offset, index):
        track_offset, track_count, frame_count, loop_frame = struct.unpack('<IIII', self.data[offset:offset+16])
        
        tracks = []
        for i in range(track_count):
            if self.version > 90:
                t_off = track_offset + i * 40
                buf_type, usage, joint, bone = struct.unpack('<BBBB', self.data[t_off:t_off+4])
                weight = self.read_float(t_off+4)
                buf_size = self.read_uint(t_off+8)
                buf_offset = self.read_uint(t_off+12)
                ref_x, ref_y, ref_z, ref_w = struct.unpack('<ffff', self.data[t_off+16:t_off+32])
                
                # BoneID in >90 is overridden by the 4-byte int at t_off+36
                bone = self.read_uint(t_off+36)
                extra = self.read_uint(t_off+32)
            else:
                t_off = track_offset + i * 36
                buf_type, usage, joint, bone = struct.unpack('<BBBB', self.data[t_off:t_off+4])
                weight = self.read_float(t_off+4)
                buf_size = self.read_uint(t_off+8)
                buf_offset = self.read_uint(t_off+12)
                ref_x, ref_y, ref_z, ref_w = struct.unpack('<ffff', self.data[t_off+16:t_off+32])
                extra = self.read_uint(t_off+32)

            bounds = None
            if extra > 0 and extra + 32 <= len(self.data):
                extent = struct.unpack('<4f', self.data[extra:extra+16])
                base = struct.unpack('<4f', self.data[extra+16:extra+32])
                bounds = (base, extent)

            frames = []
            
            # Read Buffer
            if buf_size > 0 and buf_offset > 0:
                cur_frame = 0
                ptr = buf_offset

                while ptr < buf_offset + buf_size:
                    if buf_type == 6: # LMTQuatFramev14
                        b = self.data[ptr:ptr+8]
                        ptr += 8
                        val, rel = unpack_quat_14(b, '<')
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        

                    elif buf_type == 4:
                        i1, i2, i3, i4 = struct.unpack('<HHHH', self.data[ptr:ptr+8])
                        ptr += 8
                        val, rel = unpack_vec3_16(i1, i2, i3, i4, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 11:
                        ivalue = struct.unpack('<I', self.data[ptr:ptr+4])[0]
                        ptr += 4
                        val, rel = unpack_quat_xw(ivalue, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 12:
                        ivalue = struct.unpack('<I', self.data[ptr:ptr+4])[0]
                        ptr += 4
                        val, rel = unpack_quat_yw(ivalue, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 13:
                        ivalue = struct.unpack('<I', self.data[ptr:ptr+4])[0]
                        ptr += 4
                        val, rel = unpack_quat_zw(ivalue, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                    elif buf_type == 14: # LMTQuatized11Quat
                        b = self.data[ptr:ptr+6]
                        ptr += 6
                        val, rel = unpack_quat_11(b, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 15: # LMTQuatized9Quat
                        b = self.data[ptr:ptr+5]
                        ptr += 5
                        val, rel = unpack_quat_9(b, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 5: # LMTQuatized8Vec3
                        i1 = struct.unpack('<I', self.data[ptr:ptr+4])[0]
                        ptr += 4
                        val, rel = unpack_vec3_8(i1, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 7: # LMTQuatized7Quat
                        b = self.data[ptr:ptr+4]
                        ptr += 4
                        val, rel = unpack_quat_7(b, bounds)
                        frames.append((cur_frame, val))
                        cur_frame += rel
                        
                    elif buf_type == 1: # LMTVec3 (Absolute?)
                        x, y, z = struct.unpack('<fff', self.data[ptr:ptr+12])
                        ptr += 12
                        val = (x, y, z)
                        frames.append((cur_frame, val))
                        cur_frame += 1
                        
                    else:
                        print(f"Unknown BufType {buf_type}")
                        break

            tracks.append({
                'buf_type': buf_type,
                'usage': usage,
                'joint': joint,
                'bone': bone,
                'weight': weight,
                'ref': (ref_x, ref_y, ref_z, ref_w),
                'frames': frames
            })
            
        return {'index': index, 'frame_count': frame_count, 'loop_frame': loop_frame, 'tracks': tracks}

def unpack_half(val):
    return struct.unpack('<e', struct.pack('<H', val))[0]

# --- Utils ---
def unpack_10_10_10_2(val):
    x = (val & 0x3FF)
    y = ((val >> 10) & 0x3FF)
    z = ((val >> 20) & 0x3FF)
    if x >= 512: x -= 1024
    if y >= 512: y -= 1024
    if z >= 512: z -= 1024
    l = math.sqrt(x*x + y*y + z*z)
    if l == 0: return (0, 0, 1)
    return (x / l, y / l, z / l)

# --- LMT Decoders ---
class LMTBounds:
    def __init__(self, addin, offset):
        self.addin = addin
        self.offset = offset
        
    def lerp3(self, fraction):
        return (
            self.offset[0] + fraction[0] * self.addin[0],
            self.offset[1] + fraction[1] * self.addin[1],
            self.offset[2] + fraction[2] * self.addin[2]
        )
        
    def lerpq(self, fraction):
        return (
            self.offset[0] + fraction[0] * self.addin[0],
            self.offset[1] + fraction[1] * self.addin[1],
            self.offset[2] + fraction[2] * self.addin[2],
            self.offset[3] + fraction[3] * self.addin[3]
        )

def decode_type5(f, bounds):
    x, y, z, relframe = struct.unpack('<BBBB', f.read(4))
    if bounds:
        val = bounds.lerp3((x/255.0, y/255.0, z/255.0))
    else:
        val = (x/255.0, y/255.0, z/255.0)
    return val, relframe

def decode_type6(f):
    v1, v2 = struct.unpack('<II', f.read(8))
    w = v1 & 0x3FFF
    z = (v1 >> 14) & 0x3FFF
    y = ((v1 >> 28) & 0xF) | ((v2 & 0x3FF) << 4)
    x = (v2 >> 10) & 0x3FFF
    relframe = (v2 >> 24) & 0xFF
    def dequantize(val):
        if val > 0x1FFF: val = -(0x3FFF - val)
        return val * 0.000244156
    return (dequantize(x), dequantize(y), dequantize(z), dequantize(w)), relframe

def decode_type7(f, bounds):
    val = struct.unpack('<I', f.read(4))[0]
    w = val & 0x7F
    z = (val >> 7) & 0x7F
    y = (val >> 14) & 0x7F
    x = (val >> 21) & 0x7F
    relframe = (val >> 28) & 0xF
    def dequantize(v): return (v - 8) * 0.0089285718
    w, x, y, z = dequantize(w), dequantize(x), dequantize(y), dequantize(z)
    if bounds:
        return bounds.lerpq((x, y, z, w)), relframe
    return (x, y, z, w), relframe

def decode_type11_12_13(f, bounds, mode):
    val = struct.unpack('<I', f.read(4))[0]
    v = val & 0x3FFF
    w = (val >> 14) & 0x3FFF
    relframe = (val >> 28) & 0xF
    if not bounds:
        w *= 0.000244141
        if v > 0x1FFF: v = -(0x3FFF - v)
        v *= 0.000122085
        if mode == 'X': return (v, 0, 0, w), relframe
        if mode == 'Y': return (0, v, 0, w), relframe
        if mode == 'Z': return (0, 0, v, w), relframe
    else:
        v *= 0.000061039
        w *= 0.000061039
        vec = [0, 0, 0, w]
        if mode == 'X': vec[0] = v
        elif mode == 'Y': vec[1] = v
        elif mode == 'Z': vec[2] = v
        return bounds.lerpq(vec), relframe

def decode_type14(f, bounds):
    v1, v2, v3 = struct.unpack('<HHH', f.read(6))
    x = v1 & 0x7FF
    y = (v2 & 0x3F) | ((v1 & 0xF800) >> 5)
    z = (v3 & 1) | ((v2 & 0xFFC0) >> 5)
    w = (v3 & 0x0FFE) >> 1
    relframe = (v3 & 0xF000) >> 12
    x *= 0.00048852
    y *= 0.00048852
    z *= 0.00048852
    w *= 0.00048852
    if bounds: return bounds.lerpq((x,y,z,w)), relframe
    return (x,y,z,w), relframe

def decode_type15(f, bounds):
    v1, v2, v3, v4, v5 = struct.unpack('<BBBBB', f.read(5))
    x = (v2 & 1) | (v1 << 1)
    y = (v3 & 3) | ((v2 & 0xFE) << 1)
    z = (v4 & 7) | ((v3 & 0xF8) << 1)
    w = (v5 & 0xF) | ((v4 & 0xE0) << 1)
    relframe = (v5 & 0xF0) >> 4
    x *= 0.00195695
    y *= 0.00195695
    z *= 0.00195695
    w *= 0.00195695
    if bounds: return bounds.lerpq((x,y,z,w)), relframe
    return (x,y,z,w), relframe

# --- File Parsers ---

def safe_half_to_int(h):
    val = unpack_half(h)
    if math.isnan(val) or math.isinf(val):
        return 0
    return int(val)

# Upper 20-bit prefix (block_hash >> 12) for vertex declarations in MT Framework (MTF\0..7.ms)
# whose vertex positions at v_data[0:12] are 3x IEEE-754 float32 (<fff) in unscaled model space.
FLOAT32_POS_PREFIXES = {
    0xa7d7d, 0x207d6, 0xd1a47, 0xc66fa, 0xa14e0, 0x2082f,
    0xd8297, 0x49b4f, 0x5e7f2, 0xafa63, 0x747d1, 0x12553,
    0x81890, 0x926fd, 0x9399c, 0xb86de, 0x63b6c, 0xb6681,
    0x37a4e, 0xc9690, 0x4325a,
    0x82917, 0x61803, 0x638f1, 0x3f788, 0x59dc4,
}

# Upper 20-bit prefix (block_hash >> 12) for vertex declarations whose vertex positions
# at v_data[0:6] are 3x normalized int16 (<hhh) scaled by vtbuffscale + bbmin.
INT16_POS_PREFIXES = {
    0xb0983, 0xdb7da, 0x0cb68, 0xa8fab, 0x01cb8, 0xcbf6c,
    0x667b1, 0xc9cfc, 0xc31f2, 0x6a2e1, 0xa0135, 0x0d9e8,
    0x14d40, 0xbde53, 0xa320c, 0xd8778, 0x77d87, 0xd86ca,
    0xda55a, 0x707fb, 0xb3921, 0xbb424, 0x12737, 0x75c3e,
    0xd84e3, 0x1b9a2, 0x64593, 0xcc510, 0xcbcf7,
}

def parse_mrl_file(mod_filepath, mat_names):
    """Parse companion .mrl (MRL v34) file to map MOD material names to texture basenames."""
    base_no_ext = os.path.splitext(mod_filepath)[0]
    mrl_path = None
    for ext in ('.mrl', '.MRL'):
        candidate = base_no_ext + ext
        if os.path.exists(candidate):
            mrl_path = candidate
            break
    if not mrl_path:
        return {}

    mrl_textures = {}
    try:
        with open(mrl_path, 'rb') as f:
            raw = f.read()
        if len(raw) < 28 or raw[:4] != b'MRL\x00':
            return {}
        magic, ver, mat_cnt, tex_cnt, unk, tex_off, mat_off = struct.unpack('<4sIIIIII', raw[:28])

        tex_names = []
        for i in range(tex_cnt):
            off = tex_off + i * 76
            if off + 76 > len(raw):
                break
            t_str = raw[off + 12:off + 76].split(b'\x00')[0].decode('ascii', errors='ignore')
            t_base = os.path.basename(t_str.replace('\\', '/'))
            tex_names.append(t_base)

        jamcrc_to_names = {}
        for name in mat_names:
            if not name:
                continue
            jcrc = (~zlib.crc32(name.encode('ascii'))) & 0xffffffff
            jamcrc_to_names.setdefault(jcrc, []).append(name)

        for i in range(mat_cnt):
            off = mat_off + i * 60
            if off + 60 > len(raw):
                break
            vals = struct.unpack('<15I', raw[off:off + 60])
            m_hash = vals[1]
            cmd_size = vals[2]
            cmd_off = vals[13]
            matched_names = jamcrc_to_names.get(m_hash)
            if not matched_names:
                continue

            bm_list = []
            nm_list = []
            mm_list = []
            all_list = []
            if cmd_off + cmd_size <= len(raw):
                for c in range(0, cmd_size - 11, 12):
                    w0, w1, w2 = struct.unpack('<III', raw[cmd_off + c:cmd_off + c + 12])
                    if (w0 & 0xfff) not in (0xdc0, 0xdc1, 0xdc2, 0xdc3):
                        break
                    if (w0 & 0xff) == 0xc3:
                        if 1 <= w1 <= len(tex_names):
                            t_name = tex_names[w1 - 1]
                            if t_name and t_name not in all_list:
                                all_list.append(t_name)
                            t_upper = t_name.upper()
                            if '_NM' in t_upper:
                                if t_name not in nm_list:
                                    nm_list.append(t_name)
                            elif '_MM' in t_upper or '_CM' in t_upper:
                                if t_name not in mm_list:
                                    mm_list.append(t_name)
                            elif '_BM' in t_upper or '_DM' in t_upper or '_AM' in t_upper:
                                if t_name not in bm_list:
                                    bm_list.append(t_name)

            if not bm_list:
                # Fallback: any non-normal/non-mask texture bound to this material
                for t_name in all_list:
                    if t_name not in nm_list and t_name not in mm_list:
                        bm_list.append(t_name)

            for m_name in matched_names:
                mrl_textures[m_name] = {
                    'BM': bm_list,
                    'NM': nm_list,
                    'MM': mm_list,
                    'ALL': all_list,
                }
    except Exception:
        pass
    return mrl_textures

def parse_mod_file(filepath, context):
    with open(filepath, 'rb') as f:
        data = f.read(4)
        magic = struct.unpack('<I', data)[0]
        if magic != 0x444f4d:
            raise ValueError(f"Invalid MOD file (Magic: {magic:x})")
        f.seek(4)
        v1, v2, boneCount, meshCount, matCount = struct.unpack('<BBHHH', f.read(8))
        
        f.seek(12)
        vtxCount, faceCount, vtxIds, vtxBufSize, secBufSize = struct.unpack('<IIIII', f.read(20))
        groupCount, bonesOff, groupOff, texOff, meshOff, vtxOff, facesOff, unkOff = struct.unpack('<IIIIIIII', f.read(32))

        mat_names = []
        f.seek(texOff)
        for _ in range(matCount):
            data = f.read(128)
            name = data.split(b'\x00')[0].decode('ascii', errors='ignore')
            mat_names.append(name)

        f.seek(80)
        bbmin_file = mathutils.Vector(struct.unpack('<fff', f.read(12)))
        f.seek(96)
        bbmax_file = mathutils.Vector(struct.unpack('<fff', f.read(12)))
        
        extents = bbmax_file - bbmin_file
        vt_scale = max(extents.x, extents.y, extents.z)

        # --- Bones ---
        bones = []
        f.seek(bonesOff)
        for i in range(boneCount):
            b_data = f.read(24)
            _id, _pid, _cid, _unk = struct.unpack('<BBBB', b_data[:4])
            bones.append({'id': i, 'parent': _pid, 'lmat': None, 'amat': None, 'bone_id': _id})

        lmat_offset = bonesOff + boneCount * 24
        f.seek(lmat_offset)

        for i in range(boneCount):
            mat_data = struct.unpack('<16f', f.read(64))
            lmat = mathutils.Matrix([mat_data[0:4], mat_data[4:8], mat_data[8:12], mat_data[12:16]]).transposed()
            bones[i]['lmat'] = lmat

        amat_offset = lmat_offset + boneCount * 64
        f.seek(amat_offset)
        for i in range(boneCount):
            mat_data = struct.unpack('<16f', f.read(64))
            amat = mathutils.Matrix([mat_data[0:4], mat_data[4:8], mat_data[8:12], mat_data[12:16]]).transposed()
            bones[i]['amat'] = amat

        if v1 < 190:
            scale = (vt_scale / 32767.0, vt_scale / 32767.0, vt_scale / 32767.0)
            offset = (bbmin_file.x, bbmin_file.y, bbmin_file.z)
        elif boneCount > 0:
            # MT Framework (LMT, MOD).ms port:
            # mHeader.vtbuffscale = mbones.amatrices[1].scale
            # mHeader.bbmin = mbones.amatrices[1].row4+mbones.lmatrices[1].row4
            sx = bones[0]['amat'].col[0].to_3d().length
            sy = bones[0]['amat'].col[1].to_3d().length
            sz = bones[0]['amat'].col[2].to_3d().length
            scale = (sx / 32767.0, sy / 32767.0, sz / 32767.0)
            
            t_amat = bones[0]['amat'].translation
            t_lmat = bones[0]['lmat'].translation
            offset = (t_amat.x + t_lmat.x, t_amat.y + t_lmat.y, t_amat.z + t_lmat.z)
        else:
            # MT Framework (LMT, MOD).ms: when v1 >= 190 and boneCount == 0:
            # mHeader.vtbuffscale = [1,1,1]; mHeader.bbmin = [0,0,0]
            scale = (1.0 / 32767.0, 1.0 / 32767.0, 1.0 / 32767.0)
            offset = (0.0, 0.0, 0.0)
            
        if boneCount > 0:
            remap_offset = amat_offset + boneCount * 64
            f.seek(remap_offset)
            remap_raw = f.read(256)
            if len(remap_raw) == 256:
                remap_table = struct.unpack('<256B', remap_raw)
            else:
                remap_table = tuple(range(256))
        else:
            remap_table = tuple(range(256))
        
        meshes = []
        f.seek(meshOff)
        for m in range(meshCount):
            m_data = f.read(48)
            v_count = struct.unpack('<H', m_data[2:4])[0]
            b_size = m_data[10]
            v_sub = struct.unpack('<I', m_data[12:16])[0]
            f_off = struct.unpack('<I', m_data[24:28])[0]
            f_count = struct.unpack('<I', m_data[28:32])[0]
            # 12-bit material index in MODMeshPartv2 (bits 4..15 of uint16 at m_data[5:7])
            m_mat = struct.unpack('<H', m_data[5:7])[0] >> 4
            mesh_type = m_data[1]
            render_priority = m_data[9]
            blocktype = m_data[11]
            block_hash = struct.unpack('<I', m_data[20:24])[0]
            single_bone = m_data[8]
            mesh_vtxOff = vtxOff + struct.unpack('<I', m_data[16:20])[0] + (b_size * v_sub)
            boneMapIdx = m_data[36]
            
            # MT Framework separates LMT remap_table (256 bytes) and Mesh boneMap (MODBoneRemap).
            # We don't currently parse MODBoneRemap, so we use an empty map (which falls back to global indices).
            b_map = []

            meshes.append({
                'id': m,
                'mat_idx': m_mat if (m_mat < len(mat_names) and mat_names[m_mat]) else 0,
                'mesh_type': mesh_type,
                'render_priority': render_priority,
                'vtxOff': mesh_vtxOff,
                'v_count': v_count,
                'stride': b_size,
                'vtxSub': v_sub,
                'faceOff': f_off,
                'faceCount': f_count,
                'boneMap': b_map,
                'blocktype': blocktype,
                'block_hash': block_hash,
                'single_bone': single_bone,
                'vertices': [],
                'normals': [],
                'indices': [],
                'uvs': [],
                'uvs2': [],
                'colors': [],
                'weights': [],
            })
            
        for mesh in meshes:
            stride = mesh['stride']
            block_hash = mesh['block_hash']
            pref = block_hash >> 12
            is_float_pos = (pref in FLOAT32_POS_PREFIXES) or (boneCount == 0 and pref not in INT16_POS_PREFIXES)
            has_uv2 = False

            f.seek(mesh['vtxOff'])
            for v in range(mesh['v_count']):
                v_data = f.read(stride)
                if len(v_data) < stride: break
                
                u, v_coord = 0.0, 0.0
                u2, v2_coord = 0.0, 0.0
                v_col = (1.0, 1.0, 1.0, 1.0)
                b_weights = []

                if is_float_pos:
                    # Static/scene/prop formats (MTF\0..7.ms): 3x float32 position at v_data[0:12]
                    fx, fy, fz = struct.unpack('<fff', v_data[0:12])
                    if pref in (0xa7d7d, 0x207d6, 0xd1a47, 0xc66fa, 0xa14e0, 0x2082f):
                        if stride >= 20:
                            u_h, v_h = struct.unpack('<HH', v_data[16:20])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if pref in (0xd1a47, 0xc66fa, 0xa14e0, 0x2082f) and stride >= 24:
                            u2_h, v2_h = struct.unpack('<HH', v_data[20:24])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        if pref == 0x207d6 and stride >= 24:
                            r, g, b, a = struct.unpack('<BBBB', v_data[20:24])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref == 0xa14e0 and stride >= 28:
                            r, g, b, a = struct.unpack('<BBBB', v_data[24:28])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    elif pref in (0x82917, 0x61803, 0x638f1, 0x3f788, 0x59dc4):
                        if stride >= 24:
                            u, v_raw = struct.unpack('<ff', v_data[16:24])
                            v_coord = 1.0 - v_raw
                        if pref == 0x59dc4 and stride >= 28:
                            r, g, b, a = struct.unpack('<BBBB', v_data[24:28])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref == 0x3f788 and stride >= 32:
                            r, g, b, a = struct.unpack('<BBBB', v_data[28:32])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    else:
                        # 0xd8297, 0x49b4f, 0x5e7f2, 0xafa63, 0x747d1, 0x12553, 0x81890,
                        # 0x926fd, 0x9399c, 0xb86de, 0x63b6c, 0xb6681, 0x37a4e, 0xc9690, 0x4325a
                        if stride >= 24:
                            u_h, v_h = struct.unpack('<HH', v_data[20:24])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if pref in (0x5e7f2, 0xafa63, 0x926fd, 0x9399c, 0xb86de, 0x63b6c, 0xb6681, 0xc9690) and stride >= 28:
                            u2_h, v2_h = struct.unpack('<HH', v_data[24:28])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        if block_hash == 0xd8297029 and stride >= 20:
                            r, g, b, a = struct.unpack('<BBBB', v_data[16:20])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref == 0x49b4f and stride >= 28:
                            r, g, b, a = struct.unpack('<BBBB', v_data[24:28])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref in (0x926fd, 0x9399c, 0xb86de, 0xb6681) and stride >= 32:
                            r, g, b, a = struct.unpack('<BBBB', v_data[28:32])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref == 0xc9690 and stride >= 40:
                            r, g, b, a = struct.unpack('<BBBB', v_data[36:40])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                else:
                    # Skinned / int16 formats (MTF\3..7.ms, plus Model20 0xcbf6c and Model37 0xa8fab)
                    hx, hy, hz = struct.unpack('<hhh', v_data[0:6])
                    fx = hx * scale[0] + offset[0]
                    fy = hy * scale[1] + offset[1]
                    fz = hz * scale[2] + offset[2]

                    if pref == 0xb0983:
                        b1 = struct.unpack('<H', v_data[6:8])[0]
                        b_weights.append((b1, 1.0))
                    elif pref == 0xdb7da:
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        b1, b2 = struct.unpack('<HH', v_data[12:16])
                        if w1 > 0: b_weights.append((b1, w1))
                        if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                        if not b_weights: b_weights.append((b1, 1.0))
                    elif pref == 0x0cb68:
                        b1, b2, b3, b4 = struct.unpack('<BBBB', v_data[8:12])
                        w1, w2, w3, w4 = struct.unpack('<BBBB', v_data[12:16])
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if w1 > 0: b_weights.append((b1, w1 / 255.0))
                        if w2 > 0: b_weights.append((b2, w2 / 255.0))
                        if w3 > 0: b_weights.append((b3, w3 / 255.0))
                        if w4 > 0: b_weights.append((b4, w4 / 255.0))
                    elif pref in (0xa8fab, 0x01cb8, 0x667b1, 0xc9cfc, 0xd8778, 0x707fb):
                        b1 = struct.unpack('<H', v_data[6:8])[0]
                        b_weights.append((b1, 1.0))
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if pref == 0xc9cfc and stride >= 24:
                            u2_h, v2_h = struct.unpack('<HH', v_data[20:24])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        elif pref in (0xd8778, 0x707fb) and stride >= 32:
                            u2_h, v2_h = struct.unpack('<HH', v_data[28:32])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        if pref == 0x707fb and stride >= 36:
                            r, g, b, a = struct.unpack('<BBBB', v_data[32:36])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    elif pref == 0xcbf6c:
                        # Model20 / PaintedModel05 (int16 pos, no vertex weights; uses mesh single_bone if rigged)
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if stride >= 24:
                            r, g, b, a = struct.unpack('<BBBB', v_data[20:24])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    elif pref in (0xc31f2, 0x6a2e1, 0xa0135, 0x0d9e8):
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        b1_h, b2_h = struct.unpack('<HH', v_data[20:24])
                        b1, b2 = safe_half_to_int(b1_h), safe_half_to_int(b2_h)
                        if w1 > 0: b_weights.append((b1, w1))
                        if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                        if pref == 0xa0135 and stride >= 28:
                            r, g, b, a = struct.unpack('<BBBB', v_data[24:28])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    elif pref == 0xcc510:
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        b1, b2, b3, b4 = struct.unpack('<BBBB', v_data[16:20])
                        w2_h, w3_h = struct.unpack('<HH', v_data[20:24])
                        w2, w3 = unpack_half(w2_h), unpack_half(w3_h)
                        u_h, v_h = struct.unpack('<HH', v_data[24:28])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if stride >= 40:
                            u2_h, v2_h = struct.unpack('<HH', v_data[36:40])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        if stride >= 44:
                            r, g, b, a = struct.unpack('<BBBB', v_data[40:44])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        w4 = 1.0 - w1 - w2 - w3
                        if w1 > 0: b_weights.append((b1, w1))
                        if w2 > 0: b_weights.append((b2, w2))
                        if w3 > 0: b_weights.append((b3, w3))
                        if w4 > 0: b_weights.append((b4, w4))
                    elif pref in (0x14d40, 0xbde53, 0x77d87, 0xd86ca, 0xda55a, 0x64593):
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        b1, b2, b3, b4 = struct.unpack('<BBBB', v_data[16:20])
                        u_h, v_h = struct.unpack('<HH', v_data[20:24])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        w2_h, w3_h = struct.unpack('<HH', v_data[24:28])
                        w2, w3 = unpack_half(w2_h), unpack_half(w3_h)
                        w4 = 1.0 - w1 - w2 - w3
                        if w1 > 0: b_weights.append((b1, w1))
                        if w2 > 0: b_weights.append((b2, w2))
                        if w3 > 0: b_weights.append((b3, w3))
                        if w4 > 0: b_weights.append((b4, w4))
                        if pref in (0x77d87, 0xd86ca) and stride >= 32:
                            r, g, b, a = struct.unpack('<BBBB', v_data[28:32])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                        elif pref == 0xda55a and stride >= 32:
                            u2_h, v2_h = struct.unpack('<HH', v_data[28:32])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        elif pref == 0x64593 and stride >= 36:
                            u2_h, v2_h = struct.unpack('<HH', v_data[32:36])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                    elif pref == 0xa320c:
                        bns = struct.unpack('<8B', v_data[8:16])
                        w_u8 = struct.unpack('<4B', v_data[16:20])
                        w5_h, w6_h = struct.unpack('<HH', v_data[20:24])
                        ws = [w / 255.0 for w in w_u8] + [unpack_half(w5_h), unpack_half(w6_h)]
                        for b_i, w_i in zip(bns[:6], ws):
                            if w_i > 0: b_weights.append((b_i, w_i))
                    elif pref in (0xb3921, 0x1b9a2):
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        b1_h, b2_h = struct.unpack('<HH', v_data[16:20])
                        b1, b2 = safe_half_to_int(b1_h), safe_half_to_int(b2_h)
                        if w1 > 0: b_weights.append((b1, w1))
                        if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                        u_h, v_h = struct.unpack('<HH', v_data[20:24])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        if pref == 0x1b9a2 and stride >= 36:
                            u2_h, v2_h = struct.unpack('<HH', v_data[32:36])
                            u2, v2_coord = unpack_half(u2_h), 1.0 - unpack_half(v2_h)
                            has_uv2 = True
                        if pref == 0x1b9a2 and stride >= 40:
                            r, g, b, a = struct.unpack('<BBBB', v_data[36:40])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    elif pref in (0xbb424, 0x12737, 0x75c3e, 0xd84e3, 0xcbcf7):
                        w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                        w2, w3, w4, w5 = [x / 255.0 for x in struct.unpack('<BBBB', v_data[12:16])]
                        bns = struct.unpack('<8B', v_data[16:24])
                        u_h, v_h = struct.unpack('<HH', v_data[24:28])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        w6_h, w7_h = struct.unpack('<HH', v_data[28:32])
                        w6, w7 = unpack_half(w6_h), unpack_half(w7_h)
                        w8 = 1.0 - (w1 + w2 + w3 + w4 + w5 + w6 + w7)
                        for b_i, w_i in zip(bns, [w1, w2, w3, w4, w5, w6, w7, w8]):
                            if w_i > 0: b_weights.append((b_i, w_i))
                        if pref == 0xd84e3 and stride >= 40:
                            r, g, b, a = struct.unpack('<BBBB', v_data[36:40])
                            v_col = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)
                    else:
                        # Fallback by stride for any unrecognized int16 vertex format
                        if stride == 12:
                            b1 = struct.unpack('<H', v_data[6:8])[0]
                            b_weights.append((b1, 1.0))
                        elif stride == 16:
                            b1 = struct.unpack('<H', v_data[12:14])[0]
                            b_weights.append((b1, 1.0))
                        elif stride == 20:
                            b1 = struct.unpack('<H', v_data[6:8])[0]
                            b_weights.append((b1, 1.0))
                            u_h, v_h = struct.unpack('<HH', v_data[16:20])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        elif stride == 24:
                            w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                            u_h, v_h = struct.unpack('<HH', v_data[16:20])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                            b1_h, b2_h = struct.unpack('<HH', v_data[20:24])
                            b1, b2 = safe_half_to_int(b1_h), safe_half_to_int(b2_h)
                            if w1 > 0: b_weights.append((b1, w1))
                            if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                        elif stride in (28, 32, 40, 44):
                            w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                            b1, b2, b3, b4 = struct.unpack('<BBBB', v_data[16:20])
                            u_h, v_h = struct.unpack('<HH', v_data[20:24])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                            w2_h, w3_h = struct.unpack('<HH', v_data[24:28])
                            w2, w3 = unpack_half(w2_h), unpack_half(w3_h)
                            w4 = 1.0 - w1 - w2 - w3
                            if w1 > 0: b_weights.append((b1, w1))
                            if w2 > 0: b_weights.append((b2, w2))
                            if w3 > 0: b_weights.append((b3, w3))
                            if w4 > 0: b_weights.append((b4, w4))
                        elif stride == 36:
                            w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                            b1_h, b2_h = struct.unpack('<HH', v_data[16:20])
                            b1, b2 = safe_half_to_int(b1_h), safe_half_to_int(b2_h)
                            if w1 > 0: b_weights.append((b1, w1))
                            if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                            u_h, v_h = struct.unpack('<HH', v_data[20:24])
                            u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                
                mesh['vertices'].append((fx, fy, fz))
                mesh['uvs'].append((u, v_coord))
                if has_uv2:
                    mesh['uvs2'].append((u2, v2_coord))
                mesh['colors'].append(v_col)
                mesh['weights'].append(b_weights)
            
            f.seek(facesOff + mesh['faceOff'] * 2)
            strip_indices = struct.unpack(f'<{mesh["faceCount"]}H', f.read(mesh["faceCount"] * 2))
            flip = False
            for i in range(len(strip_indices) - 2):
                i0, i1, i2 = strip_indices[i], strip_indices[i+1], strip_indices[i+2]
                if i0 == 65535 or i1 == 65535 or i2 == 65535:
                    flip = False
                    continue
                if i0 == i1 or i1 == i2 or i2 == i0:
                    flip = not flip
                    continue
                    
                if flip:
                    i0, i1, i2 = i0, i2, i1
                flip = not flip
                
                o0 = i0 - mesh['vtxSub']
                o1 = i1 - mesh['vtxSub']
                o2 = i2 - mesh['vtxSub']
                
                # Protect against out of bounds indices which crash Blender
                if o0 < 0 or o1 < 0 or o2 < 0 or o0 >= len(mesh['vertices']) or o1 >= len(mesh['vertices']) or o2 >= len(mesh['vertices']):
                    continue
                    
                mesh['indices'].append((o0, o1, o2))

        # Prevent Z-fighting on coplanar stage terrain transition/decal overlay meshes
        # (meshes with render_priority > 0 whose vertices coincide with lower-priority base meshes).
        if boneCount == 0 and any(m.get('render_priority', 0) > 0 for m in meshes):
            distinct_prios = sorted({m.get('render_priority', 0) for m in meshes})
            prio_to_rank = {p: idx for idx, p in enumerate(distinct_prios)}
            pos_normals = {}
            for m in sorted(meshes, key=lambda x: x.get('render_priority', 0)):
                verts = m['vertices']
                for o0, o1, o2 in m['indices']:
                    p0, p1, p2 = verts[o0], verts[o1], verts[o2]
                    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
                    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
                    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
                    for pt in (p0, p1, p2):
                        acc = pos_normals.get(pt)
                        if acc is None:
                            pos_normals[pt] = [nx, ny, nz]
                        else:
                            acc[0] += nx
                            acc[1] += ny
                            acc[2] += nz

            pts_by_prio = {}
            for m in meshes:
                pr = m.get('render_priority', 0)
                pts_by_prio.setdefault(pr, set()).update(m['vertices'])

            for m in meshes:
                pr = m.get('render_priority', 0)
                rank = prio_to_rank.get(pr, 0)
                if rank <= 0 or not m['vertices']:
                    continue
                lower_pts = set()
                for other_pr, pts in pts_by_prio.items():
                    if other_pr < pr:
                        lower_pts |= pts
                if not lower_pts:
                    continue
                unique_m_pts = set(m['vertices'])
                shared_cnt = len(unique_m_pts & lower_pts)
                if shared_cnt >= max(1, len(unique_m_pts) // 4):
                    disp = rank * 0.25
                    new_verts = []
                    for pt in m['vertices']:
                        n = pos_normals.get(pt)
                        if n:
                            nl = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
                            if nl > 1e-8:
                                new_verts.append((pt[0] + (n[0] / nl) * disp, pt[1] + (n[1] / nl) * disp, pt[2] + (n[2] / nl) * disp))
                                continue
                        new_verts.append((pt[0], pt[1] + disp, pt[2]))
                    m['vertices'] = new_verts
            
        return bones, meshes, remap_table, vt_scale, bbmin_file, mat_names

def parse_lmt_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    decoder = LMTDecoder(data)
    return decoder.anims

def build_blender_data(bones, meshes, remap_table, mat_names, filepath, name="MHGU_Model"):
    arm_data = bpy.data.armatures.new(f"{name}_Armature")
    arm_obj = bpy.data.objects.new(f"{name}_Armature", arm_data)
    arm_obj["remap_table"] = remap_table
    bpy.context.collection.objects.link(arm_obj)
    
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    edit_bones = {}
    eb_root = arm_data.edit_bones.new("Bone_255")
    eb_root.head = (0, 0, 0)
    eb_root.tail = (0, 0.05, 0)
    edit_bones[255] = eb_root
    
    for bone in bones:
        b_name = f"Bone_{bone['id']:03d}"
        eb = arm_data.edit_bones.new(b_name)
        eb.head = (0, 0, 0)
        eb.tail = (0, 0.05, 0)
        edit_bones[bone['id']] = eb
        
    fix_axis = mathutils.Matrix.Rotation(math.radians(90), 4, 'X')
    arm_obj.matrix_world = mathutils.Matrix.Identity(4)
    arm_obj.scale = (0.01, 0.01, 0.01)
    
    world_matrices = {255: mathutils.Matrix.Identity(4)}
    
    def get_world_mat(b_id):
        if b_id in world_matrices: return world_matrices[b_id]
        if b_id == 255: return mathutils.Matrix.Identity(4)
        bone = next((b for b in bones if b['id'] == b_id), None)
        if not bone: return mathutils.Matrix.Identity(4)
        p_mat = get_world_mat(bone['parent'])
        w_mat = p_mat @ bone['lmat']
        world_matrices[b_id] = w_mat
        return w_mat

    for bone in bones:
        eb = edit_bones[bone['id']]
        if bone['parent'] in edit_bones: eb.parent = edit_bones[bone['parent']]
        elif bone['parent'] == 255: eb.parent = edit_bones[255]
        w_mat = get_world_mat(bone['id'])
        eb.head = w_mat.translation
        eb.tail = w_mat @ mathutils.Vector((0, 0.5, 0))
        eb.matrix = fix_axis @ w_mat
        eb.length = 25.0
        eb.use_inherit_scale = False
        
    bpy.ops.object.mode_set(mode='OBJECT')
    
    mrl_textures = parse_mrl_file(filepath, mat_names)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    mod_dir = os.path.dirname(filepath)

    # Identify materials that use vertex-alpha gradients (e.g. terrain/cliff/water transition overlays)
    # vs materials with constant vertex alpha (e.g. trees, bushes, foliage cutouts).
    vcol_blend_mats = set()
    for md in meshes:
        m_idx = md['mat_idx']
        m_name = mat_names[m_idx] if (m_idx < len(mat_names) and mat_names[m_idx]) else f"Material_{m_idx}"
        cols = md.get('colors')
        if cols and min(c[3] for c in cols) < 0.98:
            vcol_blend_mats.add(m_name)

    for mesh_data in meshes:
        mesh_name = f"Mesh_{mesh_data['id']:03d}"
        bmesh_data = bpy.data.meshes.new(mesh_name)
        
        verts = [fix_axis @ mathutils.Vector(v) for v in mesh_data['vertices']]
        bmesh_data.from_pydata(verts, [], mesh_data['indices'])
        
        for p in bmesh_data.polygons: p.use_smooth = True
        bmesh_data.update()
        
        mesh_obj = bpy.data.objects.new(mesh_name, bmesh_data)
        mesh_obj.parent = arm_obj
        
        mat_idx = mesh_data['mat_idx']
        mesh_type = mesh_data.get('mesh_type', 0)
        
        if mat_idx < len(mat_names) and mat_names[mat_idx]:
            mat_name = mat_names[mat_idx]
        else:
            mat_name = f"Material_{mat_idx}"
            
        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
        else:
            mat = bpy.data.materials[mat_name]
            
        mat.use_nodes = True
        
        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bsdf = node
                break
                
        if bsdf:
            # Check if texture node already exists
            tex_node = None
            nm_tex_node = None
            nm_node = None
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    if tex_node is None:
                        tex_node = node
                    else:
                        nm_tex_node = node
                elif node.type == 'NORMAL_MAP':
                    nm_node = node
            
            if not tex_node:
                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex_node.location = (-300, 0)
                
            # Always link color
            mat.node_tree.links.new(tex_node.outputs[0], bsdf.inputs[0])
            
            # ONLY Link Alpha if material name implies transparency
            alpha_input = None
            for inp in bsdf.inputs:
                if inp.identifier == 'Alpha' or inp.name == 'Alpha':
                    alpha_input = inp
                    break
                    
            use_alpha = False
            parts = mat.name.split('_')
            if len(parts) > 0 and 'A' in parts[0]:
                use_alpha = True
            elif 'hair' in mat.name.lower() or 'fur' in mat.name.lower() or 'alpha' in mat.name.lower():
                use_alpha = True

            mrl_mat_info = mrl_textures.get(mat_name, {})
            bm_tex_names_lower = " ".join(mrl_mat_info.get('BM', [])).lower()
            is_smooth_blend = (
                (mat_name in vcol_blend_mats)
                or any(k in bm_tex_names_lower for k in ('suimen', 'mizu', 'taki', 'kumo', 'fog', 'smoke', 'glare', 'hikari', 'kage'))
            )
                
            if use_alpha and alpha_input and tex_node:
                vcol_node = mat.node_tree.nodes.get("MHGU_VCol")
                if not vcol_node:
                    vcol_node = mat.node_tree.nodes.new('ShaderNodeVertexColor')
                    vcol_node.name = "MHGU_VCol"
                    vcol_node.location = (-500, -50)
                vcol_node.layer_name = "Col"

                alpha_mul_node = mat.node_tree.nodes.get("MHGU_AlphaMul")
                if not alpha_mul_node:
                    alpha_mul_node = mat.node_tree.nodes.new('ShaderNodeMath')
                    alpha_mul_node.name = "MHGU_AlphaMul"
                    alpha_mul_node.location = (-150, -50)
                alpha_mul_node.operation = 'MULTIPLY'

                mat.node_tree.links.new(tex_node.outputs[1], alpha_mul_node.inputs[0])
                mat.node_tree.links.new(vcol_node.outputs[1], alpha_mul_node.inputs[1])
                mat.node_tree.links.new(alpha_mul_node.outputs[0], alpha_input)
                if is_smooth_blend:
                    # Smooth gradient transparency (terrain/water/mist transitions):
                    # show_transparent_back MUST be True so Eevee does not write Alpha=0 pixels to the depth buffer.
                    mat.blend_method = 'BLEND'
                    mat.shadow_method = 'HASHED'
                    mat.show_transparent_back = True
                else:
                    # Cutout transparency (trees, bushes, grass, monster wings/fur):
                    # CLIP discards Alpha < threshold fragments from the depth buffer while preserving exact Z-depth occlusion.
                    mat.blend_method = 'CLIP'
                    mat.alpha_threshold = 0.25
                    mat.shadow_method = 'CLIP'
                mat.use_backface_culling = True
            else:
                mat.blend_method = 'OPAQUE'
                mat.shadow_method = 'OPAQUE'
                if alpha_input and alpha_input.is_linked:
                    for link in list(alpha_input.links):
                        mat.node_tree.links.remove(link)
            
            if not nm_tex_node:
                nm_tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                nm_tex_node.location = (-600, -300)
                
                nm_node = mat.node_tree.nodes.new('ShaderNodeNormalMap')
                nm_node.location = (-300, -300)
                
                # Fix MT Framework BC5 Normal Maps (missing Z channel / Blue=0 causing black shading)
                sep_node = mat.node_tree.nodes.new('ShaderNodeSeparateColor')
                sep_node.location = (-500, -200)
                comb_node = mat.node_tree.nodes.new('ShaderNodeCombineColor')
                comb_node.location = (-400, -200)
                comb_node.inputs[2].default_value = 1.0 # Force Blue to 1.0
                
                mat.node_tree.links.new(nm_tex_node.outputs[0], sep_node.inputs[0])
                mat.node_tree.links.new(sep_node.outputs[0], comb_node.inputs[0])
                mat.node_tree.links.new(sep_node.outputs[1], comb_node.inputs[1])
                mat.node_tree.links.new(comb_node.outputs[0], nm_node.inputs[1])
            
            normal_input = None
            for inp in bsdf.inputs:
                if inp.identifier == 'Normal' or inp.name == 'Normal' or inp.name == '法向': # Check for Chinese UI compatibility
                    normal_input = inp
                    break

            mrl_mat_info = mrl_textures.get(mat_name, {})

            # Assign BM texture (try .png, .dds, .tex)
            if tex_node and tex_node.image and tex_node.image.filepath.endswith('.tex'):
                tex_node.image = None
                
            if not tex_node.image:
                bm_candidates = list(mrl_mat_info.get('BM', []))
                suffix_list = ['_BM', '_BM+A']
                mat_lower = mat.name.lower()
                if 'angry' in mat_lower or 'blood' in mat_lower:
                    suffix_list = ['_blood_BM', '_angry_BM'] + suffix_list
                if 'eye' in mat_lower:
                    suffix_list = ['_eye_BM'] + suffix_list
                for suffix in suffix_list:
                    cand = f"{base_name}{suffix}"
                    if cand not in bm_candidates:
                        bm_candidates.append(cand)

                for ext in ['.png', '.dds', '.tex']:
                    loaded = False
                    for cand in bm_candidates:
                        tex_path = os.path.join(mod_dir, f"{cand}{ext}")
                        if os.path.exists(tex_path):
                            try:
                                img = bpy.data.images.load(tex_path)
                                tex_node.image = img
                                loaded = True
                            except:
                                img = bpy.data.images.new(name=f"{cand}{ext}", width=1, height=1)
                                img.source = 'FILE'
                                img.filepath = tex_path
                                tex_node.image = img
                                loaded = True
                            break
                    if loaded:
                        break

            # Assign NM texture (try .png, .dds, .tex)
            if nm_tex_node and nm_tex_node.image and nm_tex_node.image.filepath.endswith('.tex'):
                nm_tex_node.image = None
                
            if nm_tex_node and not nm_tex_node.image:
                nm_candidates = list(mrl_mat_info.get('NM', []))
                for suffix in ['_NM', '_NM_MIRROR', '_NM_MQ_MIRROR']:
                    cand = f"{base_name}{suffix}"
                    if cand not in nm_candidates:
                        nm_candidates.append(cand)

                for ext in ['.png', '.dds', '.tex']:
                    loaded = False
                    for cand in nm_candidates:
                        tex_path = os.path.join(mod_dir, f"{cand}{ext}")
                        if os.path.exists(tex_path):
                            try:
                                img = bpy.data.images.load(tex_path)
                                img.colorspace_settings.name = 'Non-Color'
                                nm_tex_node.image = img
                                loaded = True
                            except:
                                img = bpy.data.images.new(name=f"{cand}{ext}", width=1, height=1)
                                img.source = 'FILE'
                                img.filepath = tex_path
                                try: img.colorspace_settings.name = 'Non-Color'
                                except: pass
                                nm_tex_node.image = img
                                loaded = True
                            break
                    if loaded:
                        break

            # Only link Normal Map node to BSDF Normal when a normal map image is present
            if normal_input and nm_node:
                if nm_tex_node and nm_tex_node.image:
                    mat.node_tree.links.new(nm_node.outputs[0], normal_input)
                elif normal_input.is_linked:
                    for link in list(normal_input.links):
                        mat.node_tree.links.remove(link)
        
        bmesh_data.materials.append(mat)
        
        modifier = mesh_obj.modifiers.new(type='ARMATURE', name="Armature")
        modifier.object = arm_obj
        
        for b in bones:
            mesh_obj.vertex_groups.new(name=f"Bone_{b['id']:03d}")
            
        for v_idx, w_data in enumerate(mesh_data['weights']):
            if not w_data:
                single_bone = mesh_data.get('single_bone', 0)
                b_map = mesh_data.get('boneMap', [])
                if single_bone < len(b_map) and b_map[single_bone] != 255:
                    mod_bone_id = b_map[single_bone]
                else:
                    mod_bone_id = single_bone
                
                if mod_bone_id < len(bones):
                    grp_name = f"Bone_{mod_bone_id:03d}"
                    if grp_name not in mesh_obj.vertex_groups:
                        mesh_obj.vertex_groups.new(name=grp_name)
                    mesh_obj.vertex_groups[grp_name].add([v_idx], 1.0, 'REPLACE')
                continue

            for b_id, w_val in w_data:
                # Map the local mesh bone index to the global bone index using boneMap
                b_map = mesh_data.get('boneMap', [])
                if b_id < len(b_map) and b_map[b_id] != 255:
                    mod_bone_id = b_map[b_id]
                else:
                    mod_bone_id = b_id
                
                if mod_bone_id < len(bones) and w_val > 0:
                    grp_name = f"Bone_{mod_bone_id:03d}"
                    if grp_name not in mesh_obj.vertex_groups:
                        mesh_obj.vertex_groups.new(name=grp_name)
                    mesh_obj.vertex_groups[grp_name].add([v_idx], w_val, 'REPLACE')
        
        if bmesh_data.loops:
            uv_layer = bmesh_data.uv_layers.new(name="UVMap")
            for loop in bmesh_data.loops:
                uv_layer.data[loop.index].uv = mesh_data['uvs'][loop.vertex_index]
            if mesh_data.get('uvs2') and len(mesh_data['uvs2']) == len(mesh_data['vertices']):
                uv2_layer = bmesh_data.uv_layers.new(name="UVMap2")
                for loop in bmesh_data.loops:
                    uv2_layer.data[loop.index].uv = mesh_data['uvs2'][loop.vertex_index]
            if mesh_data.get('colors') and len(mesh_data['colors']) == len(mesh_data['vertices']):
                vcol_layer = bmesh_data.vertex_colors.new(name="Col")
                for loop in bmesh_data.loops:
                    vcol_layer.data[loop.index].color = mesh_data['colors'][loop.vertex_index]
        
        bpy.context.collection.objects.link(mesh_obj)
        
    bpy.ops.object.mode_set(mode='POSE')
    remap_table = arm_obj["remap_table"]
    for i, mod_bone_id in enumerate(remap_table):
        if mod_bone_id < len(bones) and mod_bone_id != 255:
            bone_name = f"Bone_{mod_bone_id:03d}"
            if bone_name in arm_obj.pose.bones:
                arm_obj.pose.bones[bone_name]['LMT_Bone'] = i
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return arm_obj

def get_lmat(pb):
    fix_axis = mathutils.Matrix.Rotation(math.radians(90), 4, 'X')
    if pb.parent:
        return pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
    else:
        return fix_axis.inverted() @ pb.bone.matrix_local

def apply_lmt_to_armature(arm_obj, animations, lmt_filename=""):
    if not arm_obj.animation_data:
        arm_obj.animation_data_create()

    remap_table = arm_obj.get('remap_table', list(range(256)))
    lmt_to_bone_name = {}
    for lmt_id, bone_index in enumerate(remap_table):
        if bone_index == 255:
            continue
        bone_name = f'Bone_{bone_index:03d}'
        if bone_name in arm_obj.pose.bones:
            lmt_to_bone_name[lmt_id] = bone_name

    import os
    for anim in animations:
        if lmt_filename:
            base_name = os.path.splitext(os.path.basename(lmt_filename))[0]
            action_name = f"{base_name}.{anim['index']:02d}"
        else:
            action_name = f"Anim_{anim['index']:02d}"
        action = bpy.data.actions.new(name=action_name)
        arm_obj.animation_data.action = action

        for pb in arm_obj.pose.bones:
            pb.rotation_mode = 'QUATERNION'

        loop_frame = anim.get('loop_frame', 0)
        frame_count = anim.get('frame_count', 999999)
        for track in anim['tracks']:
            if track['bone'] == 4294967295 or track['bone'] == 255:
                bone_name = 'Bone_255'
            else:
                if track['bone'] not in lmt_to_bone_name: continue
                bone_name = lmt_to_bone_name[track['bone']]

            if bone_name not in arm_obj.pose.bones:
                continue
            pb = arm_obj.pose.bones[bone_name]

            data_path = ""
            is_quat = False

            if track['usage'] == 1:
                data_path = "location"
            elif track['usage'] in (0, 3):
                data_path = "rotation_quaternion"
                is_quat = True
            elif track['usage'] == 2:
                data_path = "scale"
            else:
                continue

            frames_to_process = track['frames']
            if not frames_to_process:
                frames_to_process = [(0, track['ref'])]

            prev_q = None
            prev_frame = -1.0

            for f in frames_to_process:
                frame = float(f[0])
                if frame <= prev_frame:
                    frame = prev_frame + 0.01
                prev_frame = frame
                value = f[1]
                if is_quat:
                    x, y, z, w = value
                    
                    # Exact mapping, no negation. The local space is invariant under the global X90 rotation.
                    final_q = mathutils.Quaternion((w, x, y, z))
                    
                    if final_q.magnitude > 0.0001:
                        final_q.normalize()

                    if prev_q is not None and prev_q.dot(final_q) < 0:
                        final_q.negate()

                    pb.rotation_quaternion = final_q
                    prev_q = final_q.copy()
                elif track['usage'] in (1, 4, 5):
                    if len(value) >= 3:
                        pb.location = mathutils.Vector((value[0], value[1], value[2]))
                elif track['usage'] == 2:
                    if len(value) >= 3:
                        pb.scale = (value[0], value[1], value[2])
                
                pb.keyframe_insert(data_path=data_path, frame=frame)

                # Stop adding frames if we have passed the animation's designated frame count.
                # This prevents baked physics loops from continuing indefinitely.
                if frame > frame_count:
                    break

        # Make all interpolation linear to avoid bezier overshoot
        if action.fcurves:
            for fcurve in action.fcurves:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = 'LINEAR'

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator

class ImportMHGUMod(Operator, ImportHelper):
    """Import MHGU Model File"""
    bl_idname = "import_scene.mhgu_mod"
    bl_label = "Import MHGU Model"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".mod"
    filter_glob: StringProperty(
        default="*.mod",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        try:
            bones, meshes, remap_table, vt_scale, bbmin_file, mat_names = parse_mod_file(self.filepath, context)
            name = os.path.splitext(os.path.basename(self.filepath))[0]
            build_blender_data(bones, meshes, remap_table, mat_names, self.filepath, name)
            self.report({'INFO'}, "Successfully imported MHGU Model.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error parsing MOD file: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

class ImportMHGULmt(Operator, ImportHelper):
    """Import MHGU Animation File"""
    bl_idname = "import_scene.mhgu_lmt"
    bl_label = "Import MHGU Animation"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".lmt"
    filter_glob: StringProperty(
        default="*.lmt",
        options={'HIDDEN'},
        maxlen=255,
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        arm_obj = context.active_object
        
        # Try to robustly find the armature
        if arm_obj and arm_obj.type == 'MESH' and arm_obj.parent and arm_obj.parent.type == 'ARMATURE':
            arm_obj = arm_obj.parent
        elif arm_obj and arm_obj.type != 'ARMATURE':
            for obj in context.selected_objects:
                if obj.type == 'ARMATURE':
                    arm_obj = obj
                    break
            else:
                armatures = [obj for obj in context.scene.objects if obj.type == 'ARMATURE']
                if len(armatures) == 1:
                    arm_obj = armatures[0]
                else:
                    self.report({'ERROR'}, "Please select an Armature before importing LMT.")
                    return {'CANCELLED'}
        elif not arm_obj:
            armatures = [obj for obj in context.scene.objects if obj.type == 'ARMATURE']
            if len(armatures) == 1:
                arm_obj = armatures[0]
            else:
                self.report({'ERROR'}, "Please select an Armature before importing LMT.")
                return {'CANCELLED'}
                
        try:
            animations = parse_lmt_file(self.filepath)
            apply_lmt_to_armature(arm_obj, animations, self.filepath)
            self.report({'INFO'}, f"Successfully imported LMT: {len(animations)} animations.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error parsing LMT file: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}

def menu_func_import_mod(self, context):
    self.layout.operator(ImportMHGUMod.bl_idname, text="MHGU Model (.mod)")

def menu_func_import_lmt(self, context):
    self.layout.operator(ImportMHGULmt.bl_idname, text="MHGU Animation (.lmt)")

def register():
    bpy.utils.register_class(ImportMHGUMod)
    bpy.utils.register_class(ImportMHGULmt)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mod)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_lmt)

def unregister():
    bpy.utils.unregister_class(ImportMHGUMod)
    bpy.utils.unregister_class(ImportMHGULmt)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_mod)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_lmt)

if __name__ == '__main__':
    register()
