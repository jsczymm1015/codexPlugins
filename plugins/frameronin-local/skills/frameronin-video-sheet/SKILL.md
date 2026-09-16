---
name: frameronin-video-sheet
description: 将用户指定视频通过本地FrameRonin后台提取帧、抠图并导出Sprite Sheet与索引；用于视频转动画图集，不用于凭图片或名字生成动作。
---

# 视频转序列帧

使用中文。此技能依赖已运行的本地 FrameRonin 后台，不提供图像生成模型。当前已知项目 D:/godot-tools/FrameRonin，API http://127.0.0.1:8000；5173是前端。只处理用户明确指定的输入文件，输出到新文件，不覆盖原素材。不自动安装依赖、启动Docker、删除后台任务或调用外部服务。服务不可用则报告并跳过，不凭空补全能力。

插件根目录可由本 SKILL.md 向上两级定位。使用 Python 3 执行插件的 scripts/frameronin_client.py；只有标准库依赖。先运行 `python <插件根>/scripts/frameronin_client.py health`。服务可用后按下述命令调用。脚本不持续等待，提交得到job_id后用status检查；未完成时隔一段时间重查，不重复提交。后台状态存于内存，重启可能返回404，此时先报告状态丢失，不自动重传。

完成后下载到用户任务输出目录，实测图片尺寸、alpha与索引，查看主体边缘及连续性；只获得HTTP成功不能宣称效果合格。脚本API只使用本机回环地址，不能把这些接口当作授权向远程上传。用户未请求相应素材处理时，不因本技能存在而调用。

提交：`python <插件根>/scripts/frameronin_client.py submit-video --input <视频绝对路径> --params <参数JSON路径>`。
状态：`python <插件根>/scripts/frameronin_client.py status --kind jobs --job-id <id>`。
成功后下载：`python <插件根>/scripts/frameronin_client.py download --kind jobs --job-id <id> --output <新目录/result.zip>`；ZIP含sprite.png和index.json，无需分别获取。

参数以后台默认值为基础，仅改变用户指定值：fps12、max_frames300、target_size 256×256、padding4、spacing4、columns12、layout_mode fixed_columns、crop_mode tight_bbox、matte_strength0.6、transparent true。时间裁剪用frame_range.start_sec/end_sec。参阅 [后台能力与限制](../../references/backend-contract.md)。
后台总会执行rembg；transparent=false仅改变底色，不会跳过抠图。逐帧tight_bbox+LANCZOS缩放可能使角色尺度跳变，像素素材优先crop_mode=none以保留画面锚点，但不能承诺消除闪动。fps是视频采样率，不等于角色生成或补帧。不要把重复姿势当作新动作。
