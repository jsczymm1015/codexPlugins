---
name: frameronin-workflow
description: Use FrameRonin for sprite-sheet preview, frame arrangement, cutout and pixel-asset preparation when the user requests FrameRonin. This is a local browser workflow adapter, not an official FrameRonin MCP server or bundled FrameRonin backend.
---

# FrameRonin 素材工作流

来源：https://github.com/systemchester/FrameRonin
官方页面：https://frameronin.com （旧入口 https://systemchester.github.io/FrameRonin/）。

本插件是用户要求创建安装的本地工作流接入。没有内置 FrameRonin 后端、API key 或专用 MCP，不得宣称已安装完整服务。

使用场景：用户要求的序列帧预览、重排、合成、去背与像素素材检查。通过可用浏览器控制工具打开官方页面，先读取当前界面，再使用实际存在的功能；不能猜测API或点击位置。界面无法访问时明确记录阻塞。

上传前确认用户已授权该素材用于此服务；不上传整个私有项目。保留原素材，在副本上操作，下载结果后检查透明背景、方向顺序、帧数、脚底对齐和循环效果，再接入Unity。网页内付费或第三方生成能力不自动视为已授权。

对三国项目，必须保持用户批准的刘备、关羽、张飞身份和比例；不为了适配FrameRonin默认模板而重绘人物或降低图像尺寸。FrameRonin用于素材处理，不替代Unity运行时或Git。只有获得实际产物才报告处理完成。
