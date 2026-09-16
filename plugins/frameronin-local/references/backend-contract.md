# 后台扫描依据与边界
扫描仅使用 backend/app/{main,models,config,storage}.py 与 worker/{processor,tasks,watermark_remover}.py；未扫描前端或浏览器页面。封装调用API，不复制服务实现或模型。

## 能力
POST /jobs multipart file+params(JSON字符串)，返回job_id。GET /jobs/id查询；completed后 GET /jobs/id/result?format=zip得到sprite.png和index.json。索引含frame_size、sheet_size、frames[{i,x,y,w,h,t}]，spacing会产生格间距，应按索引取帧。
POST /matte multipart file，直接返回PNG。
POST /watermark multipart file，返回job_id；GET /watermark/id查询；完成后GET /watermark/id/result返回MP4。

## 参数
fps1–60，max_frames1–2000，padding/spacing0–64，columns1–64，matte_strength0–1。target_size.w/h必须大于两倍padding。layout_mode为fixed_columns或auto_square，crop_mode为none/tight_bbox/safe_bbox。默认视频上传上限200MB(服务配置可改)，允许mp4/mov/webm/avi/mkv；图片上限20MB。
不要使用frame_range.start_frame/end_frame：模型定义存在但处理器不读取。MAX_VIDEO_DURATION_SEC/MAX_SHEET_EDGE虽然定义但处理器不执行，不能称后台已限制这些值。客户端预检预计图集边长不超过16384，避免超大输出。

## 跳过
URL导入只出现在模型/注释，上传接口仍强制file；跳过。未发现Gem内部提示词、参考图知识库、人物动作生成、文本到图像、前端地图工具的后台实现；不封装或推断。无独立视频插帧、像素最近邻缩放、统一脚底锚点API；不声称具备。

## 验证
插件清单与技能规范验证、客户端健康/错误路径检查、视频抽帧端到端冒烟测试另见本次执行结果。HTTP成功不代表抠图或角标修复视觉合格。
