# 美学 · 审美逻辑 · 人体交互逻辑 审计准则

> 依据同目录已存档专业资料（lawsofux.html / webaim-contrast.html / baymard-line-length.html / ixd-aesthetic-usability.html）。
> 审计员逐条判 PASS/RISK/FAIL，证据须为 文件:行号 / 截图区域 / 实测计算值。

## A 审美逻辑
- A1 视觉层级：字号阶梯(12/13/14/16/20/26/34) + 色彩对比引导视线；Von Restorff——关键元素（心灯/CTA）应孤立突出；衬线大标题为第一锚点。
- A2 留白与节奏：section 间距 ≥64px、卡片内边距 20-22px、网格 gap 一致；Gestalt 接近性——相关内容成组。
- A3 色彩和谐：暖类比色系（金#9A6414/橙#B4552D/玫瑰#A03A4E/褐文本）+ 苔绿点缀；强调色 ≤4；底/卡/文三档明度梯度一致；设计令牌单一可信源（globals→tailwind→DESIGN 三处值一致）。
- A4 排版对比：衬线(情感/标题/引文) vs 无衬线(正文) vs 等宽(时间戳) 分工清晰；行高 1.6-1.8；标题字距 +0.02em；微字 11-12px 不滥用。
- A5 美感可用性效应（ixd 材料）：美观提升感知可用性，但不得牺牲对比度——与 WCAG 硬指标并审。
- A6 负空间与「间」：有机层（菌丝/蘑菇/暮光）为背景低.opacity(≤0.16)，不与内容争锋。

## B 人体交互逻辑
- B1 Fitts 定律：命中尺寸 ≥40px（推荐 44px）——侧栏图标命中区、按钮、种子卡、人物 chips、发送钮。
- B2 Hick 定律：导航 11 项单列图标栏 + 悬浮展开标签，符合常见后台心智模型（Jakob 定律）；筛选 chips 计数降序分块。
- B3 反馈时效：hover/focus/active/运行态/结束态 反馈在 100-500ms 感知窗内；长任务给结束 toast 回执。
- B4 键盘/语义：可聚焦元素须有 :focus-visible 指示；交互型卡片为 button 或补 role+tabIndex+keydown+aria-expanded；图标按钮补 title/aria-label。
- B5 认知负荷/Miller：每页单任务、信息分块（Today 2 卡 slice(0,8)；记忆页先 chips 再三列卡）；避免同源数据重复展示。
- B6 可读性：卡内中文行宽 ≈20-30 字（baymard 50-75 英文字符量级内）；行高 ≥1.6；对比度 ≥4.5:1（含 alpha 底上的小字前景）。
- B7 无障碍：prefers-reduced-motion 对 JS 动画也降级（MotionConfig reducedMotion=user + setInterval 处 matchMedia）；焦点可见；非仅颜色传达（标签有文字）。
- B8 指针分层/动效自律：氛围层 pointer-events:none；常驻发光同屏 ≤5；动效 0.5-0.9s 长尾缓出，连续流动 linear 须有合约例外声明。
- B9 移动端：底栏 60px；导航单项 ≥44px（或横滚）；标签 9px 足读；触屏 hover 有替代。
- B10 记忆负担/Jakob：术语体系自洽；跨页组件词汇一致；时间戳本地化（勿裸 ISO T）。
