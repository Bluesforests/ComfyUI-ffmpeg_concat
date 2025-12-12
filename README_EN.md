[中文](./README.md) | [English]

# ConcatVideos — ComfyUI Video concatenation, overlay, and cutting nodes

**(Supports multiple formats, different frame rates, and external audio)**

ConcatVideos is a ComfyUI node powered by **FFmpeg**, designed for stable and flexible video concatenation.
It supports **1–4 video inputs**, can automatically unify resolutions/frame rates for stable merging,
or concatenate videos quickly in a **lossless/high-speed mode**.

**Update: December 12, 2025**

- **Overlay video**: Video overlay with support for transparent videos.
- **Cut video**: Video trimming, supporting both time-based and frame-based cutting.

## Key Features

### **Two Concatenation Modes**

---

#### 1. **reencode (Highly Compatible) — Default**

* Supports videos with different resolutions, frame rates, and codecs
* If no target resolution/frame rate is set, the output automatically follows the first video
  or any user-specified target settings
* Uses `filter_complex concat`
* Ideal for stitching model-generated clips or combining mixed-source videos

---

#### 2. **fast (Lossless & High-Speed)**

* Uses FFmpeg's `-c copy` for **lossless stream copy**
* Extremely fast, no quality loss, no frame rate changes

**Recommended for:**

* Videos with **identical resolution and frame rate**
* Workflow-generated videos with consistent specs
* Note: If input specs differ, concatenation may fail or produce corrupted output

---

### **External Audio Support**

You may provide a separate audio file (music / BGM / narration).
You can also choose whether to use `-shortest` to trim the video duration.
`shortest = True` by default.

---

### **Video Overlay Node**<br />
- Overlay videos node.  
- Uses FFmpeg's `overlay` filter to precisely composite Video A (foreground) onto Video B (background) at a specified position.  
- FFmpeg’s `overlay` filter natively supports alpha channel blending—transparent overlay is applied automatically as long as the input stream contains a valid alpha channel.
- ⚠️ When overlaying transparent videos (with alpha channel), please connect the **video path** directly using a **String** node, because ComfyUI does not properly support transparent videos, which can cause the transparency to be lost.

---

## Parameter Description

### **1. Mode**

| Mode               | Behavior                                               | Recommended Use Case                       |
| ------------------ | ------------------------------------------------------ | ------------------------------------------ |
| reencode (default) | Re-encodes, unifies resolution/frame rate; most stable | Mixed-source videos, model-generated clips |
| fast               | Lossless stream copy; extremely fast                   | Inputs with fully identical specs          |

The FFmpeg command used in **fast** mode:

```
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

**Pros:** Ultra-fast
**Cons:** All input videos must have identical specs; otherwise FFmpeg cannot concatenate losslessly.

---

### **2. target_width / target_height / target_fps**

* Sets the output resolution and frame rate
* Only works in **reencode** mode
* Default: `0` (automatically follows the first video)

---

### **3. Single Video**

* Audio can be added
* Video format can be changed

### **4. external_audio_path (Optional)**

* For adding BGM, narration, music, etc.
* Overrides all original audio tracks
* Requires **reencode** mode

---

### **5. use_shortest**

Only effective when external audio is used.

| Value          | Behavior                                                          |
| -------------- | ----------------------------------------------------------------- |
| True (default) | Video length = audio length; prevents overshooting                |
| False          | Video follows concatenated length; silence added after audio ends |

---

## Installation

1. Ensure **FFmpeg** is installed and added to your system PATH
2. Open your ComfyUI directory and run:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Bluesforests/ComfyUI-ffmpeg_concat
```

3. Restart ComfyUI

---

## Usage Examples

![exampleA](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20A.png)
![exampleB](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20B.png)
![exampleC](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20C.png)

## Thanks
Thank you, PenguinAI, for helping me test the demo!

