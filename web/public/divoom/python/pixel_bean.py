from typing import Union, List

import numpy as np
from PIL import Image


class PixelBean(object):
    @property
    def total_frames(self):
        return self._total_frames

    @property
    def speed(self):
        return self._speed

    @property
    def row_count(self):
        return self._row_count

    @property
    def column_count(self):
        return self._column_count

    @property
    def frames_data(self):
        return self._frames_data

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def __init__(
        self,
        total_frames: int,
        speed: int,
        row_count: int,
        column_count: int,
        frames_data: List[np.ndarray],
    ):
        """
        Initialize PixelBean.
        
        Args:
            total_frames: Number of frames in the animation
            speed: Frame delay in milliseconds
            row_count: Number of 16x16 tile rows
            column_count: Number of 16x16 tile columns
            frames_data: List of numpy arrays (one per frame), each of shape (height, width, 3) with RGB values
        """
        self._total_frames = total_frames
        self._speed = speed
        self._row_count = row_count
        self._column_count = column_count
        self._frames_data = frames_data

        self._width = column_count * 16
        self._height = row_count * 16

    def get_frame_image(
        self,
        frame_number: int,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> Image:
        """
        Get Pillow Image of a frame.
        
        Args:
            frame_number: Frame number (1-indexed)
            scale: Optional scale factor
            target_width: Optional target width
            target_height: Optional target height
            
        Returns:
            PIL Image object
        """
        if frame_number <= 0 or frame_number > self.total_frames:
            raise Exception('Frame number out of range!')

        # Get the frame as a numpy array (height, width, 3) with RGB values
        frame_array = self._frames_data[frame_number - 1]
        
        # Convert numpy array to PIL Image
        # numpy array is already in RGB format with shape (height, width, 3)
        img = Image.fromarray(frame_array.astype(np.uint8), 'RGB')

        img = self._resize(
            img, scale=scale, target_width=target_width, target_height=target_height
        )
        return img

    def _resize(
        self,
        img: Image,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> Image:
        """
        Resize image based on scale or target dimensions.
        
        Args:
            img: PIL Image to resize
            scale: Scale factor (default 1, no scaling)
            target_width: Optional explicit target width
            target_height: Optional explicit target height
            
        Returns:
            Resized PIL Image
        """
        if target_width is not None and target_height is not None:
            return img.resize((target_width, target_height), Image.NEAREST)
        elif target_width is not None:
            new_height = int(img.height * target_width / img.width)
            return img.resize((target_width, new_height), Image.NEAREST)
        elif target_height is not None:
            new_width = int(img.width * target_height / img.height)
            return img.resize((new_width, target_height), Image.NEAREST)
        elif scale != 1:
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            return img.resize((new_width, new_height), Image.NEAREST)
        return img

    def save_to_webp(
        self,
        output,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> None:
        """Convert animation to WebP file"""
        webp_frames = []

        for frame_number in range(self._total_frames):
            img = self.get_frame_image(
                frame_number + 1,
                scale=scale,
                target_width=target_width,
                target_height=target_height,
            )
            webp_frames.append(img)


        # Save to WebP
        save_kwargs = dict(
            append_images=webp_frames[1:],
            duration=self._speed,
            save_all=True,
            loop=0,
            disposal=0,
            lossless=True,
        )
        if hasattr(output, "write"):
            webp_frames[0].save(output, format="WEBP", **save_kwargs)
        else:
            webp_frames[0].save(output, **save_kwargs)

    def save_to_gif(
        self,
        output,
        scale: Union[int, float] = 1,
        target_width: int = None,
        target_height: int = None,
    ) -> None:
        """Convert animation to GIF file"""
        gif_frames = []
        for frame_number in range(self._total_frames):
            img = self.get_frame_image(
                frame_number + 1,
                scale=scale,
                target_width=target_width,
                target_height=target_height,
            )
            gif_frames.append(img)

        def to_gif_frame(image: Image) -> Image:
            return image.convert('P', palette=Image.ADAPTIVE)

        primary = to_gif_frame(gif_frames[0])
        remainder = [to_gif_frame(frame) for frame in gif_frames[1:]]
        save_kwargs = dict(
            append_images=remainder,
            duration=self._speed,
            save_all=True,
            loop=0,
            disposal=2,
        )
        if hasattr(output, "write"):
            primary.save(output, format="GIF", **save_kwargs)
        else:
            primary.save(output, **save_kwargs)
