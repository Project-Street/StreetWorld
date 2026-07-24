import os
import subprocess

import cv2
import numpy as np
from tqdm.auto import tqdm


def image_files_to_video(video_name, image_folder, fps, code="mp4v"):
    """
    code=mp4v, avc1, x264, h264 etc.
    """
    assert video_name.endswith(".mp4")
    images = [img for img in os.listdir(image_folder) if img.endswith(".png")]
    images.sort(key=lambda x: int(x[:-4]))
    assert len(images) > 0
    frame = cv2.imread(os.path.join(image_folder, images[0]))
    height, width, layers = frame.shape
    video = cv2.VideoWriter(video_name, cv2.VideoWriter_fourcc(*code), fps, (width, height))
    for image in tqdm(images, desc="Writing Video"):
        video.write(cv2.imread(os.path.join(image_folder, image)))
    video.release()


def image_list_to_video(video_name, image_list, fps):
    assert video_name.endswith(".mp4")
    assert len(image_list) > 0
    first_frame = np.asarray(image_list[0])
    if first_frame.dtype != np.uint8 or first_frame.ndim != 3 or first_frame.shape[2] != 3:
        raise ValueError(f"Video frames must be uint8 RGB images, got {first_frame.shape} {first_frame.dtype}")
    height, width = first_frame.shape[:2]
    if width % 2 or height % 2:
        raise ValueError(f"H.264 yuv420p requires even frame dimensions, got {width}x{height}")

    encoder = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(float(fps)),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            video_name,
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for image in tqdm(image_list, desc="Writing Video"):
            frame = np.asarray(image)
            if frame.shape != first_frame.shape or frame.dtype != np.uint8:
                raise ValueError(f"Video frames must match {first_frame.shape} {first_frame.dtype}, got {frame.shape} {frame.dtype}")
            encoder.stdin.write(np.ascontiguousarray(frame).tobytes())
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", errors="replace")
        if encoder.wait() != 0:
            raise RuntimeError(f"ffmpeg H.264 encoding failed: {stderr}")
    finally:
        if encoder.stdin is not None and not encoder.stdin.closed:
            encoder.stdin.close()
        if encoder.stderr is not None and not encoder.stderr.closed:
            encoder.stderr.close()
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()
