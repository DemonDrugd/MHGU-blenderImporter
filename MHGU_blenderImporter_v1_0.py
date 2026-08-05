bl_info = {
    "name": "MHGU-blenderImporter",
    "author": "DemonDrug",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "description": "Import Monster Hunter Generations Ultimate .mod and .lmt files",
    "category": "Import-Export"
}

# MHGU MTFramework tools for Blender

import bpy
import bmesh
import struct
import math
import mathutils
import os


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
        scale = (vt_scale / 32767.0, vt_scale / 32767.0, vt_scale / 32767.0)
        offset = (bbmin_file.x, bbmin_file.y, bbmin_file.z)
        
        f.seek(12)
        vtxCount, faceCount, vtxIds, vtxBufSize, secBufSize = struct.unpack('<IIIII', f.read(20))
        groupCount, bonesOff, groupOff, texOff, meshOff, vtxOff, facesOff, unkOff = struct.unpack('<IIIIIIII', f.read(32))

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

        if v1 >= 190 and boneCount > 0:
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
            
        remap_offset = amat_offset + boneCount * 64
        
        f.seek(remap_offset)
        remap_table = struct.unpack(f'<{256}B', f.read(256))
        
        meshes = []
        f.seek(meshOff)
        for m in range(meshCount):
            m_data = f.read(48)
            v_count = struct.unpack('<H', m_data[2:4])[0]
            b_size = m_data[10]
            v_sub = struct.unpack('<I', m_data[12:16])[0]
            f_off = struct.unpack('<I', m_data[24:28])[0]
            f_count = struct.unpack('<I', m_data[28:32])[0]
            m_mat = m_data[5] >> 4
            mesh_type = m_data[1]
            blocktype = m_data[11]
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
                'vtxOff': mesh_vtxOff,
                'v_count': v_count,
                'stride': b_size,
                'vtxSub': v_sub,
                'faceOff': f_off,
                'faceCount': f_count,
                'boneMap': b_map,
                'blocktype': blocktype,
                'single_bone': single_bone,
                'vertices': [],
                'normals': [],
                'indices': [],
                'uvs': [],
                'weights': [],
            })
            
        for mesh in meshes:
            stride = mesh['stride']
            f.seek(mesh['vtxOff'])
            for v in range(mesh['v_count']):
                v_data = f.read(stride)
                if len(v_data) < stride: break
                
                hx, hy, hz = struct.unpack('<hhh', v_data[0:6])
                fx = hx * scale[0] + offset[0]
                fy = hy * scale[1] + offset[1]
                fz = hz * scale[2] + offset[2]

                u, v_coord = 0.0, 0.0
                b_weights = []
                
                if stride == 12:
                    b1 = struct.unpack('<H', v_data[6:8])[0]
                    b_weights.append((b1, 1.0))
                elif stride == 16:
                    b1 = struct.unpack('<H', v_data[12:14])[0]
                    b_weights.append((b1, 1.0))
                elif stride == 32:
                    b1 = struct.unpack('<H', v_data[6:8])[0]
                    u_h, v_h = struct.unpack('<HH', v_data[16:20])
                    u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                    b_weights.append((b1, 1.0))
                elif stride == 36:
                    w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                    b1_h, b2_h = struct.unpack('<HH', v_data[16:20])
                    b1, b2 = int(unpack_half(b1_h)), int(unpack_half(b2_h))
                    if w1 > 0: b_weights.append((b1, w1))
                    if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                    u_h, v_h = struct.unpack('<HH', v_data[20:24])
                    u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                elif stride == 20:
                    if mesh['blocktype'] == 196:
                        b1, b2, b3, b4 = struct.unpack('<BBBB', v_data[8:12])
                        w1, w2, w3, w4 = struct.unpack('<BBBB', v_data[12:16])
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                        
                        if w1 > 0: b_weights.append((b1, w1 / 255.0))
                        if w2 > 0: b_weights.append((b2, w2 / 255.0))
                        if w3 > 0: b_weights.append((b3, w3 / 255.0))
                        if w4 > 0: b_weights.append((b4, w4 / 255.0))
                    else:
                        b1 = struct.unpack('<H', v_data[6:8])[0]
                        b_weights.append((b1, 1.0))
                        u_h, v_h = struct.unpack('<HH', v_data[16:20])
                        u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                elif stride == 40:
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
                elif stride == 24:
                    w1 = struct.unpack('<h', v_data[6:8])[0] / 32767.0
                    u_h, v_h = struct.unpack('<HH', v_data[16:20])
                    u, v_coord = unpack_half(u_h), 1.0 - unpack_half(v_h)
                    b1_h, b2_h = struct.unpack('<HH', v_data[20:24])
                    b1, b2 = int(unpack_half(b1_h)), int(unpack_half(b2_h))
                    if w1 > 0: b_weights.append((b1, w1))
                    if 1.0 - w1 > 0: b_weights.append((b2, 1.0 - w1))
                elif stride == 28:
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
                
                mesh['vertices'].append((fx, fy, fz))
                mesh['uvs'].append((u, v_coord))
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
        
        if mat_idx < len(mat_names):
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
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    if tex_node is None:
                        tex_node = node
                    else:
                        nm_tex_node = node
            
            if not tex_node:
                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex_node.location = (-300, 0)
                
            # Always link color
            mat.node_tree.links.new(tex_node.outputs[0], bsdf.inputs[0])
            
            # ONLY Link Alpha and use CLIP if material name implies transparency
            alpha_input = None
            for inp in bsdf.inputs:
                if inp.identifier == 'Alpha' or inp.name == 'Alpha':
                    alpha_input = inp
                    break
                    
            use_alpha = False
            parts = mat.name.split('_')
            if len(parts) > 0 and 'A' in parts[0]:
                use_alpha = True
            elif 'hair' in mat.name.lower() or 'fur' in mat.name.lower():
                use_alpha = True
                
            if use_alpha and alpha_input and tex_node:
                mat.node_tree.links.new(tex_node.outputs[1], alpha_input)
                mat.blend_method = 'BLEND'
                mat.shadow_method = 'CLIP'
            else:
                mat.blend_method = 'OPAQUE'
                mat.shadow_method = 'OPAQUE'
                if alpha_input and alpha_input.is_linked:
                    for link in alpha_input.links:
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
                
                # Link to BSDF Normal
                normal_input = None
                for inp in bsdf.inputs:
                    if inp.identifier == 'Normal' or inp.name == 'Normal' or inp.name == '法向': # Check for Chinese UI compatibility
                        normal_input = inp
                        break
                if normal_input:
                    mat.node_tree.links.new(nm_node.outputs[0], normal_input)
            
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            mod_dir = os.path.dirname(filepath)
            
            # Assign BM texture (try .png, .dds, .tex)
            if tex_node and tex_node.image and tex_node.image.filepath.endswith('.tex'):
                tex_node.image = None
                
            if not tex_node.image:
                for ext in ['.png', '.dds', '.tex']:
                    loaded = False
                    for suffix in ['_BM', '_BM+A']:
                        tex_path = os.path.join(mod_dir, f"{base_name}{suffix}{ext}")
                        if os.path.exists(tex_path):
                            try:
                                img = bpy.data.images.load(tex_path)
                                tex_node.image = img
                                loaded = True
                            except:
                                img = bpy.data.images.new(name=f"{base_name}{suffix}{ext}", width=1, height=1)
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
                for ext in ['.png', '.dds', '.tex']:
                    loaded = False
                    for suffix in ['_NM', '_NM_MIRROR', '_NM_MQ_MIRROR']:
                        tex_path = os.path.join(mod_dir, f"{base_name}{suffix}{ext}")
                        if os.path.exists(tex_path):
                            try:
                                img = bpy.data.images.load(tex_path)
                                img.colorspace_settings.name = 'Non-Color'
                                nm_tex_node.image = img
                                loaded = True
                            except:
                                img = bpy.data.images.new(name=f"{base_name}{suffix}{ext}", width=1, height=1)
                                img.source = 'FILE'
                                img.filepath = tex_path
                                try: img.colorspace_settings.name = 'Non-Color'
                                except: pass
                                nm_tex_node.image = img
                                loaded = True
                            break
                    if loaded:
                        break
        
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
