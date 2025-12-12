import os
import subprocess

# 正确的 VideoFromFile 导入位置（和官方 comfy_api 节点一致）
try:
    from comfy_api.input_impl import VideoFromFile
except Exception:
    VideoFromFile = None


class CutVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # 小圆点端口的 STRING：只能连线
                "video": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "forceInput": True,
                }),
                # 剪切模式：按时间 or 按帧数
                "mode": ([
                    "time",   # 按时间剪切
                    "frame",  # 按帧数剪切
                ], {
                    "default": "time",
                }),
                # ====== 时间模式参数 ======
                # 剪切起始时间（秒）
                "start_time": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1e9,
                    "step": 0.01,
                }),
                # 持续时长（秒），<= 0 表示从 start_time 一直到视频结束
                "duration": ("FLOAT", {
                    "default": 5.0,
                    "min": 0.0,
                    "max": 1e9,
                    "step": 0.01,
                }),
                # ====== 帧数模式参数 ======
                # 起始帧号（从 0 开始）
                "start_frame": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10_000_000,
                    "step": 1,
                }),
                # 要导出的帧数，<= 0 表示从 start_frame 一直到视频结束
                "frame_count": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10_000_000,
                    "step": 1,
                }),
                # 是否自动使用原视频 fps
                "fps_auto": ("BOOLEAN", {
                    "default": True,
                }),
                # 当 fps_auto 关闭时，使用这个 fps 数值
                "fps": ("FLOAT", {
                    "default": 30.0,
                    "min": 0.01,
                    "max": 1000.0,
                    "step": 0.01,
                }),
                # 是否保留原视频音频
                "keep_audio": ([
                    "yes",   # 保留音频
                    "no",    # 静音
                ], {
                    "default": "yes",
                }),
            }
        }

    # 输出：video_path（字符串） + video（VideoFromFile 对象）
    RETURN_TYPES = ("STRING", "VIDEO")
    RETURN_NAMES = ("video_path", "video")
    FUNCTION = "cut_video"
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
    def _next_cut_path(cls):
        """
        在 ComfyUI/output 下自动生成 cut_01.mp4, cut_02.mp4 这样的文件名。
        """
        output_dir = cls._get_output_dir()
        prefix = "cut_"
        ext = ".mp4"

        max_idx = 0
        try:
            for name in os.listdir(output_dir):
                if not name.startswith(prefix) or not name.endswith(ext):
                    continue
                middle = name[len(prefix):-len(ext)]  # 取中间数字
                if middle.isdigit():
                    idx = int(middle)
                    if idx > max_idx:
                        max_idx = idx
        except FileNotFoundError:
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

    def _make_video_object(self, path: str):
        """
        使用 comfy_api 的 VideoFromFile 生成 VIDEO 对象。
        """
        if VideoFromFile is None:
            raise RuntimeError(
                "未找到 comfy_api.input_impl.VideoFromFile，"
                "请确认 ComfyUI 已升级到带 VIDEO 类型的版本。"
            )
        return VideoFromFile(path)

    def _get_video_fps(self, video_path: str) -> float:
        """
        使用 ffprobe 读取原视频 fps，失败则返回 0。
        """
        try:
            # ffprobe 通常和 ffmpeg 一起安装
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            text = result.stdout.decode("utf-8", errors="ignore").strip()
            if not text:
                return 0.0

            # 可能是 "30000/1001" 这种形式
            if "/" in text:
                num_str, den_str = text.split("/", 1)
                num = float(num_str)
                den = float(den_str)
                if den == 0:
                    return 0.0
                return num / den
            else:
                return float(text)
        except Exception:
            # 任何错误都返回 0，让外面走兜底逻辑
            return 0.0

    def cut_video(
        self,
        video,
        mode,
        start_time,
        duration,
        start_frame,
        frame_count,
        fps_auto,
        fps,
        keep_audio,
        **kwargs,
    ):
        # video 是通过小圆点连进来的路径字符串
        if not video or not os.path.exists(video):
            raise FileNotFoundError(f"视频文件不存在: {video}")

        # 统一换算成「按时间剪切」所需的 start_time_sec / duration_sec
        if mode == "time":
            # ===== 按时间剪切 =====
            try:
                start_time_sec = float(start_time)
            except Exception:
                start_time_sec = 0.0
            if start_time_sec < 0:
                start_time_sec = 0.0

            try:
                duration_sec = float(duration)
            except Exception:
                duration_sec = 0.0
            if duration_sec < 0:
                duration_sec = 0.0

        else:
            # ===== 按帧数剪切 =====
            try:
                start_frame = int(start_frame)
            except Exception:
                start_frame = 0
            if start_frame < 0:
                start_frame = 0

            try:
                frame_count = int(frame_count)
            except Exception:
                frame_count = 0
            if frame_count < 0:
                frame_count = 0

            # 决定使用哪个 fps
            if fps_auto:
                fps_val = self._get_video_fps(video)
                # 如果自动获取失败（<=0），再退回到用户输入 fps
                if fps_val <= 0:
                    try:
                        fps_val = float(fps)
                    except Exception:
                        fps_val = 0.0
            else:
                try:
                    fps_val = float(fps)
                except Exception:
                    fps_val = 0.0

            if fps_val <= 0:
                raise ValueError("帧数模式下无法得到有效的 fps（自动检测和手动输入都无效）。")

            # 帧 -> 秒： n / fps
            start_time_sec = start_frame / fps_val
            duration_sec = frame_count / fps_val if frame_count > 0 else 0.0

        self._ensure_ffmpeg()

        out_path = self._next_cut_path()

        cmd = ["ffmpeg", "-y"]

        # 时间剪切：start_time_sec > 0 时才加 -ss
        if start_time_sec > 0:
            cmd.extend(["-ss", f"{start_time_sec}"])

        cmd.extend(["-i", video])

        # duration_sec > 0 时，加 -t；否则直到视频结束
        if duration_sec > 0:
            cmd.extend(["-t", f"{duration_sec}"])

        # 视频编码
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
        ])

        # 音频：根据 keep_audio 选择保留或静音
        if keep_audio == "yes":
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.append("-an")  # no audio

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
                "ffmpeg 剪切失败：\n"
                f"命令: {' '.join(cmd)}\n\n"
                f"stderr:\n{e.stderr.decode('utf-8', errors='ignore')}"
            ) from e

        # 返回 video_path + video（VideoFromFile 对象）
        video_obj = self._make_video_object(out_path)
        return (out_path, video_obj)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "CutVideo": CutVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CutVideo": "Cut Video (FFmpeg)",
}
