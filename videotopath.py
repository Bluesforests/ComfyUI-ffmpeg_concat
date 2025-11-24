import os
import tempfile
from typing import Any

import cv2
import numpy as np
import torch
import folder_paths

try:
    # 新版 ComfyUI
    from comfy_api.input_impl import VideoFromFile  # type: ignore
except Exception:
    try:
        # 有些 nightly 把它挪到了这里
        from comfy_api.latest_input_impl.video_types import VideoFromFile  # type: ignore
    except Exception:
        VideoFromFile = None  # type: ignore


class VideoToPath:
    """
    功能：
    - 输入：VIDEO 或 IMAGE（frames），二选一，优先使用 VIDEO。
    - 输出：video_path (STRING)
        * 有 VIDEO：解析出真实视频文件路径。
        * 只有 frames：把帧合成为一个临时 mp4，返回该 mp4 的路径。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                # 原生 Load Video 的输出
                "video": ("VIDEO",),
                # 其他节点输出的帧序列
                "frames": ("IMAGE",),
                # 合成视频时的帧率（只在使用 frames 时生效）
                "fps": ("INT", {
                    "default": 25,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    OUTPUT_IS_LIST = (False,)

    FUNCTION = "convert"
    CATEGORY = "Video/FFmpeg"

    # ====== VIDEO -> path ======

    @staticmethod
    def _extract_path_from_video(video: Any) -> str:
        """
        尝试从 VIDEO 类型里提取真正的文件路径。
        """
        # 1. 已经是字符串
        if isinstance(video, str):
            if folder_paths.exists_annotated_filepath(video):
                return folder_paths.get_annotated_filepath(video)
            return video

        # 2. list/tuple，取第一个继续解析
        if isinstance(video, (list, tuple)) and video:
            return VideoToPath._extract_path_from_video(video[0])

        # 3. 原生 VideoFromFile
        if VideoFromFile is not None and isinstance(video, VideoFromFile):
            for attr in ("video_path", "path", "file_path", "filename", "file"):
                value = getattr(video, attr, None)
                if isinstance(value, str) and value:
                    return value

            # 再保险一点：从 __dict__ 里找一个存在的路径
            try:
                for value in getattr(video, "__dict__", {}).values():
                    if isinstance(value, str) and os.path.exists(value):
                        return value
            except Exception:
                pass

        # 4. 兜底：常见属性名再试一轮
        for attr in ("video", "source", "data", "url"):
            value = getattr(video, attr, None)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, (list, tuple)) and value:
                try:
                    return VideoToPath._extract_path_from_video(value[0])
                except Exception:
                    pass

        raise ValueError(
            f"VideoToPath: cannot extract a filesystem path from VIDEO input of type {type(video)}.\n"
            "This node currently supports raw path strings and VideoFromFile objects."
        )

    # ====== frames -> mp4 path ======

    @staticmethod
    def _tensor_to_bgr_uint8(frame: Any) -> np.ndarray:
        """
        将 Comfy 的 IMAGE Tensor / 数组转换成 OpenCV 可写入的 BGR uint8 图像。
        """
        if isinstance(frame, torch.Tensor):
            img = frame
        else:
            img = torch.from_numpy(np.array(frame))

        # 去掉 batch 维度 (1, H, W, C) -> (H, W, C)
        if img.dim() == 4 and img.shape[0] == 1:
            img = img[0]

        # 保证在 [0, 1]
        img = img.clamp(0.0, 1.0)
        img = (img * 255.0).byte().cpu().numpy()  # (H, W, C), RGB

        # 转成 BGR
        if img.shape[-1] == 3:
            img = img[..., ::-1].copy()

        return img

    @staticmethod
    def _frames_to_video(frames, fps: int) -> str:
        """
        把 IMAGE 序列写成一个临时 mp4，返回该文件路径。
        """
        if isinstance(frames, torch.Tensor):
            # 假设形状为 (N, H, W, C)
            frame_list = [frames[i] for i in range(frames.shape[0])]
        else:
            frame_list = list(frames)

        if not frame_list:
            raise ValueError("VideoToPath: frames input is empty, cannot create video.")

        # 根临时目录
        if hasattr(folder_paths, "get_temp_directory"):
            root_tmp = folder_paths.get_temp_directory()
        else:
            root_tmp = os.path.join(folder_paths.get_output_directory(), "tmp_videos")

        os.makedirs(root_tmp, exist_ok=True)

        # 创建临时 mp4 文件名
        fd, video_path = tempfile.mkstemp(prefix="frames_", suffix=".mp4", dir=root_tmp)
        os.close(fd)

        # 用第一帧确定尺寸
        first = VideoToPath._tensor_to_bgr_uint8(frame_list[0])
        h, w = first.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, float(fps), (w, h))

        if not writer.isOpened():
            raise RuntimeError(f"VideoToPath: cannot open VideoWriter for {video_path}")

        # 写第一帧
        writer.write(first)

        # 写后续帧
        for f in frame_list[1:]:
            img = VideoToPath._tensor_to_bgr_uint8(f)
            if img.shape[0] != h or img.shape[1] != w:
                img = cv2.resize(img, (w, h))
            writer.write(img)

        writer.release()

        return video_path

    # ====== 主逻辑 ======

    def convert(self, video=None, frames=None, fps=25):
        """
        逻辑：
        - 若 video 不为空 -> 只用 video，忽略 frames 和 fps，输出视频文件路径。
        - 若 video 为空且 frames 有值 -> 把帧合成为 mp4，输出该 mp4 路径。
        - 若都没有 -> 报错。
        """
        # 两个都连上 -> 按要求以 video 为准
        if video is not None:
            video_path = self._extract_path_from_video(video)
            return (video_path,)

        # 只有 frames
        if frames is not None:
            video_path = self._frames_to_video(frames, int(fps))
            return (video_path,)

        # 都没输入
        raise ValueError(
            "VideoToPath: no input provided. Please connect either 'video' or 'frames'."
        )


NODE_CLASS_MAPPINGS = {
    "VideoToPath": VideoToPath,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoToPath": "video to path",
}
