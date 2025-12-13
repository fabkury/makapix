import json
from enum import Enum
from io import IOBase
from struct import unpack

import numpy as np
import lzallright
from Crypto.Cipher import AES
import io
from typing import List, Tuple
from PIL import Image

try:
    from .pixel_bean import PixelBean
except ImportError:  # Running outside the package layout
    from pixel_bean import PixelBean


class FileFormat(Enum):
    PIC_MULTIPLE = 17
    ANIM_SINGLE = 9  # 16x16
    ANIM_MULTIPLE = 18  # 32x32 or 64x64
    ANIM_MULTIPLE_64 = 26  # 64x64 or 128x128
    ANIM_FORMAT_0x1F = 31  # Unknown format 31 (0x1F)
    ANIM_FORMAT_0x29 = 41  # Unknown format 41 (0x29) - JPEG sequence animations at 256x256
    ANIM_CONTAINER_ZSTD = 42  # 256x256: zstd-compressed raw RGB frames
    ANIM_EMBEDDED_IMAGE = 43  # 256x256: embedded GIF/WEBP container


class BaseDecoder(object):
    AES_SECRET_KEY = '78hrey23y28ogs89'
    AES_IV = '1234567890123456'.encode('utf8')

    def __init__(self, fp: IOBase):
        self._fp = fp
        self._lzo = lzallright.LZOCompressor()

    def decode() -> PixelBean:
        raise Exception('Not implemented!')

    def _decrypt_aes(self, data):
        cipher = AES.new(
            self.AES_SECRET_KEY.encode('utf8'),
            AES.MODE_CBC,
            self.AES_IV,
        )
        return cipher.decrypt(data)

    def _compact(self, frames_data, total_frames, row_count=1, column_count=1):
        """
        Convert raw frame data to numpy arrays with RGB values.
        
        Args:
            frames_data: List of raw frame bytes (RGB data)
            total_frames: Number of frames
            row_count: Number of 16x16 tile rows
            column_count: Number of 16x16 tile columns
            
        Returns:
            List of numpy arrays, each with shape (height, width, 3)
        """
        frame_size = row_count * column_count * 16 * 16 * 3
        width = column_count * 16
        height = row_count * 16
        
        frames_arrays = []

        for current_frame, frame_data in enumerate(frames_data):
            # Create numpy array for this frame (height, width, 3)
            frame_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            pos = 0
            x = 0
            y = 0
            grid_x = 0
            grid_y = 0

            while pos < frame_size:
                r, g, b = unpack('BBB', frame_data[pos : pos + 3])
                
                real_x = x + (grid_x * 16)
                real_y = y + (grid_y * 16)
                
                # Store RGB values directly in numpy array
                frame_array[real_y, real_x] = [r, g, b]

                x += 1
                pos += 3
                if (pos / 3) % 16 == 0:
                    x = 0
                    y += 1

                if (pos / 3) % 256 == 0:
                    x = 0
                    y = 0
                    grid_x += 1

                    if grid_x == row_count:
                        grid_x = 0
                        grid_y += 1
            
            frames_arrays.append(frame_array)

        return frames_arrays


