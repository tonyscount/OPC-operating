---
name: dribbble-ui-designer
version: 1.2.1
description: "Dribbble 品质 UI 设计引擎。当用户要求设计 UI 界面、网页、APP 页面、Dashboard、落地页、或是要求 Dribbble 风格、减少 AI 感、高级感设计、去模板化、像大厂出品时触发。核心能力：生成具备 Dribbble 社区水准的 UI 设计 HTML/CSS；系统性消除 AI 生成感的视觉特征；注入真实品牌个性的色彩/字体/质感体系。适用场景：SaaS 产品页、金融 Dashboard、电商 Landing、社交 APP 界面、设计灵感参考。"
---

# Dribbble UI Designer — 消除 AI 感的设计引擎

## 概述

此 Skill 的目标是让生成的 UI 设计达到 Dribbble 社区中 "Trending" 页面的视觉品质
——不是简单的渐变+圆角卡片堆砌，而是有设计灵魂、有品牌辨识度、经得起专业设计师审视的作品。

核心理念：**AI 感来自偷懒的设计决策。每次设计决策都要有理由。**

---

## 触发词

### 中文触发词
- "Dribbble 风格" / "dribbble 设计" / "类似 dribbble"
- "UI 设计" / "界面设计" / "网页设计" / "APP 页面设计"
- "减少 AI 感" / "去 AI 味" / "不要模板感"
- "高级感" / "设计感" / "大厂设计"
- "Dashboard" / "后台管理" / "数据看板"
- "Landing Page" / "落地页" / "产品页"
- "设计灵感" / "设计参考" / "模仿 XX 的设计"

### 英文触发词
- "dribbble style" / "dribbble quality" / "like dribbble"
- "UI design" / "web design" / "app design"
- "reduce AI feel" / "professional design"
- "premium design" / "design inspiration"

---

## 核心工作流

### Phase 1 — 需求分析

在动手之前，必须先回答以下问题（可在思维中推理，但关键决策需与用户确认）：

1. **设计对象**: 这是什么产品/页面？（SaaS、电商、社交、金融、工具？）
2. **品牌人格**: 现代科技？温暖生活？专业严肃？年轻潮流？
3. **目标用户**: 谁在看？（管理者、开发者、消费者、设计师？）
4. **核心任务**: 这页面的第一目标是什么？（展示数据？促成转化？内容浏览？）
5. **Dribbble 参考风格**: 用户是否提供了参考？如未提供，根据品牌人格推荐 2-3 个风格方向。

### Phase 2 — 设计决策（决策表）

每一项都必须做出**有理由的决策**。按顺序执行，加载对应 reference：

| # | 决策维度 | 核心约束 | 加载参考 |
|---|----------|----------|----------|
| 2.1 | **色彩系统** | 主色不撞 AI 色库 (`#6C63FF`/`#667EEA`/`#764BA2`禁止)；背景非纯白；至少 1 个非常规强调色；渐变最多 1 处且非蓝紫系 | `references/color-palettes.md` |
| 2.2 | **字体系统** | 标题/正文必须不同字体；字号用 modular scale (1.25)；至少 2 种字重 | `references/typography-guide.md` |
| 2.3 | **质感系统** | 从 6 大质感中选 1-2 种（禁止全不选） | `references/design-systems.md` |
| 2.4 | **布局策略** | 禁止三列等宽网格；必须用不对称布局；至少 1 处留白≥30% | `references/dribbble-patterns.md` |

**色彩对比度**: 确保 WCAG AA（正文 4.5:1，大文本 3:1）

### Phase 3 — 消除 AI 感（必须逐项检查）

生成代码之前，必须通过以下检查清单。任何未通过项必须修复：

