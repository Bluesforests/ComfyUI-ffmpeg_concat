[中文] | [English](./README_EN.md)

# ConcatVideos — ComfyUI 视频拼接节点（支持多格式、不同帧率、外部音频）
- ConcatVideos 是一个基于 ffmepg 能力的comfyui 拼接视频的节点，支持 1–4 个视频文件输入，可自动统一分辨率/帧率进行稳定拼接，或以无损/高速方式快速串联视频。


## 主要特性

### **concat video 节点（两种拼接模式）**

---

#### 1. **reencode（强兼容）——默认** 
* 合并时可以兼容不同的分辨率、帧率、编码格式， 
* 如果不设置新的分辨率和帧率，则自动按第一个视频或指定的目标分辨率/帧率进行统一 
* 使用 filter_complex concat, 适合模型生成片段拼接、混合来源视频等复杂场景

---

#### 2. fast（无损高速）
* 全程使用 ffmpeg的 lossless模式 -c copy（流拷贝）无损拼接 <br />
* 非常快、不降画质、不改帧率 <br />

**<p>fast 模式推荐用于：</p>**

- 视频分辨率、帧率相同。
- 工作流跑出来规格一致的视频，推荐用fast 模式。
- 如果输入视频规格不同，会导致拼接失败，拼接不完整和花屏。

---

#### 3. 单视频链接
- 可以填加音频 
- 可以更改视频格式

### **外部音频支持** <br />
可输入单独的音频文件（music / bgm / narration），并选择是否使用 -shortest 截断视频长度。<br />
shortest默认开启。

### **视频叠加节点**<br />
- overlay videos node。
- 使用 ffmpeg 的 overlay 滤镜将视频 A（前景）精确叠加到视频 B（背景）的指定位置。
- FFmpeg 的 overlay 滤镜原生支持 Alpha 通道合成，只要输入流包含有效 alpha，它会自动进行透明叠加。

---

## 参数说明

### **1. 模式**
   
| 模式             | 行为                                 | 推荐场景                           |
|------------------|--------------------------------------|------------------------------------|
| reencode（默认） | 重编码、统一分辨率/帧率、最稳定     | 混合不同来源的视频、模型生成片段拼接 |
| fast             | 无损流拷贝，极快                     | 输入视频规格完全一致               |

fast 模式执行的ffmpeg 命令是 `ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4` <br />
优点：极快 <br />
缺点：输入视频必须规格相同，否则 FFmpeg 无法无损拼接，导致拼接出错。<br />

### **2. target_width / target_height / target_fps** <br />
- 设置输出分辨率
- 仅在 reencode 模式生效
- 默认为 0 = 自动按第一个视频适配

### **3. external_audio_path（可选音频）**
- 可输入 bgm、旁白、音乐等
- 会覆盖所有输入视频原音轨
- 必须使用 reencode 模式

### **4. use_shortest**
- 外部音频时有效
  
| 值           | 行为                                       |
|--------------|--------------------------------------------|
| True（默认） | 视频长度 = 音频长度，视频保证不超出音频   |
| False        | 视频按拼接长度输出，音频结束后静音       |

## 安装步骤
1. 先确保电脑已经安装了ffmpeg, 并配了环境变量。<br />
2. 打开comfyui的目录，运行cmd <br /> 
```python
cd ComfyUI/custom_nodes 
git clone https://github.com/Bluesforests/ComfyUI-ffmpeg_concat
```

3. 重启comfyui

## 使用参考
![exampleA](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20A.png)
![exampleB](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20B.png)
![exampleC](https://github.com/Bluesforests/ComfyUI-ffmpeg_concat/blob/main/example/example%20C.png)


## Thanks
谢谢企鹅帮我测试 Demo