# AI 生成感反模式大全

本文档列出 AI 生成 UI 最常见的视觉模式——这些模式正是"AI 感"的来源。
设计时务必逐一规避。

---

## 色彩反模式

### P1: 蓝紫渐变统治
最常见、最致命的 AI 特征。任何形式的蓝→紫/紫→粉渐变（`#667EEA`、`#6C63FF`、`#764BA2`、`#A855F7`）
都让设计看起来像"AI 生成的"。

**禁止的渐变组合:**
```
#667EEA → #764BA2   (标准 AI 渐变)
#6C63FF → #A855F7   (变体)
#667EEA → #F093FB   (蓝→粉)
#4F46E5 → #9333EA   (Tailwind indigo→purple)
```

**替代方案:**
- 单色弥散（纯色大色块 + 低透明度叠加）
- 对角线渐变（角度 30°-60°，不做 0°/90°/180°）
- 多色渐变（3+ 色标，使用非常规色）
- 完全不用渐变，改用质感系统

### P2: 纯白/纯黑背景
`#FFFFFF` 背景 + `#000000` 文字 → 极强 AI 感。

**替代:** 背景使用 `#FAFBFC`(冷灰白)、`#FDFBF7`(暖白)、`#F5F0EB`(奶茶色)
深色模式使用 `#0A0A0B`、`#111827`、`#1A1A2E`

### P3: Tailwind 默认色板
过度依赖 Tailwind 的 blue-500/purple-600/gray-100 等默认色 → AI 感。

**替代:** 自定义色板，或使用非标准 Tailwind 色（amber、teal、rose 的组合）

---

## 布局反模式

### P4: 三列等宽卡片网格
`grid-cols-3 gap-6` + 等大卡片 = 最标准的 AI 布局。

**替代:**
- Bento Grid (不等宽网格，如 2:1 或 3:2 比例)
- 交错/砖石布局 (masonry)
- 单列 + 大留白
- 层叠/重叠卡片
- 不对称分栏 (如 60/40 分栏)

### P5: 完全居中对齐
标题居中 → 副标题居中 → 按钮居中 → 全部居中。

**替代:** 至少有一处左对齐、至少有一处视觉重心偏移（黄金比例或三分法）。

### P6: 等间距统治
所有元素的 margin/padding 使用相同值（如全部 24px）。

**替代:** 使用节奏性间距：标题与内容间 48px，内容项之间 16px，区块间 80px。
至少 3 种间距值。

---

## 组件反模式

### P7: 全统一圆角
所有卡片/按钮使用相同 border-radius（如全部 12px 或全部 rounded-lg）。

**替代:**
- 卡片: 16px
- 按钮: 8px (小) / 12px (大)
- 输入框: 6px (小) / 10px (大)
- 模态/弹窗: 20px
- 头像: 50%
- 至少 4 种不同圆角值

### P8: 千篇一律的阴影
`box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1)` — 出现频率极高。

**替代方案:**
```css
/* 弥散阴影 (背景色系阴影) */
box-shadow: 0 20px 60px -20px rgba(79, 70, 229, 0.15);

/* 硬边/粗野风格阴影 */
box-shadow: 8px 8px 0 #000;

/* 多层阴影 */
box-shadow:
  0 1px 2px rgba(0,0,0,0.04),
  0 4px 16px rgba(0,0,0,0.06),
  0 12px 40px rgba(0,0,0,0.08);

/* 内阴影/发光 */
box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 0 0 1px rgba(0,0,0,0.05);
```

### P9: Heroicons/Feather Icons 默认图标
AI 频繁使用 outline 风格的通用图标。

**替代方案（按推荐度排序）:**
1. **阿里 iconfont 精选图标** — 800 万+ 图标，覆盖中文行业场景（餐饮/零售/金融），填充风格优先
2. **Emoji** — 零依赖、跨平台一致、有温度和个性
3. **内联 SVG** — 从 iconfont 下载单个 SVG 内联，完全可控、可动画化
4. **纯 CSS 绘制** — 简单几何图标（箭头、关闭按钮等）
5. **混合使用** — 功能图标用 iconfont、装饰用 emoji、品牌图形用内联 SVG

→ 完整图标集成指南：加载 `references/icon-resources.md`

---

## 内容反模式

### P10: Lorem Ipsum
任何占位文本都是 AI 感的标志。

**替代:**
- 虚构但真实的公司名称和产品文案
- 仿照 Stripe/Vercel/Linear 的文案风格
- 使用中文真实内容（如果是中文界面）

### P11: 千篇一律的 CTA 文案
"Get Started" / "Learn More" / "Sign Up Free" — 缺乏个性。