```
□ 无蓝紫渐变 (无 #667EEA → #764BA2 等组合)
□ 无纯白背景 (背景色不能是 #FFF 或 #FFFFFF)
□ 无全圆角统一 (不同元素使用不同圆角值)
□ 无全部等间距 (padding/gap 至少使用 3 种不同值)
□ 无默认系统字体栈 (标题和正文使用不同字体)
□ 无全统一阴影 (至少 3 种不同阴影参数)
□ 无 Lorem Ipsum (所有文字内容必须真实、有意义)
□ 无 Heroicons 风格图标 (优先使用阿里 iconfont 填充风格、emoji、内联 SVG)
□ 无标准三列卡片网格
□ 无对称居中对齐 (至少有一处左对齐或右对齐的不对称布局)
□ 有至少一个 "设计亮点"（独特视觉元素）
□ 有至少一种非常规交互（hover 状态、微动效、滚动视差）
```

→ 详细反模式参考: `references/anti-ai-patterns.md`

### Phase 4 — 代码生成

生成独立的 HTML 文件，包含内联 CSS 和 JS：

**HTML 结构要求:**
- 语义化标签 (header, nav, main, section, article, footer)
- 数据属性标记关键元素 (`data-design-token="primary"` 等)
- 使用真实内容文本

**CSS 要求:**
- 使用 CSS 自定义属性 (`--color-primary` 等) 构建设计 token
- 至少使用 1 种 CSS 高级特性：`backdrop-filter`, `clip-path`, `mask`, `mix-blend-mode`, `@container query`
- 动画使用 `@keyframes` + `cubic-bezier()` 自定义缓动
- 响应式断点至少覆盖 mobile / tablet / desktop
- 使用 `@font-face` 或 Google Fonts 引入自定义字体

**JS 要求（可选但加分）:**
- 至少 1 处微交互：hover 变换、滚动触发动效、光标跟随、计数器动画
- 使用 `IntersectionObserver` 或 `requestAnimationFrame`

### Phase 5 — 迭代优化

生成后执行自我审查：

1. 用 "AI 感检查清单" 逐项复查
2. 检查是否有至少 1 处让人 "哇" 的设计细节
3. 确认品牌人格与视觉呈现一致
4. 向用户展示时说明设计决策理由

---

## 输出标准

每个设计输出应包含：

1. **设计说明** (2-3 句): 品牌人格、色彩选择理由、布局策略
2. **AI 感消除要点** (列表): 本次设计做了哪些反 AI 的刻意选择
3. **完整 HTML 文件**: 可独立运行的页面
4. **"为什么这样设计"**: 折叠区附带关键设计决策的推理

> **输出范例**: 见 `assets/example-output.html` — 一个完整的 SaaS 控制台页面，展示了所有 Phase 的执行结果和注解。

---

## 参考资料

此 Skill 包含以下参考文件，根据需要加载：

| 文件 | 内容 | 何时加载 |
|------|------|----------|
| `references/anti-ai-patterns.md` | AI 生成感反模式大全，含检查清单 | Phase 3 检查时必须加载 |
| `references/color-palettes.md` | 28 组主题配色 + 5 组暗色模式 + 4 组安全渐变 = 37 组方案 | Phase 2.1 选色时加载 |
| `references/typography-guide.md` | 字体配对方案与排版阶梯 | Phase 2.2 选字时加载 |
| `references/design-systems.md` | 6 大质感系统实现指南 | Phase 2.3 选质感时加载 |
| `references/dribbble-patterns.md` | 典型布局模式与实现 | Phase 2.4 布局时加载 |
| `references/icon-resources.md` | 图标方案指南 — iconfont/Emoji/SVG/CSS 四合一，含 15 大行业关键字 | Phase 3 P9 检查 / Phase 4 生成图标时加载 |

---

## 边界

- 此 Skill 生成的是 HTML/CSS 原型设计，不是生产级代码
- 复杂交互（拖拽、实时协作等）超出范围，告知用户需额外开发
- 不替代 Figma/Sketch 等专业设计工具
- 图片资源使用 CSS 绘制、SVG 或 emoji，不依赖外部图片 CDN（避免加载失败）
- 字体通过 Google Fonts CDN 引入，如加载失败降级到系统字体
- 图标优先使用阿里 iconfont (Symbol 引用) 或 emoji，iconfont 链接需用户提供项目 ID，生成时使用占位符 `font_XXXXXXX`
