---
name: frameronin-video-watermark
description: 调用本地FrameRonin后台修复用户指定Seedance/即梦视频的角标区域；仅自动角落检测，不用于通用任意区域修复。
---

# 视频角标修复

使用中文。此技能依赖已运行的本地 FrameRonin 后台，不提供图像生成模型。当前已知项目 D:/godot-tools/FrameRonin，API http://127.0.0.1:8000；5173是前端。只处理用户明确指定的输入文件，输出到新文件，不覆盖原素材。不自动安装依赖、启动Docker、删除后台任务或调用外部服务。服务不可用则报告并跳过，不凭空补全能力。

插件根目录可由本 SKILL.md 向上两级定位。使用 Python 3 执行插件的 scripts/frameronin_client.py；只有标准库依赖。先运行 `python <插件根>/scripts/frameronin_client.py health`。服务可用后按下述命令调用。脚本不持续等待，提交得到job_id后用status检查；未完成时隔一段时间重查，不重复提交。后台状态存于内存，重启可能返回404，此时先报告状态丢失，不自动重传。

完成后下载到用户任务输出目录，实测图片尺寸、alpha与索引，查看主体边缘及连续性；只获得HTTP成功不能宣称效果合格。脚本API只使用本机回环地址，不能把这些接口当作授权向远程上传。用户未请求相应素材处理时，不因本技能存在而调用。

仅在用户要求处理该视频角标时执行。提交：`python <插件根>/scripts/frameronin_client.py submit-watermark --input <视频绝对路径>`。
状态：`python <插件根>/scripts/frameronin_client.py status --kind watermark --job-id <id>`。
完成：`python <插件根>/scripts/frameronin_client.py download --kind watermark --job-id <id> --output <新路径.mp4>`。
后台通过四角边缘密度与时间稳定性自动定位，使用OpenCV TELEA修复，FFmpeg重新编码H264并尝试保留音频。可能误判角落场景，必须检查实际处理区域和输出；不能保证无痕。内部函数虽有manual_region参数，HTTP接口未暴露，禁止编造参数。检测失败报告并跳过，不无限重试。
