import os
import subprocess

# 正确的 VideoFromFile 导入位置（和官方 comfy_api 节点一致）
try:
    from comfy_api.input_impl import VideoFromFile
except Exception:
    VideoFromFile = None


class OverlayVideos:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # 小圆点端口的 STRING：使用 forceInput 让它只能连线，不能在 UI 里直接输入
                "bg_video": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "forceInput": True,
                }),
                "fg_video": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "forceInput": True,
                }),
                "x": ("INT", {
                    "default": 0,
                    "min": -4096,
                    "max": 4096,
                    "step": 1
                }),
                "y": ("INT", {
                    "default": 0,
                    "min": -4096,
                    "max": 4096,
                    "step": 1
                }),
                # fg_width / fg_height
                "fg_width": ("INT", {
                    "default": 320,
                    "min": 1,
                    "max": 4096,
                    "step": 1
                }),
                "fg_height": ("INT", {
                    "default": 240,
                    "min": 1,
                    "max": 4096,
                    "step": 1
                }),
                "keep_audio_from": ([
                    "background",   # 只保留背景视频音频
                    "foreground",   # 只保留前景视频音频
                    "mix",          # 简单混合两路音频
                    "none"          # 静音
                ], {
                    "default": "background"
                }),
            },
            "optional": {
                "external_audio": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "forceInput": True,
                }),
            }
        }

    # 输出：video_path（字符串） + video（VideoFromFile 对象）
    RETURN_TYPES = ("STRING", "VIDEO")
    RETURN_NAMES = ("video_path", "video")
    FUNCTION = "overlay"
    CATEGORY = "FFmpeg"

    # 输出到 comfyui/output（当前文件往上两层）
    @staticmethod
    def _get_output_dir():
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    @classmethod
    def _next_overlay_path(cls):
        """
        在 ComfyUI/output 下自动生成 overlay_01.mp4, overlay_02.mp4 这样的文件名。
        """
        output_dir = cls._get_output_dir()
        prefix = "overlay_"
        ext = ".mp4"

        max_idx = 0
        try:
            for name in os.listdir(output_dir):
                if not name.startswith(prefix) or not name.endswith(ext):
                    continue
                middle = name[len(prefix):-len(ext)]  # 取中间的数字部分
                if middle.isdigit():
                    idx = int(middle)
                    if idx > max_idx:
                        max_idx = idx
        except FileNotFoundError:
            # 理论上 _get_output_dir 已经确保存在，这里只是兜底
            os.makedirs(output_dir, exist_ok=True)

        next_idx = max_idx + 1
        filename = f"{prefix}{next_idx:02d}{ext}"
        return os.path.join(output_dir, filename)

    def _ensure_ffmpeg(self):
        """简单检测 ffmpeg 是否可用。"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except Exception as e:
            raise RuntimeError("无法调用 ffmpeg，请确认已安装并加入系统 PATH。") from e

    def _build_audio_args_keep_mode(self, keep_audio_from: str):
        """
        根据 keep_audio_from 构造 -filter_complex 的音频相关部分
        和输出映射参数（仅在没有 external_audio 时使用）。
        """
        # 返回 (extra_filter, extra_maps, need_audio_codec)
        if keep_audio_from == "background":
            # 只用 0:a
            return "", ["-map", "0:a?"], True
        elif keep_audio_from == "foreground":
            # 只用 1:a
            return "", ["-map", "1:a?"], True
        elif keep_audio_from == "mix":
            # amix 混合
            extra_filter = ";[0:a][1:a]amix=inputs=2:normalize=0[aout]"
            return extra_filter, ["-map", "[aout]"], True
        else:  # none
            return "", [], False  # 不输出音频

    def _build_audio_args_external(self):
        """
        使用 external_audio 时的音频映射参数：
        - 假设 external_audio 是第 3 个输入（index 2）
        """
        # 返回 (extra_filter, extra_maps, need_audio_codec)
        # 不需要额外的 filter_complex，只映射 2:a
        return "", ["-map", "2:a?"], True

    def _make_video_object(self, path: str):
        """
        使用 comfy_api 的 VideoFromFile 生成 VIDEO 对象。
        """
        if VideoFromFile is None:
            raise RuntimeError(
                "未找到 comfy_api.input_impl.VideoFromFile，"
                "请确认 ComfyUI 已升级到带 VIDEO 类型的版本。"
            )
        # 直接用文件路径构造 VideoFromFile
        return VideoFromFile(path)

    def overlay(
        self,
        bg_video,
        fg_video,
        x,
        y,
        fg_width,
        fg_height,
        keep_audio_from,
        external_audio=None
    ):
        # bg_video / fg_video / external_audio 都是字符串路径（通过小圆点端口连进来）
        if not bg_video or not os.path.exists(bg_video):
            raise FileNotFoundError(f"背景视频文件不存在: {bg_video}")
        if not fg_video or not os.path.exists(fg_video):
            raise FileNotFoundError(f"前景视频文件不存在: {fg_video}")

        external_audio_path = None
        if external_audio is not None and str(external_audio).strip():
            external_audio_path = str(external_audio).strip()
            if not os.path.exists(external_audio_path):
                raise FileNotFoundError(f"外接音频文件不存在: {external_audio_path}")

        self._ensure_ffmpeg()

        # 用数字排序的方式命名：overlay_01.mp4, overlay_02.mp4, ...
        out_path = self._next_overlay_path()

        # 视频部分 filter_complex：缩放 + 叠加
        # [1:v]scale=fg_width:fg_height[fg];[0:v][fg]overlay=x:y:shortest=1[outv]
        video_filter = (
            f"[1:v]scale={fg_width}:{fg_height}[fg];"
            f"[0:v][fg]overlay={x}:{y}:shortest=1[outv]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", bg_video,
            "-i", fg_video,
        ]

        # 如果有 external_audio，则 keep_audio_from 自动失效，音频直接来自 external_audio
        if external_audio_path:
            cmd.extend(["-i", external_audio_path])
            extra_audio_filter, audio_maps, need_audio_codec = self._build_audio_args_external()
        else:
            extra_audio_filter, audio_maps, need_audio_codec = self._build_audio_args_keep_mode(
                keep_audio_from
            )

        filter_complex = video_filter + extra_audio_filter

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
        ])

        # 音频映射
        cmd.extend(audio_maps)

        # 有音频的情况才指定编码器
        if need_audio_codec:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.append(out_path)

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "ffmpeg 叠加失败：\n"
                f"命令: {' '.join(cmd)}\n\n"
                f"stderr:\n{e.stderr.decode('utf-8', errors='ignore')}"
            ) from e

        # 返回 video_path + video（VideoFromFile 对象）
        video_obj = self._make_video_object(out_path)
        return (out_path, video_obj)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "OverlayVideos": OverlayVideos,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OverlayVideos": "Overlay Videos (FFmpeg)",
}
