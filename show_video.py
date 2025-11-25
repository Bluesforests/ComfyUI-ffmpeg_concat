from __future__ import annotations

import os
import folder_paths
from typing_extensions import override

from comfy_api.latest import io, ui, ComfyExtension


class ShowVideo(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ShowVideo",
            display_name="Show Video",
            category="image/video",
            description=(
                "Shows a preview of an existing video file without saving anything. "
                "Supports relative paths under the output directory or absolute paths "
                "inside ComfyUI's output/temp directories."
            ),
            inputs=[
                io.String.Input(
                    "video_path",
                    default="",
                    force_input=True,
                    optional=True,
                    tooltip=(
                        "Video file path to preview. "
                        "You can use:\n"
                        "  • Relative path under output dir, e.g. 'video/ComfyUI_00000_.mp4'\n"
                        "  • Absolute path inside output/temp directories."
                    ),
                ),
            ],
            outputs=[],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, video_path: str) -> io.NodeOutput:
        if video_path is None:
            raise ValueError("video_path must not be None.")

        path = video_path.strip()
        if not path:
            raise ValueError("video_path must not be empty.")

        # 统一分隔符
        path = path.replace("\\", "/")

        folder_type = io.FolderType.output
        subfolder = ""
        file = ""

        if os.path.isabs(path):
            # 绝对路径：判断是不是在 output 或 temp 目录里
            abs_path = os.path.abspath(path)
            output_dir = os.path.abspath(folder_paths.get_output_directory())
            temp_dir = os.path.abspath(folder_paths.get_temp_directory())

            def _is_in(base: str, p: str) -> bool:
                try:
                    common = os.path.commonpath([base, p])
                except ValueError:
                    return False
                return common == base

            if _is_in(output_dir, abs_path):
                rel = os.path.relpath(abs_path, output_dir).replace("\\", "/")
                folder_type = io.FolderType.output
            elif _is_in(temp_dir, abs_path):
                rel = os.path.relpath(abs_path, temp_dir).replace("\\", "/")
                folder_type = io.FolderType.temp
            else:
                # 不在 ComfyUI 的可预览目录里，前端也看不到，直接报错更清晰
                raise ValueError(
                    "Absolute path is not inside ComfyUI output or temp directory.\n"
                    f"video_path: {video_path}\n"
                    f"output_dir: {output_dir}\n"
                    f"temp_dir:   {temp_dir}"
                )

            parts = rel.split("/")
        else:
            # 相对路径：按 output 目录下的相对路径处理
            parts = path.split("/")
            folder_type = io.FolderType.output

        if len(parts) == 1:
            subfolder = ""
            file = parts[0]
        else:
            subfolder = "/".join(parts[:-1])
            file = parts[-1]

        return io.NodeOutput(
            ui=ui.PreviewVideo(
                [
                    ui.SavedResult(
                        file,
                        subfolder,
                        folder_type,
                    )
                ]
            )
        )



# 节点注册映射
NODE_CLASS_MAPPINGS = {
    "ShowVideo": ShowVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ShowVideo": "Show Video",
}
