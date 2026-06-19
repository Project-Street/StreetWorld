from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np


def ensure_uint8_rgb(image: np.ndarray) -> np.ndarray:
    image = np.asarray(image)
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Expected RGB image with shape (H, W, 3), got {image.shape}")
    return np.ascontiguousarray(image)


def compose_image_layout(
    image_stacks: Mapping[str, np.ndarray],
    layout: Sequence[Sequence[str]],
    pad_value: int = 0,
) -> np.ndarray:
    flat_names = [camera_name for row in layout for camera_name in row]
    if not flat_names:
        raise ValueError("image layout must contain at least one camera name")

    images = {}
    for camera_name in flat_names:
        image_stack = np.asarray(image_stacks[camera_name])
        if image_stack.ndim != 4 or image_stack.shape[0] <= 0:
            raise ValueError(f"Invalid image stack shape for {camera_name}: {image_stack.shape}")
        images[camera_name] = ensure_uint8_rgb(image_stack[-1])

    max_h = max(image.shape[0] for image in images.values())
    max_w = max(image.shape[1] for image in images.values())
    max_cols = max(len(row) for row in layout)
    if max_cols <= 0:
        raise ValueError("image layout rows must not be empty")

    canvas_h = max_h * len(layout)
    canvas_w = max_w * max_cols
    canvas = np.full((canvas_h, canvas_w, 3), int(pad_value), dtype=np.uint8)

    for row_idx, row in enumerate(layout):
        if not row:
            raise ValueError("image layout rows must not be empty")
        row_offset_x = ((max_cols - len(row)) * max_w) // 2
        for col_idx, camera_name in enumerate(row):
            image = images[camera_name]
            h, w = image.shape[:2]
            cell_x = row_offset_x + col_idx * max_w
            cell_y = row_idx * max_h
            x = cell_x + (max_w - w) // 2
            y = cell_y + (max_h - h) // 2
            canvas[y:y + h, x:x + w] = image

    return canvas
