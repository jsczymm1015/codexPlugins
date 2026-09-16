---
name: frameronin-image-matte
description: 通过本地FrameRonin的rembg u2net接口给用户指定图片抠图并保存透明PNG；不重绘角色或生成动作。
---

# 单图抠图

使用中文。此技能依赖已运行的本地 FrameRonin 后台，不提供图像生成模型。当前已知项目 D:/godot-tools/FrameRonin，API http://127.0.0.1:8000；5173是前端。只处理用户明确指定的输入文件，输出到新文件，不覆盖原素材。不自动安装依赖、启动Docker、删除后台任务或调用外部服务。服务不可用则报告并跳过，不凭空补全能力。

插件根目录可由本 SKILL.md 向上两级定位。使用 Python 3 执行插件的 scripts/frameronin_client.py；只有标准库依赖。先运行 `python <插件根>/scripts/frameronin_client.py health`。服务可用后按下述命令调用。脚本不持续等待，提交得到job_id后用status检查；未完成时隔一段时间重查，不重复提交。后台状态存于内存，重启可能返回404，此时先报告状态丢失，不自动重传。

完成后下载到用户任务输出目录，实测图片尺寸、alpha与索引，查看主体边缘及连续性；只获得HTTP成功不能宣称效果合格。脚本API只使用本机回环地址，不能把这些接口当作授权向远程上传。用户未请求相应素材处理时，不因本技能存在而调用。

执行：`python <插件根>/scripts/frameronin_client.py matte --input <图片绝对路径> --output <新路径.png>`。
支持PNG/JPG/JPEG/WebP，最大20MB。首次u2net会话可能下载模型，已缓存则复用；若模型缺失或网络不可用，报告并跳过，不替换模型。输出PNG需验证alpha确有透明像素并目视检查头发、白衣、细小手脚是否被误删。该接口无matte_strength参数。
