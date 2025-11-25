import os
import subprocess

# 尝试导入 ComfyUI 的 VideoFromFile 类型，用于构造 VIDEO 对象
try:
    # 新版官方路径
    from comfy_api.input_impl import VideoFromFile
except ImportError:
    try:
        # 一些版本的兼容路径
        from comfy_api.latest._input_impl.video_types import VideoFromFile  # type: ignore
    except ImportError:
        VideoFromFile = None


class ConcatVideos:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path1": ("STRING", {"forceInput": True}),

                # mode: 默认 reencode，"lossless" 改名为 "fast"
                "mode": (["reencode", "fast"],),

                # 目标分辨率 / fps（仅 reencode 模式生效；0 表示自动用第一个视频）
                "target_width": ("INT", {"default": 0, "min": 0, "max": 7680}),
                "target_height": ("INT", {"default": 0, "min": 0, "max": 4320}),
                "target_fps": ("INT", {"default": 0, "min": 0, "max": 240}),

                "filename_prefix": ("STRING", {"default": "concat_"}),
                "format": (["mp4", "mov", "webm"],),
            },
            "optional": {
                "video_path2": ("STRING", {"forceInput": True}),
                "video_path3": ("STRING", {"forceInput": True}),
                "video_path4": ("STRING", {"forceInput": True}),
                "external_audio_path": ("STRING", {"forceInput": True}),

                # 外部音频时是否使用 -shortest，默认开启，UI 最后一个
                "use_shortest": ("BOOLEAN", {"default": True}),
            },
        }

    # 两个输出：路径 + video
    # 第二个输出类型改为 "VIDEO"
    RETURN_TYPES = ("STRING", "VIDEO")
    RETURN_NAMES = ("output_path", "video")
    FUNCTION = "concat"
    CATEGORY = "FFmpeg"

    # ----------------- 工具方法 -----------------

    def _get_output_dir(self):
        """
        获取 ComfyUI 根目录下的 output 目录，并确保存在。
        """
        node_dir = os.path.dirname(__file__)
        comfy_root = os.path.abspath(
            os.path.join(node_dir, os.pardir, os.pardir)
        )
        out_dir = os.path.join(comfy_root, "output")
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def _get_filename_with_counter(self, filename_prefix, format):
        """
        生成带数字计数器的文件名，类似 ComfyUI core 的 save image：
        prefix_00001.mp4, prefix_00002.mp4, ...
        """
        out_dir = self._get_output_dir()

        counter = 1
        existing_files = [
            f for f in os.listdir(out_dir)
            if f.startswith(filename_prefix) and f.endswith(f".{format}")
        ]

        if existing_files:
            numbers = []
            for f in existing_files:
                name_part = f[len(filename_prefix):-len(f".{format}")].strip("_")
                if name_part.isdigit():
                    numbers.append(int(name_part))

            if numbers:
                counter = max(numbers) + 1

        filename = f"{filename_prefix}_{counter:05d}.{format}"
        return os.path.join(out_dir, filename)

    def _probe_video_info(self, path):
        """
        使用 ffprobe 获取视频的宽高和平均帧率。
        返回字典: {width, height, fps}；失败时返回 None。
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            lines = out.decode("utf-8", errors="ignore").strip().splitlines()
            if len(lines) < 3:
                return None
            width = int(lines[0])
            height = int(lines[1])
            fr = lines[2]  # 形如 "30000/1001" 或 "25/1"
            num, den = (0, 0)
            if "/" in fr:
                n, d = fr.split("/", 1)
                try:
                    num = int(n)
                    den = int(d)
                except ValueError:
                    num, den = 0, 0
            fps = None
            if num > 0 and den > 0:
                fps = num / den
            return {
                "width": width,
                "height": height,
                "fps": fps,
            }
        except Exception:
            return None

    def _build_filter_concat_cmd(
        self,
        videos,
        external_audio_path,
        output_path,
        target_width,
        target_height,
        target_fps,
        use_shortest,
    ):
        """
        reencode 模式：使用 filter_complex concat 拼接多个视频，自动/手动统一分辨率 / 帧率。
        - target_width/height/fps > 0 时使用用户指定值；
          否则以第一个视频为基准（探测失败则默认 1920x1080@30fps）。
        - 视频编码：libx264, CRF 18, preset medium。
        - external_audio_path 存在时，将该音轨作为输出音频；
          use_shortest 控制是否加 -shortest。
        """
        if len(videos) == 0:
            raise ValueError("没有可拼接的视频。")

        # 先探测第一个视频的信息（作为 auto 模式的基准）
        probe = self._probe_video_info(videos[0])

        # 决定最终目标分辨率
        if isinstance(target_width, int) and target_width > 0 and \
           isinstance(target_height, int) and target_height > 0:
            target_w = target_width
            target_h = target_height
        else:
            if probe is not None:
                target_w = probe["width"] or 1920
                target_h = probe["height"] or 1080
            else:
                target_w, target_h = 1920, 1080

        # 决定最终目标 fps
        if isinstance(target_fps, int) and target_fps > 0:
            fps_int = target_fps
        else:
            if probe is not None and probe["fps"]:
                fps_int = max(1, int(round(probe["fps"])))
            else:
                fps_int = 30

        cmd = ["ffmpeg", "-y"]

        # 添加视频输入
        for v in videos:
            cmd += ["-i", v]

        use_external_audio = (
            isinstance(external_audio_path, str)
            and external_audio_path.strip() != ""
        )

        audio_input_index = None
        if use_external_audio:
            audio_input_index = len(videos)
            cmd += ["-i", external_audio_path]

        # 构建 filter_complex
        filter_parts = []
        for idx in range(len(videos)):
            filter_parts.append(
                f"[{idx}:v:0]"
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,"
                f"fps={fps_int}"
                f"[v{idx}]"
            )

        concat_inputs = "".join(f"[v{i}]" for i in range(len(videos)))
        filter_parts.append(
            f"{concat_inputs}concat=n={len(videos)}:v=1:a=0[outv]"
        )
        filter_complex = "; ".join(filter_parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[outv]",
        ]

        # 处理外部音频：由 use_shortest 控制是否加 -shortest
        if use_external_audio:
            cmd += ["-map", f"{audio_input_index}:a:0"]
            if use_shortest:
                cmd += ["-shortest"]
        else:
            # 没有外部音频时，明确禁用音轨
            cmd += ["-an"]

        # 编码设置：统一重编码视频；音频按需编码
        cmd += [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
        ]

        if use_external_audio:
            cmd += [
                "-c:a", "aac",
                "-b:a", "192k",
            ]

        cmd.append(output_path)
        return cmd

    def _build_fast_concat_cmd(
        self,
        videos,
        external_audio_path,
        output_path,
        use_shortest,
    ):
        """
        fast 模式：无论条件如何，一律按「lossless/fast」方式处理。
        - 使用 concat demuxer：-f concat -safe 0 -i list.txt
        - 仅做流拷贝：-c copy 或 -c:v copy -c:a copy
        - 不做缩放、不改帧率、不统一参数（要求输入视频本身规格兼容）。
        - target_width / target_height / target_fps 在此模式下会被忽略。

        用完后自动删除临时 list 文件。
        """
        if len(videos) == 0:
            raise ValueError("没有可拼接的视频。")

        out_dir = self._get_output_dir()
        list_file = os.path.join(out_dir, "temp_concat_list_fast.txt")

        # 写入 concat 列表
        with open(list_file, "w", encoding="utf-8") as f:
            for v in videos:
                abs_path = os.path.abspath(v).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
        ]

        use_external_audio = (
            isinstance(external_audio_path, str)
            and external_audio_path.strip() != ""
        )

        if use_external_audio:
            cmd += ["-i", external_audio_path]
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
            if use_shortest:
                cmd += ["-shortest"]
            cmd += ["-c:v", "copy", "-c:a", "copy"]
        else:
            cmd += ["-c", "copy"]

        cmd.append(output_path)

        # 返回命令 + list 文件路径，用于执行后删除
        return cmd, list_file

    # ----------------- 主函数 -----------------

    def concat(
        self,
        video_path1,
        mode,
        target_width,
        target_height,
        target_fps,
        filename_prefix,
        format,
        video_path2=None,
        video_path3=None,
        video_path4=None,
        external_audio_path=None,
        use_shortest=True,
    ):
        # 收集有效的视频输入（最多 4 个），支持 None（未连接）
        raw_videos = [video_path1, video_path2, video_path3, video_path4]
        videos = []
        for v in raw_videos:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                videos.append(s)

        if len(videos) < 1:
            raise ValueError("至少需要提供一个视频路径（请连接上游节点到 video_path1 / video_path2 等）。")

        # 生成带计数器的输出路径
        output_path = self._get_filename_with_counter(filename_prefix, format)

        # fast 模式：无条件走无损/快速 concat
        if mode == "fast":
            if len(videos) == 1 and not external_audio_path:
                # 只有一个视频 & 无外部音频：直接 copy 封装
                cmd = [
                    "ffmpeg", "-y",
                    "-i", videos[0],
                    "-c", "copy",
                    output_path,
                ]
                subprocess.run(cmd, check=True)
            else:
                # 多视频 or 单视频 + 外部音频 → 使用 concat demuxer
                cmd, list_file = self._build_fast_concat_cmd(
                    videos=videos,
                    external_audio_path=external_audio_path,
                    output_path=output_path,
                    use_shortest=use_shortest,
                )
                subprocess.run(cmd, check=True)
                try:
                    os.remove(list_file)
                except:
                    pass

        else:
            # reencode 模式：使用 filter_complex concat
            cmd = self._build_filter_concat_cmd(
                videos=videos,
                external_audio_path=external_audio_path,
                output_path=output_path,
                target_width=target_width,
                target_height=target_height,
                target_fps=target_fps,
                use_shortest=use_shortest,
            )
            subprocess.run(cmd, check=True)

        # 这里构造 VIDEO 对象：
        # 如果有 comfy_api 的 VideoFromFile，就用它；否则退化为字符串路径
        if VideoFromFile is not None:
            video_obj = VideoFromFile(output_path)
        else:
            video_obj = output_path

        return (output_path, video_obj)


NODE_CLASS_MAPPINGS = {
    "ConcatVideos": ConcatVideos
}