class AnimSingleDecoder(BaseDecoder):
    def decode(self) -> PixelBean:
        content = b'\x00' + self._fp.read()  # Add back the first byte (file type)

        # Re-arrange data
        encrypted_data = bytearray(len(content) - 4)
        for i in range(len(content)):
            encrypted_data[i - 4] = content[i]

        row_count = 1
        column_count = 1
        speed = unpack('>H', content[2:4])[0]

        # Decrypt AES
        decrypted_data = self._decrypt_aes(encrypted_data)
        total_frames = len(decrypted_data) // 768

        # Parse frames data
        frames_data = []
        for i in range(total_frames):
            pos = i * 768
            frames_data.append(decrypted_data[pos : pos + 768])

        # Convert to numpy arrays
        frames_arrays = self._compact(frames_data, total_frames)

        return PixelBean(
            total_frames,
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class AnimMultiDecoder(BaseDecoder):
    def decode(self) -> PixelBean:
        total_frames, speed, row_count, column_count = unpack('>BHBB', self._fp.read(5))
        encrypted_data = self._fp.read()

        return self._decode_frames_data(
            encrypted_data, total_frames, speed, row_count, column_count
        )

    def _decode_frames_data(
        self, encrypted_data, total_frames, speed, row_count, column_count
    ):
        width = 16 * column_count
        height = 16 * row_count

        data = self._decrypt_aes(encrypted_data)
        uncompressed_frame_size = width * height * 3
        pos = 0

        frames_data = [] * total_frames
        for current_frame in range(total_frames):
            frame_size = unpack('>I', data[pos : pos + 4])[0]
            pos += 4

            frame_data = self._lzo.decompress(
                data[pos : pos + frame_size], uncompressed_frame_size
            )
            pos += frame_size

            frames_data.append(frame_data)

        frames_arrays = self._compact(
            frames_data, total_frames, row_count, column_count
        )

        return PixelBean(
            total_frames,
            speed,
            row_count,
            column_count,
            frames_arrays,
        )



class Decoder0x1A(BaseDecoder):
    """Decoder for format 0x1A (26 decimal) - 64x64 and 128x128 animations with multiple encryption types."""
    
    def _get_dot_info(self, data, pos, pixel_idx, bVar9):
        """Extract pixel color index from compressed data (for 0x0C encryption)."""
        if pos >= len(data):
            return -1

        uVar2 = bVar9 * pixel_idx & 7
        uVar4 = bVar9 * pixel_idx * 65536 >> 0x13

        if bVar9 < 9:
            uVar3 = bVar9 + uVar2
            if uVar3 < 9:
                idx = pos + uVar4
                if idx >= len(data):
                    return -1
                uVar6 = data[idx] << (8 - uVar3 & 0xFF) & 0xFF
                uVar6 >>= uVar2 + (8 - uVar3) & 0xFF
            else:
                idx1 = pos + uVar4 + 1
                idx0 = pos + uVar4
                if idx1 >= len(data) or idx0 >= len(data):
                    return -1
                uVar6 = data[idx1] << (0x10 - uVar3 & 0xFF) & 0xFF
                uVar6 >>= 0x10 - uVar3 & 0xFF
                uVar6 &= 0xFFFF
                uVar6 <<= 8 - uVar2 & 0xFF
                uVar6 |= data[idx0] >> uVar2
        else:
            raise Exception('(2) Unimplemented')

        return uVar6

    def _decode_frame_data_0x0c(self, data):
        """Decode a single frame with 0x0C encryption type."""
        if len(data) < 8:
            raise Exception(f'Frame data too short: {len(data)} bytes')
        
        output = [None] * 12288  # 64x64 * 3 channels
        encrypt_type = data[5]
        if encrypt_type != 0x0C:
            raise Exception(f'Expected 0x0C encryption, got 0x{encrypt_type:02X}')

        uVar13 = data[6]
        iVar11 = uVar13 * 3

        if uVar13 == 0:
            bVar9 = 8
            iVar11 = 768  # Fix corrupted frame
        else:
            bVar9 = 0xFF
            bVar15 = 1
            while True:
                if (uVar13 & 1) != 0:
                    bVar18 = bVar9 == 0xFF
                    bVar9 = bVar15
                    if bVar18:
                        bVar9 = bVar15 - 1

                uVar14 = uVar13 & 0xFFFE
                bVar15 = bVar15 + 1
                uVar13 = uVar14 >> 1
                if uVar14 == 0:
                    break

        pixel_idx = 0
        pos = (iVar11 + 8) & 0xFFFF

        while True:
            color_index = self._get_dot_info(data, pos, pixel_idx & 0xFFFF, bVar9)

            target_pos = pixel_idx * 3
            if color_index == -1:  # transparent -> black
                output[target_pos] = 0
                output[target_pos + 1] = 0
                output[target_pos + 2] = 0
            else:
                color_pos = 8 + color_index * 3
                
                # Bounds check for palette access
                if color_pos + 2 < len(data):
                    output[target_pos] = data[color_pos]
                    output[target_pos + 1] = data[color_pos + 1]
                    output[target_pos + 2] = data[color_pos + 2]
                else:
                    # Out of bounds - use black
                    output[target_pos] = 0
                    output[target_pos + 1] = 0 
                    output[target_pos + 2] = 0

            pixel_idx += 1
            if pixel_idx == 4096:  # 64x64
                break

        return bytearray(output)
    
    def decode(self) -> PixelBean:
        """Decode the animation file and return a PixelBean."""
        # Read container header (5 bytes)
        header_bytes = self._fp.read(5)
        total_frames = header_bytes[0]
        speed = unpack('>H', header_bytes[1:3])[0]
        row_count = header_bytes[3]
        column_count = header_bytes[4]
        
        # Calculate actual dimensions
        width = column_count * 16
        height = row_count * 16
        
        # Read all remaining frame data
        all_frame_data = self._fp.read()
        
        # Detect format by checking first frame structure
        # For 0x0C: 4-byte size + frame_data (where frame_data[5] == 0x0C)
        # For 0x11/0x13/0x15: 4-byte header + 0xAA marker at byte 4
        uses_0x0c_format = False
        if len(all_frame_data) >= 10:
            # Check if byte at position 4 is 0xAA marker (0x11/0x13/0x15 format)
            # If not, check if this might be 0x0C format
            if all_frame_data[4] != 0xAA:
                # Could be 0x0C format - try to verify
                # Read first frame size and check if encryption type at position 9 is 0x0C
                first_frame_size = unpack('>I', all_frame_data[0:4])[0]
                if 0 < first_frame_size < len(all_frame_data):
                    # In 0x0C format, frame data starts at byte 4
                    # Frame data has structure: [0-4: header, 5: encrypt_type, ...]
                    # So encrypt_type is at all_frame_data[4 + 5] = all_frame_data[9]
                    if all_frame_data[9] == 0x0C:
                        uses_0x0c_format = True
        
        frames_rgb = []
        
        if uses_0x0c_format:
            # Decode 0x0C format frames (AnimMulti64Decoder logic)
            pos = 0
            for frame_idx in range(total_frames):
                if pos + 4 > len(all_frame_data):
                    break
                
                try:
                    # Read 4-byte frame size (big-endian)
                    size = unpack('>I', all_frame_data[pos:pos + 4])[0]
                    pos += 4
                    
                    if pos + size > len(all_frame_data):
                        break
                    
                    # Extract frame data (size bytes)
                    frame_data = all_frame_data[pos:pos + size]
                    
                    # Decode the frame using 0x0C decoder
                    decoded_frame = self._decode_frame_data_0x0c(frame_data)
                    frames_rgb.append(decoded_frame)
                    
                    pos += size
                    
                except Exception as e:
                    # Frame has incomplete or invalid data
                    if frames_rgb:
                        frames_rgb.append(frames_rgb[-1])
                    else:
                        blank_img = Image.new('RGB', (width, height), (0, 0, 0))
                        frames_rgb.append(blank_img.tobytes())
                    break
        else:
            # Decode 0x11/0x13/0x15 format frames (with 0xAA marker)
            pos = 0
            shared_palette: List[Tuple[int, int, int]] = []
            
            for frame_idx in range(total_frames):
                if pos >= len(all_frame_data):
                    break
                
                try:
                    # Skip 4-byte frame header, then find 0xAA marker
                    idx = pos + 4
                    if idx >= len(all_frame_data):
                        break

                    if all_frame_data[idx] != 0xAA:
                        raise ValueError(f"Frame {frame_idx}: Expected 0xAA at position {idx}, got 0x{all_frame_data[idx]:02X}")

                    # Read payload length (2 bytes, little-endian)
                    if idx + 2 >= len(all_frame_data):
                        break
                    payload_len = all_frame_data[idx + 1] | (all_frame_data[idx + 2] << 8)

                    # Extract frame data from 0xAA marker to end of payload
                    frame_data = all_frame_data[idx:idx + payload_len]

                    # Determine frame encrypt type (accept high-bit variants)
                    if len(frame_data) < 8:
                        raise ValueError("Truncated frame header")
                    encrypt_type = frame_data[5] & 0x7F

                    if encrypt_type == 0x11:
                        # Raw RGB (size depends on dimensions)
                        expected_raw_size = width * height * 3
                        if len(frame_data) < 8 + expected_raw_size:
                            raise ValueError(f"Truncated raw RGB payload (expected {expected_raw_size} bytes)")
                        frames_rgb.append(bytes(frame_data[8:8 + expected_raw_size]))
                        # Reset palette persistence on raw frames
                        shared_palette = []
                    elif encrypt_type in (0x13, 0x15):
                        # Hierarchical/delta palette decode
                        frame_decoder = _Decoder0x1AFrame(
                            frame_data,
                            width=width,
                            height=height,
                            debug=False,
                            frame_index=frame_idx,
                            previous_palette=shared_palette,
                        )
                        img, _ = frame_decoder.decode_frame()
                        frames_rgb.append(img.tobytes())
                        # Persist updated palette
                        shared_palette = frame_decoder.palette
                    else:
                        # Unsupported inside this container; try hierarchical as fallback
                        frame_decoder = _Decoder0x1AFrame(
                            frame_data,
                            width=width,
                            height=height,
                            debug=False,
                            frame_index=frame_idx,
                            previous_palette=shared_palette,
                        )
                        img, _ = frame_decoder.decode_frame()
                        frames_rgb.append(img.tobytes())
                        shared_palette = frame_decoder.palette

                    # Move to next frame (skip the 4-byte header we already accounted for + payload)
                    pos = idx + payload_len

                except (IndexError, ValueError) as e:
                    # Frame has incomplete or invalid data
                    # Duplicate previous frame if available, otherwise create blank frame
                    if frames_rgb:
                        frames_rgb.append(frames_rgb[-1])
                    else:
                        # Create blank frame with correct dimensions
                        blank_img = Image.new('RGB', (width, height), (0, 0, 0))
                        frames_rgb.append(blank_img.tobytes())
                    # Try to move to next frame using payload_len if we got that far
                    try:
                        if 'payload_len' in locals():
                            pos = idx + payload_len
                        else:
                            break  # Can't continue without knowing frame size
                    except:
                        break
        
        # Build numpy arrays from decoded RGB data
        frames_arrays = self._build_frames_arrays(frames_rgb, width, height)
        
        return PixelBean(
            len(frames_rgb),
            speed,
            row_count,
            column_count,
            frames_arrays,
        )
    
    def _build_frames_arrays(self, frames_rgb, width, height):
        """
        Build numpy arrays from raw RGB frames.
        
        Args:
            frames_rgb: List of raw RGB frame data (bytes)
            width: Frame width
            height: Frame height
            
        Returns:
            List of numpy arrays, each with shape (height, width, 3)
        """
        frames_arrays = []
        
        for frame_idx, rgb_bytes in enumerate(frames_rgb):
            # Create numpy array for this frame (height, width, 3)
            frame_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            pos = 0
            for y in range(height):
                for x in range(width):
                    r = rgb_bytes[pos]
                    g = rgb_bytes[pos + 1]
                    b = rgb_bytes[pos + 2]
                    pos += 3
                    
                    # Store RGB values directly in numpy array
                    frame_array[y, x] = [r, g, b]
            
            frames_arrays.append(frame_array)
        
        return frames_arrays


class _Decoder0x1AFrame:
    """Internal helper class for decoding individual 0x15 frames (supports 64x64 and 128x128)."""
    
    def _bits_per_pixel_from_count(self, num_colors: int) -> int:
        if num_colors <= 1:
            # Zero bits encode a single constant value
            return 0
        bits = 1
        while (1 << bits) < num_colors:
            bits += 1
        return bits

    def __init__(
        self,
        frame_data: bytes,
        width: int,
        height: int,
        debug: bool = False,
        frame_index: int = 0,
        previous_palette: List[Tuple[int, int, int]] = None,
    ):
        # Parse per-frame header
        if len(frame_data) < 8:
            raise ValueError("Frame data too short")

        if frame_data[0] != 0xAA:
            raise ValueError("Frame data does not start with 0xAA")

        # Accept high-bit variant per native code
        self.encrypt_type = frame_data[5] & 0x7F

        # Palette size is 16-bit little-endian at offset 6
        palette_size_u16 = frame_data[6] | (frame_data[7] << 8)
        palette_start = 8
        # Build or extend palette according to encrypt_type
        base_palette: List[Tuple[int, int, int]] = previous_palette or []
        self.palette: List[Tuple[int, int, int]] = []
        if self.encrypt_type == 0x13:
            # Append new colors to previous palette
            self.palette = list(base_palette)
            for i in range(palette_size_u16):
                off = palette_start + i * 3
                if off + 2 >= len(frame_data):
                    raise ValueError(f"Palette OOB at {off} len={len(frame_data)}")
                r, g, b = frame_data[off], frame_data[off + 1], frame_data[off + 2]
                self.palette.append((r, g, b))
            pixel_data_offset = palette_start + palette_size_u16 * 3
        else:
            # Full palette provided (e.g., 0x15)
            for i in range(palette_size_u16):
                off = palette_start + i * 3
                if off + 2 >= len(frame_data):
                    raise ValueError(f"Palette OOB at {off} len={len(frame_data)}")
                r, g, b = frame_data[off], frame_data[off + 1], frame_data[off + 2]
                self.palette.append((r, g, b))
            pixel_data_offset = palette_start + palette_size_u16 * 3
        self.pixel = frame_data[pixel_data_offset:]
        self.pixel_data_offset = pixel_data_offset
        self._out_of_data_warning = False
        # Determine bits-per-pixel from palette size (ceil(log2(n)))
        self.base_bpp = self._bits_per_pixel_from_count(len(self.palette))

        # Output buffer (scanline order) with actual dimensions
        self.width = width
        self.height = height
        self.out: List[Tuple[int, int, int]] = [(0, 0, 0)] * (self.width * self.height)
        # Bitstream is little-endian within each byte
        self._bitorder = 'lsb'
        self._debug = debug
        self._frame_index = frame_index

    def _palette_at(self, idx: int) -> Tuple[int, int, int]:
        if not (0 <= idx < len(self.palette)):
            idx = 0
        return self.palette[idx]

    def _read_indices(self, data: bytes, start: int, num_values: int, bits: int) -> Tuple[List[int], int]:
        if bits == 0:
            return [0] * num_values, start
        if self._bitorder == 'lsb':
            pos = start
            bit = 0
            values: List[int] = []
            for _ in range(num_values):
                v = 0
                for i in range(bits):
                    if pos >= len(data):
                        if self._debug and not self._out_of_data_warning:
                            print(f"        [warn] Ran out of pixel data at pos={pos} (need {num_values} values, bits={bits})")
                            self._out_of_data_warning = True
                        b = 0
                    else:
                        b = (data[pos] >> bit) & 1
                    v |= (b << i)
                    bit += 1
                    if bit == 8:
                        bit = 0
                        pos += 1
                values.append(v)
            if bit != 0:
                pos += 1
            return values, pos
        else:
            # MSB reader (not used for 0x15)
            pos = start
            bitpos = 0
            values: List[int] = []
            cur = data[pos] if pos < len(data) else 0
            for _ in range(num_values):
                remaining = bits
                v = 0
                while remaining > 0:
                    if pos >= len(data):
                        if self._debug and not self._out_of_data_warning:
                            print(f"        [warn] Ran out of pixel data at pos={pos} (need {num_values} values, bits={bits})")
                            self._out_of_data_warning = True
                        take = remaining
                        chunk = 0
                    else:
                        avail = 8 - bitpos
                        take = remaining if remaining <= avail else avail
                        mask = ((0xFF >> bitpos) & (0xFF << (8 - (bitpos + take)))) & 0xFF
                        chunk = (cur & mask) >> (8 - (bitpos + take))
                    v = (v << take) | chunk
                    remaining -= take
                    bitpos += take
                    if bitpos == 8:
                        bitpos = 0
                        pos += 1
                        cur = data[pos] if pos < len(data) else 0
                values.append(v)
            if bitpos != 0:
                pos += 1
            return values, pos

    def _decode_fix_64(self, offset: int, xq: int, yq: int) -> int:
        x0 = xq * 64
        y0 = yq * 64
        if offset + 1 >= len(self.pixel):
            raise IndexError(f"fix_64 header OOB at {offset} len={len(self.pixel)}")
        ctrl = self.pixel[offset]
        if ctrl == 0:
            ptr = offset + 1
        else:
            if offset + 1 >= len(self.pixel):
                raise IndexError(f"fix_64 header OOB at {offset+1} len={len(self.pixel)}")
            N = self.pixel[offset + 1] or 0x100
            ptr = offset + 2
        if self._debug:
            print(f"  [64] off={offset} ctrl={ctrl} ptr={ptr} remain={len(self.pixel)-ptr}")
        if ctrl == 2:
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            selected: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    selected.append(i)
            ptr += mask_bytes
            bpp = self._bits_per_pixel_from_count(len(selected))
            if self._debug:
                print(f"  [64] ctrl=2 selected={len(selected)} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 64 * 64, bpp)
            # Paint in 8×8 subtiles (Morton-style nested loops in C)
            it = 0
            w = self.width
            for br in range(8):
                for bc in range(8):
                    for row in range(8):
                        y = y0 + br * 8 + row
                        base = y * w + (x0 + bc * 8)
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            if not (0 <= idx < len(selected)):
                                idx = 0
                            self.out[base + col] = self._palette_at(selected[idx])
            return ptr2 - offset
        elif ctrl == 0:
            bpp = self.base_bpp
            if self._debug:
                print(f"  [64] ctrl=0 bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 64 * 64, bpp)
            it = 0
            w = self.width
            for br in range(8):
                for bc in range(8):
                    for row in range(8):
                        y = y0 + br * 8 + row
                        base = y * w + (x0 + bc * 8)
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            pal_index = idx if 0 <= idx < len(self.palette) else 0
                            self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        else:
            # Recursion with a mask into the base palette
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            mapping: List[int] = [i for i in range(N) if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0]
            ptr += mask_bytes
            if self._debug:
                print(f"  [64] ctrl=rec mapping={len(mapping)} read_from={ptr}")
            consumed = 0
            consumed += self._decode_fix_32(ptr + consumed, xq * 2 + 0, yq * 2 + 0, mapping)
            consumed += self._decode_fix_32(ptr + consumed, xq * 2 + 1, yq * 2 + 0, mapping)
            consumed += self._decode_fix_32(ptr + consumed, xq * 2 + 0, yq * 2 + 1, mapping)
            consumed += self._decode_fix_32(ptr + consumed, xq * 2 + 1, yq * 2 + 1, mapping)
            return 2 + mask_bytes + consumed

    def _decode_fix_32(self, offset: int, xq: int, yq: int, parent_map: List[int]) -> int:
        x0 = xq * 32
        y0 = yq * 32
        if offset + 1 >= len(self.pixel):
            raise IndexError(f"fix_32 header OOB at {offset} len={len(self.pixel)}")
        ctrl = self.pixel[offset]
        if ctrl == 0:
            ptr = offset + 1
        else:
            if offset + 1 >= len(self.pixel):
                raise IndexError(f"fix_32 header OOB at {offset+1} len={len(self.pixel)}")
            N = self.pixel[offset + 1] or 0x100
            ptr = offset + 2
        if self._debug:
            print(f"    [32] off={offset} ctrl={ctrl} ptr={ptr} remain={len(self.pixel)-ptr}")
        if ctrl == 2:
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            selected: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    if i < len(parent_map):
                        selected.append(parent_map[i])
            ptr += mask_bytes
            if not selected:
                selected = [0]
            bpp = self._bits_per_pixel_from_count(len(selected))
            if self._debug:
                print(f"    [32] ctrl=2 selected={len(selected)} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 32 * 32, bpp)
            it = 0
            w = self.width
            for br in range(4):
                for bc in range(4):
                    for row in range(8):
                        y = y0 + br * 8 + row
                        base = y * w + (x0 + bc * 8)
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            pal_index = selected[idx] if 0 <= idx < len(selected) else 0
                            self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        elif ctrl == 0:
            bpp = self._bits_per_pixel_from_count(len(parent_map) or 1)
            if self._debug:
                print(f"    [32] ctrl=0 parent_len={len(parent_map)} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 32 * 32, bpp)
            it = 0
            w = self.width
            for br in range(4):
                for bc in range(4):
                    for row in range(8):
                        y = y0 + br * 8 + row
                        base = y * w + (x0 + bc * 8)
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            pal_index = parent_map[idx] if 0 <= idx < len(parent_map) else 0
                            self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        else:
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            mapping: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    if i < len(parent_map):
                        mapping.append(parent_map[i])
            ptr += mask_bytes
            if not mapping:
                mapping = [0]
            if self._debug:
                print(f"    [32] ctrl=rec mapping={len(mapping)} read_from={ptr}")
            consumed = 0
            consumed += self._decode_fix_16(ptr + consumed, xq * 2 + 0, yq * 2 + 0, mapping)
            consumed += self._decode_fix_16(ptr + consumed, xq * 2 + 1, yq * 2 + 0, mapping)
            consumed += self._decode_fix_16(ptr + consumed, xq * 2 + 0, yq * 2 + 1, mapping)
            consumed += self._decode_fix_16(ptr + consumed, xq * 2 + 1, yq * 2 + 1, mapping)
            return 2 + mask_bytes + consumed

    def _decode_fix_16(self, offset: int, xq: int, yq: int, parent_map: List[int]) -> int:
        x0 = xq * 16
        y0 = yq * 16
        if offset + 1 >= len(self.pixel):
            raise IndexError(f"fix_32 header OOB at {offset} len={len(self.pixel)}")
        ctrl = self.pixel[offset]
        if ctrl == 0:
            ptr = offset + 1
        else:
            if offset + 1 >= len(self.pixel):
                raise IndexError(f"fix_16 header OOB at {offset+1} len={len(self.pixel)}")
            N = self.pixel[offset + 1] or 0x100
            ptr = offset + 2
        if self._debug:
            print(f"      [16] off={offset} ctrl={ctrl} ptr={ptr} remain={len(self.pixel)-ptr}")
        if ctrl == 2:
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            selected: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    if i < len(parent_map):
                        selected.append(parent_map[i])
            ptr += mask_bytes
            if not selected:
                selected = [0]
            bpp = self._bits_per_pixel_from_count(len(selected))
            if self._debug:
                print(f"      [16] ctrl=2 selected={len(selected)} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 16 * 16, bpp)
            it = 0
            w = self.width
            for row_block in range(2):  # top, bottom
                for band in range(2):   # left, right
                    x_band = x0 + band * 8
                    for row in range(8):
                        y = y0 + row_block * 8 + row
                        base = y * w + x_band
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            pal_index = selected[idx] if 0 <= idx < len(selected) else 0
                            self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        elif ctrl == 0:
            bpp = self._bits_per_pixel_from_count(len(parent_map) or 1)
            if self._debug:
                print(f"      [16] ctrl=0 parent_len={len(parent_map)} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 16 * 16, bpp)
            it = 0
            w = self.width
            for row_block in range(2):
                for band in range(2):
                    x_band = x0 + band * 8
                    for row in range(8):
                        y = y0 + row_block * 8 + row
                        base = y * w + x_band
                        for col in range(8):
                            idx = values[it]
                            it += 1
                            pal_index = parent_map[idx] if 0 <= idx < len(parent_map) else 0
                            self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        else:
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            mapping: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    if i < len(parent_map):
                        mapping.append(parent_map[i])
            ptr += mask_bytes
            if not mapping:
                mapping = [0]
            if self._debug:
                print(f"      [16] ctrl=rec mapping={len(mapping)} read_from={ptr}")
            consumed = 0
            consumed += self._decode_fix_8(ptr + consumed, xq * 2 + 0, yq * 2 + 0, mapping)
            consumed += self._decode_fix_8(ptr + consumed, xq * 2 + 1, yq * 2 + 0, mapping)
            consumed += self._decode_fix_8(ptr + consumed, xq * 2 + 0, yq * 2 + 1, mapping)
            consumed += self._decode_fix_8(ptr + consumed, xq * 2 + 1, yq * 2 + 1, mapping)
            return 2 + mask_bytes + consumed

    def _decode_fix_8(self, offset: int, xq: int, yq: int, parent_map: List[int]) -> int:
        x0 = xq * 8
        y0 = yq * 8
        if offset >= len(self.pixel):
            raise IndexError(f"fix_8 header OOB at {offset} len={len(self.pixel)}")
        first = self.pixel[offset]
        if first & 0x80:  # mask-present header
            N = first & 0x7F
            ptr = offset + 1
            mask_bytes = (N + 7) // 8
            if ptr + mask_bytes > len(self.pixel):
                raise IndexError(f"fix_64 mask OOB ptr={ptr} mask_bytes={mask_bytes} len={len(self.pixel)}")
            selected: List[int] = []
            for i in range(N):
                if ((self.pixel[ptr + (i >> 3)] >> (i & 7)) & 1) != 0:
                    if i < len(parent_map):
                        selected.append(parent_map[i])
            ptr += mask_bytes
            if not selected:
                selected = [0]
            bpp = self._bits_per_pixel_from_count(len(selected))
            if self._debug:
                print(f"        [8] mask hdr N={N} bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 8 * 8, bpp)
            # Paint contiguous 8×8
            it = 0
            w = self.width
            for row in range(8):
                base = (y0 + row) * w + x0
                for col in range(8):
                    idx = values[it]
                    it += 1
                    pal_index = selected[idx] if 0 <= idx < len(selected) else 0
                    self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset
        else:
            bpp = self._bits_per_pixel_from_count(len(parent_map))
            ptr = offset + 1
            if self._debug:
                print(f"        [8] raw hdr bpp={bpp} read_from={ptr}")
            values, ptr2 = self._read_indices(self.pixel, ptr, 8 * 8, bpp)
            it = 0
            w = self.width
            for row in range(8):
                base = (y0 + row) * w + x0
                for col in range(8):
                    idx = values[it]
                    it += 1
                    pal_index = parent_map[idx] if 0 <= idx < len(parent_map) else 0
                    self.out[base + col] = self._palette_at(pal_index)
            return ptr2 - offset

    def decode_frame(self) -> Tuple[Image.Image, int]:
        """
        Decode a single frame and return the image and bytes consumed.
        
        For 64x64 frames: decode only the top-left 64x64 quadrant
        For 128x128 frames: decode all four 64x64 quadrants
        """
        off = 0
        
        # Always decode the top-left quadrant (0, 0)
        off += self._decode_fix_64(off, 0, 0)
        
        # For 128x128 frames, decode the remaining three quadrants
        if self.width == 128 and self.height == 128:
            off += self._decode_fix_64(off, 1, 0)  # Top-right
            off += self._decode_fix_64(off, 0, 1)  # Bottom-left
            off += self._decode_fix_64(off, 1, 1)  # Bottom-right
        
        img = Image.new('RGB', (self.width, self.height))
        img.putdata(self.out)
        if self._debug:
            total_payload = len(self.pixel) + self.pixel_data_offset
            print(f"  [frame] pixel-bytes consumed: {off} / {len(self.pixel)} | total payload used: {self.pixel_data_offset + off} / {total_payload}")
        return img, off



class PicMultiDecoder(BaseDecoder):
    def decode(self) -> PixelBean:
        row_count, column_count, length = unpack('>BBI', self._fp.read(6))
        encrypted_data = self._fp.read()

        width = 16 * column_count
        height = 16 * row_count
        uncompressed_frame_size = width * height * 3

        data = self._decrypt_aes(encrypted_data)

        frame_data = self._lzo.decompress(data[:length], uncompressed_frame_size)
        frames_data = [frame_data]
        total_frames = 1
        speed = 40
        frames_arrays = self._compact(
            frames_data, total_frames, row_count, column_count
        )
        
        return PixelBean(
            total_frames,
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class AnimZstdRawRGBDecoder(BaseDecoder):
    def _build_frames_arrays(self, frames_rgb, width, height):
        """
        Build numpy arrays from raw RGB frames.
        
        Args:
            frames_rgb: List of raw RGB frame data (bytes)
            width: Frame width
            height: Frame height
            
        Returns:
            List of numpy arrays, each with shape (height, width, 3)
        """
        frames_arrays = []
        
        for frame_idx, rgb_bytes in enumerate(frames_rgb):
            # Create numpy array for this frame (height, width, 3)
            frame_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            pos = 0
            for y in range(height):
                for x in range(width):
                    r = rgb_bytes[pos]
                    g = rgb_bytes[pos + 1]
                    b = rgb_bytes[pos + 2]
                    pos += 3
                    
                    # Store RGB values directly in numpy array
                    frame_array[y, x] = [r, g, b]
            
            frames_arrays.append(frame_array)
        
        return frames_arrays

    def decode(self) -> PixelBean:
        total_frames, speed, row_count, column_count = unpack('>BHBB', self._fp.read(5))
        width = 16 * column_count
        height = 16 * row_count
        remainder = self._fp.read()
        # Find zstd payload and decompress
        magic = b'\x28\xB5\x2F\xFD'
        idx = remainder.find(magic)
        if idx == -1:
            raise Exception('Format 42: zstd magic not found')
        payload = remainder[idx:]
        try:
            import zstandard as zstd
        except Exception:
            raise Exception('Format 42 requires zstandard package')
        decomp = zstd.ZstdDecompressor().decompress(payload)
        frame_bytes = width * height * 3
        if frame_bytes == 0:
            raise Exception('Invalid dimensions')
        available = len(decomp) // frame_bytes
        if available < total_frames:
            # Accept shorter streams; decode what we have
            target_frames = available
        else:
            target_frames = total_frames
        frames_rgb = []
        pos = 0
        for _ in range(target_frames):
            frames_rgb.append(decomp[pos : pos + frame_bytes])
            pos += frame_bytes
        frames_arrays = self._build_frames_arrays(frames_rgb, width, height)
        return PixelBean(
            target_frames,
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class AnimEmbeddedImageDecoder(BaseDecoder):
    def _extract_frames_rgb(self, data, width, height):
        # Try embedded GIF
        try:
            from PIL import Image, ImageSequence
        except Exception:
            raise Exception('Format 43 requires Pillow')
        expected = (width, height)
        def _compose_gif(gif_bytes):
            frames = []
            with Image.open(io.BytesIO(gif_bytes)) as im:  # type: ignore
                palette = im.getpalette()
                composed = None
                for frame in ImageSequence.Iterator(im):
                    if frame.mode == 'P' and not frame.getpalette() and palette:
                        frame.putpalette(palette)
                    base = Image.new('RGBA', im.size, (255, 255, 255, 255))
                    if composed is not None:
                        base.paste(composed)
                    rgba = frame.convert('RGBA')
                    base.paste(rgba, (0, 0), rgba)
                    composed = base
                    rgb = base.convert('RGB')
                    if rgb.size != expected:
                        rgb = rgb.resize(expected, Image.NEAREST)
                    frames.append(rgb.tobytes())
            return frames
        # GIF signature
        off = data.find(b'GIF8')
        if off != -1:
            return _compose_gif(data[off:])
        # WEBP inside RIFF
        offw = data.find(b'RIFF')
        if offw != -1 and data[offw + 8 : offw + 12] == b'WEBP':
            frames = []
            with Image.open(io.BytesIO(data[offw:])) as im:  # type: ignore
                composed = None
                for frame in ImageSequence.Iterator(im):
                    base = Image.new('RGBA', im.size, (255, 255, 255, 255))
                    if composed is not None:
                        base.paste(composed)
                    rgba = frame.convert('RGBA')
                    base.paste(rgba, (0, 0), rgba)
                    composed = base
                    rgb = base.convert('RGB')
                    if rgb.size != expected:
                        rgb = rgb.resize(expected, Image.NEAREST)
                    frames.append(rgb.tobytes())
            return frames
        # Last resort: let Pillow sniff container
        frames = []
        with Image.open(io.BytesIO(data)) as im:  # type: ignore
            composed = None
            for frame in ImageSequence.Iterator(im):
                base = Image.new('RGBA', im.size, (255, 255, 255, 255))
                if composed is not None:
                    base.paste(composed)
                rgba = frame.convert('RGBA')
                base.paste(rgba, (0, 0), rgba)
                composed = base
                rgb = base.convert('RGB')
                if rgb.size != expected:
                    rgb = rgb.resize(expected, Image.NEAREST)
                frames.append(rgb.tobytes())
        return frames

    def _build_frames_arrays(self, frames_rgb, width, height):
        """
        Build numpy arrays from raw RGB frames.
        
        Args:
            frames_rgb: List of raw RGB frame data (bytes)
            width: Frame width
            height: Frame height
            
        Returns:
            List of numpy arrays, each with shape (height, width, 3)
        """
        frames_arrays = []
        
        for frame_idx, rgb_bytes in enumerate(frames_rgb):
            # Create numpy array for this frame (height, width, 3)
            frame_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            pos = 0
            for y in range(height):
                for x in range(width):
                    r = rgb_bytes[pos]
                    g = rgb_bytes[pos + 1]
                    b = rgb_bytes[pos + 2]
                    pos += 3
                    
                    # Store RGB values directly in numpy array
                    frame_array[y, x] = [r, g, b]
            
            frames_arrays.append(frame_array)
        
        return frames_arrays

    def decode(self) -> PixelBean:
        import io  # local to avoid global import if unused
        from PIL import Image, ImageSequence  # type: ignore
        total_frames, speed, row_count, column_count = unpack('>BHBB', self._fp.read(5))
        width = 16 * column_count
        height = 16 * row_count
        data = self._fp.read()
        frames_rgb = self._extract_frames_rgb(data, width, height)
        frames_arrays = self._build_frames_arrays(frames_rgb, width, height)
        return PixelBean(
            len(frames_rgb),
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class Format41Decoder(BaseDecoder):
    """Decoder for format 0x29 (41) - JPEG sequence animations at 256x256."""

    _GAP_PREFIX = b'\x02\x00\x00'
    _RESERVED_HEADER_LEN = 9  # Additional bytes between header and first JPEG

    def decode(self) -> PixelBean:
        basic_header = self._fp.read(5)
        if len(basic_header) < 5:
            print("[ERROR] Format 41: header too short")
            return None

        total_frames = basic_header[0]
        speed = (basic_header[1] << 8) | basic_header[2]
        row_count = basic_header[3] or 1
        column_count = basic_header[4] or 1

        # Skip reserved/unknown header bytes (observed length: 9 bytes)
        reserved = self._fp.read(self._RESERVED_HEADER_LEN)
        if len(reserved) < self._RESERVED_HEADER_LEN:
            print("[WARN] Format 41: reserved header truncated")

        width = column_count * 16
        height = row_count * 16

        payload = self._fp.read()
        if not payload:
            print("[ERROR] Format 41: empty payload")
            return None

        jpeg_frames = self._extract_jpeg_frames(payload, total_frames)
        if not jpeg_frames:
            print("[ERROR] Format 41: no JPEG frames extracted")
            return None

        frames_arrays, derived_size = self._decode_jpeg_frames(
            jpeg_frames, width, height
        )

        if derived_size and (width == 0 or height == 0):
            width, height = derived_size
            row_count = max(1, height // 16)
            column_count = max(1, width // 16)

        actual_frames = len(frames_arrays)
        if total_frames and actual_frames != total_frames:
            print(
                f"  [WARN] Format 41: header frames {total_frames}, decoded {actual_frames}"
            )

        return PixelBean(
            actual_frames,
            speed or 50,
            row_count,
            column_count,
            frames_arrays,
        )

    def _extract_jpeg_frames(self, data: bytes, expected_frames: int) -> List[bytes]:
        frames: List[bytes] = []
        cursor = 0
        length = len(data)
        soi = b'\xff\xd8'
        eoi = b'\xff\xd9'

        while cursor < length:
            start = data.find(soi, cursor)
            if start == -1:
                break
            end = data.find(eoi, start)
            if end == -1:
                break
            end += 2  # include EOI marker
            frames.append(data[start:end])
            cursor = end

            # Skip optional gap metadata if present (5 bytes observed)
            if cursor + 5 <= length and data[cursor : cursor + 3] == self._GAP_PREFIX:
                cursor += 5

            if expected_frames and len(frames) >= expected_frames:
                break

        return frames

    def _decode_jpeg_frames(
        self, frames: List[bytes], width: int, height: int
    ) -> Tuple[List[np.ndarray], Tuple[int, int]]:
        import io
        from PIL import Image  # type: ignore

        frames_arrays: List[np.ndarray] = []
        derived_size: Tuple[int, int] = (0, 0)
        target_size = (width, height) if width and height else None

        for idx, jpeg_data in enumerate(frames):
            try:
                with Image.open(io.BytesIO(jpeg_data)) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    if target_size:
                        if img.size != target_size:
                            img = img.resize(target_size, Image.NEAREST)
                    else:
                        target_size = img.size
                        derived_size = img.size
                    frames_arrays.append(np.array(img, dtype=np.uint8))
            except Exception as exc:
                print(f"  [WARN] Format 41: failed to decode frame {idx}: {exc}")
                break

        return frames_arrays, derived_size


class AnimMulti64Decoder(BaseDecoder):
    """Decoder specifically for 64x64 animations with 0x0C encryption (format 26)."""
    
    def _get_dot_info(self, data, pos, pixel_idx, bVar9):
        """Extract pixel color index from compressed data."""
        if not data[pos:]:
            return -1

        uVar2 = bVar9 * pixel_idx & 7
        uVar4 = bVar9 * pixel_idx * 65536 >> 0x13

        if bVar9 < 9:
            uVar3 = bVar9 + uVar2
            if uVar3 < 9:
                uVar6 = data[pos + uVar4] << (8 - uVar3 & 0xFF) & 0xFF
                uVar6 >>= uVar2 + (8 - uVar3) & 0xFF
            else:
                uVar6 = data[pos + uVar4 + 1] << (0x10 - uVar3 & 0xFF) & 0xFF
                uVar6 >>= 0x10 - uVar3 & 0xFF
                uVar6 &= 0xFFFF
                uVar6 <<= 8 - uVar2 & 0xFF
                uVar6 |= data[pos + uVar4] >> uVar2
        else:
            raise Exception('(2) Unimplemented')

        return uVar6

    def _decode_frame_data(self, data):
        """Decode a single 64x64 frame with 0x0C encryption."""
        output = [None] * 12288  # 64x64 * 3 channels
        encrypt_type = data[5]
        if encrypt_type != 0x0C:
            raise Exception(f'Unsupported encryption type: 0x{encrypt_type:02X}')

        uVar13 = data[6]
        iVar11 = uVar13 * 3

        if uVar13 == 0:
            bVar9 = 8
            iVar11 = 768  # Fix corrupted frame
        else:
            bVar9 = 0xFF
            bVar15 = 1
            while True:
                if (uVar13 & 1) != 0:
                    bVar18 = bVar9 == 0xFF
                    bVar9 = bVar15
                    if bVar18:
                        bVar9 = bVar15 - 1

                uVar14 = uVar13 & 0xFFFE
                bVar15 = bVar15 + 1
                uVar13 = uVar14 >> 1
                if uVar14 == 0:
                    break

        pixel_idx = 0
        pos = (iVar11 + 8) & 0xFFFF

        while True:
            color_index = self._get_dot_info(data, pos, pixel_idx & 0xFFFF, bVar9)

            target_pos = pixel_idx * 3
            if color_index == -1:  # transparent -> black
                output[target_pos] = 0
                output[target_pos + 1] = 0
                output[target_pos + 2] = 0
            else:
                color_pos = 8 + color_index * 3

                output[target_pos] = data[color_pos]
                output[target_pos + 1] = data[color_pos + 1]
                output[target_pos + 2] = data[color_pos + 2]

            pixel_idx += 1
            if pixel_idx == 4096:  # 64x64
                break

        return bytearray(output)

    def decode(self) -> PixelBean:
        """Decode 64x64 animation and return a PixelBean."""
        total_frames, speed, row_count, column_count = unpack('>BHBB', self._fp.read(5))
        frames_data = []

        for frame in range(total_frames):
            size = unpack('>I', self._fp.read(4))[0]
            frame_data = self._decode_frame_data(self._fp.read(size))
            frames_data.append(frame_data)

        # Convert to numpy arrays
        frames_arrays = self._compact(
            frames_data, total_frames, row_count, column_count
        )

        return PixelBean(
            total_frames,
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class Decoder0x1F(BaseDecoder):
    """Decoder for format 0x1F (31 decimal) - Embedded JPEG animation format."""
    
    def _extract_jpeg_frames(self, data: bytes, width: int, height: int, total_frames: int) -> List[bytes]:
        """
        Extract individual JPEG frames from the payload and convert to RGB bytes.
        
        Args:
            data: Raw payload data containing JPEG frames
            width: Target frame width
            height: Target frame height
            total_frames: Expected number of frames
            
        Returns:
            List of raw RGB frame data (bytes)
        """
        try:
            from PIL import Image
        except Exception:
            raise Exception('Format 31 requires Pillow')
        
        frames_rgb = []
        expected = (width, height)
        
        # Find all JPEG Start Of Image (SOI) markers (0xFF 0xD8)
        jpeg_soi = b'\xff\xd8'
        jpeg_eoi = b'\xff\xd9'  # End Of Image marker
        
        pos = 0
        frame_count = 0
        
        while pos < len(data) and frame_count < total_frames:
            # Find next JPEG SOI marker
            soi_pos = data.find(jpeg_soi, pos)
            if soi_pos == -1:
                break
            
            # Find corresponding EOI marker
            eoi_pos = data.find(jpeg_eoi, soi_pos + 2)
            if eoi_pos == -1:
                # No EOI found, try to use rest of data
                eoi_pos = len(data) - 2
            
            # Extract JPEG data (including EOI marker)
            jpeg_data = data[soi_pos:eoi_pos + 2]
            
            try:
                # Decode JPEG image
                img = Image.open(io.BytesIO(jpeg_data))
                
                # Convert to RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if necessary
                if img.size != expected:
                    img = img.resize(expected, Image.NEAREST)
                
                # Convert to raw RGB bytes
                frames_rgb.append(img.tobytes())
                frame_count += 1
                
            except Exception as e:
                # If JPEG decode fails, try to continue
                print(f"  [WARN] Failed to decode JPEG frame {frame_count + 1}: {e}")
            
            # Move to next potential frame (after current EOI)
            pos = eoi_pos + 2
        
        return frames_rgb
    
    def _build_frames_arrays(self, frames_rgb: List[bytes], width: int, height: int) -> List[np.ndarray]:
        """
        Build numpy arrays from raw RGB frames.
        
        Args:
            frames_rgb: List of raw RGB frame data (bytes)
            width: Frame width
            height: Frame height
            
        Returns:
            List of numpy arrays, each with shape (height, width, 3)
        """
        frames_arrays = []
        
        for frame_idx, rgb_bytes in enumerate(frames_rgb):
            # Create numpy array for this frame (height, width, 3)
            frame_array = np.zeros((height, width, 3), dtype=np.uint8)
            
            pos = 0
            for y in range(height):
                for x in range(width):
                    if pos + 2 < len(rgb_bytes):
                        r = rgb_bytes[pos]
                        g = rgb_bytes[pos + 1]
                        b = rgb_bytes[pos + 2]
                        pos += 3
                        
                        # Store RGB values directly in numpy array
                        frame_array[y, x] = [r, g, b]
                    else:
                        # Out of bounds, use black
                        break
            
            frames_arrays.append(frame_array)
        
        return frames_arrays
    
    def decode(self) -> PixelBean:
        """
        Decode format 31 file - embedded JPEG animation.
        """
        # Read header (5 bytes like other formats)
        header_bytes = self._fp.read(5)
        
        if len(header_bytes) < 5:
            print(f"[ERROR] Header too short: {len(header_bytes)} bytes")
            return None
        
        total_frames = header_bytes[0]
        speed = unpack('>H', header_bytes[1:3])[0]
        row_count = header_bytes[3]
        column_count = header_bytes[4]
        
        # Calculate dimensions
        width = column_count * 16
        height = row_count * 16
        
        # Read all remaining payload (contains JPEG frames)
        payload = self._fp.read()
        
        # Extract and decode JPEG frames
        frames_rgb = self._extract_jpeg_frames(payload, width, height, total_frames)
        
        if not frames_rgb:
            print(f"[WARN] No JPEG frames extracted, creating blank frames")
            # Fallback: create blank frames
            blank_frame = bytes([0] * (width * height * 3))
            frames_rgb = [blank_frame] * total_frames
        
        # Build numpy arrays from RGB data
        frames_arrays = self._build_frames_arrays(frames_rgb, width, height)
        
        # Return PixelBean
        return PixelBean(
            len(frames_rgb),
            speed,
            row_count,
            column_count,
            frames_arrays,
        )


class PixelBeanDecoder(object):
    def decode_file(file_path: str) -> PixelBean:
        with open(file_path, 'rb') as fp:
            return PixelBeanDecoder.decode_stream(fp)

    def decode_stream(fp: IOBase) -> PixelBean:
        try:
            file_format = unpack('B', fp.read(1))[0]
            print(f'File format: {file_format}')
            file_format = FileFormat(file_format)
        except Exception:
            print(f'Unsupported file format: {file_format}')
            return None

        if file_format == FileFormat.ANIM_SINGLE:
            return AnimSingleDecoder(fp).decode()
        elif file_format == FileFormat.ANIM_MULTIPLE:
            return AnimMultiDecoder(fp).decode()
        elif file_format == FileFormat.PIC_MULTIPLE:
            return PicMultiDecoder(fp).decode()
        elif file_format == FileFormat.ANIM_MULTIPLE_64:
            # Check dimensions to determine which decoder to use
            # Read header: total_frames (1), speed (2), row_count (1), column_count (1)
            header = fp.read(5)
            if len(header) < 5:
                return None
            
            total_frames = header[0]
            speed = unpack('>H', header[1:3])[0]
            row_count = header[3]
            column_count = header[4]
            
            # Calculate dimensions
            width = column_count * 16
            height = row_count * 16
            
            # Create a new BytesIO stream with the header + remaining data
            import io as io_module
            remaining_data = fp.read()
            new_fp = io_module.BytesIO(header + remaining_data)
            
            # Route to appropriate decoder based on dimensions
            if width == 64 and height == 64:
                # Use AnimMulti64Decoder for 64x64 animations (0x0C encryption)
                return AnimMulti64Decoder(new_fp).decode()
            else:
                # Use Decoder0x1A for other sizes (128x128, etc.) with 0x11/0x13/0x15 encryption
                return Decoder0x1A(new_fp).decode()
        elif file_format == FileFormat.ANIM_FORMAT_0x1F:
            return Decoder0x1F(fp).decode()
        elif file_format == FileFormat.ANIM_FORMAT_0x29:
            return Format41Decoder(fp).decode()
        elif file_format == FileFormat.ANIM_CONTAINER_ZSTD:
            return AnimZstdRawRGBDecoder(fp).decode()
        elif file_format == FileFormat.ANIM_EMBEDDED_IMAGE:
            return AnimEmbeddedImageDecoder(fp).decode()