**替代:** 有品牌个性的 CTA，如 "Start building"、"See it in action"、"Try it free →"。

### P12: 无语境的数据
数字没有单位、没有对比、没有含义 → 装饰性数据。

**替代:** 每个数据标注单位和对比（如 "+23% vs last month"、"$12,450.00 USD"）。

---

## 字体反模式

### P13: 纯 Inter 或纯系统字体栈
全部使用 Inter/System UI/Roboto → 缺乏品牌辨识度。

**替代:** 标题使用展示字体 (Display font)，正文使用易读字体。

### P14: 无粗细/大小层级
全页 2 种字号、1 种粗细 → 视觉单调。

**替代:** 至少 4 种字号、2 种字重。

---

## 完整 AI 感消除检查清单

生成设计前逐项核对：

```
□ 1. 无蓝紫渐变组合
□ 2. 背景非纯白 (#FFF)
□ 3. 使用自定义色板（非 Tailwind 默认）
□ 4. 非三列等宽卡片网格
□ 5. 至少一处非居中左对齐
□ 6. 至少 3 种不同间距值
□ 7. 至少 4 种不同圆角值
□ 8. 至少 3 种不同阴影参数
□ 9. 非默认图标库图标
□ 10. 无 Lorem Ipsum 占位文本
□ 11. CTA 文案有品牌个性
□ 12. 数据标注单位和对比
□ 13. 标题/正文使用不同字体
□ 14. 至少 4 种字号层级
□ 15. 至少 1 处设计亮点（独特视觉元素）
□ 16. 至少 1 处微交互
□ 17. CSS 自定义属性构建 token 系统
□ 18. 至少 1 种高级 CSS 特性
```

---

## 设计亮点 (Design Delight) 示例

以下是可以提升"设计感"的具体手段：

### 经典交互（依然有效）
1. **光标跟随效果**: 卡片随鼠标位置微倾斜
2. **滚动视差**: 不同层以不同速度滚动
3. **渐变文字**: 标题使用 `background-clip: text` 渐变
4. **边框发光**: hover 时边框渐隐渐现
5. **数字滚动**: 计数动画带缓动
6. **纹理叠加**: 细微噪点/网格纹理作为背景
7. **有机形状装饰**: blob/circle/曲线作为背景装饰
8. **自定义滚动条**: 使用 `::-webkit-scrollbar` 美化
9. **Glass 效果**: backdrop-filter blur + 半透明

### 现代 CSS 能力（2024-2025 新特性）

10. **滚动驱动动画 (Scroll-Driven Animations)** — 无需 JS
```css
@keyframes fade-in {
  from { opacity: 0; transform: translateY(40px); }
  to   { opacity: 1; transform: translateY(0); }
}
.card-reveal {
  animation: fade-in linear;
  animation-timeline: view();
  animation-range: entry 0% entry 80%;
}
```

11. **`@starting-style` 过渡** — 元素首次渲染时触发动画
```css
.modal {
  opacity: 0; transform: scale(0.95);
  transition: opacity 0.3s, transform 0.3s;
}
.modal[open] {
  opacity: 1; transform: scale(1);
  @starting-style { opacity: 0; transform: scale(0.95); }
}
```

12. **CSS `:has()` 父选择器** — 基于子元素状态改变父样式
```css
.card:has(.btn:hover) {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glow);
}
```

13. **`color-mix()` 动态配色** — 运行时混合颜色
```css
.btn-primary:hover {
  background: color-mix(in srgb, var(--color-primary) 80%, white);
}
```

14. **`text-wrap: balance`** — 标题自动平衡换行
```css
h1, h2, h3 { text-wrap: balance; }
```

15. **`field-sizing: content`** — 自适应高度的 textarea
```css
textarea { field-sizing: content; min-height: 3lh; }
```

16. **`view-transition` API** — 页面间无缝过渡
```css
::view-transition-old(root) { animation: fade-out 0.3s; }
::view-transition-new(root) { animation: fade-in 0.3s; }
```

17. **`light-dark()` 函数** — 一行代码实现明暗主题
```css
:root {
  color-scheme: light dark;
  --bg: light-dark(#FAF9FF, #0B0D17);
  --text: light-dark(#2D2B3C, #E2E4EB);
}
```

18. **CSS 嵌套 (Nesting)** — 原生嵌套语法
```css
.card {
  background: var(--bg-card);
  & .title { font-weight: 700; }
  &:hover { transform: translateY(-4px); }
  @media (width < 768px) { padding: 16px; }
}
```

> **使用原则**: 现代 CSS 特性优先用于渐进增强，确保在不支持的浏览器中优雅降级。优先选择 `@supports` 包裹实验性特性。
