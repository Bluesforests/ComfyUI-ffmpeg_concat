from .concat_videos_path import NODE_CLASS_MAPPINGS as CONCATPATH_M
from .videotopath import NODE_CLASS_MAPPINGS as PATH_M
from .show_video import NODE_CLASS_MAPPINGS as SHOW_M


NODE_CLASS_MAPPINGS = {
    **CONCATPATH_M,
    **PATH_M,
    **SHOW_M,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    k: k for k in NODE_CLASS_MAPPINGS.keys()
}