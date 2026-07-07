# Dribbble 典型布局模式

Dribbble 上的高质量设计绝不使用标准三列网格。以下是经过验证的布局模式。

---

## 1. Bento Grid (便当网格)

Apple 推广的不等宽网格系统——当前 Dribbble 上最流行的布局之一。

**特征:**
- 不同大小的卡片组合成整体
- 通常包含 1 个大卡片 (2x)、2-3 个中等卡片 (1x)、2 个小卡片 (0.5x)
- 行/列跨越创造视觉节奏

**CSS 实现:**
```css
.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: 180px;
  gap: 20px;
}

.bento-card-large {
  grid-column: span 2;
  grid-row: span 2;
}

.bento-card-wide {
  grid-column: span 2;
  grid-row: span 1;
}

.bento-card-tall {
  grid-column: span 1;
  grid-row: span 2;
}

.bento-card-small {
  grid-column: span 1;
  grid-row: span 1;
}
```

**HTML 示例:**
```html
<div class="bento-grid">
  <div class="bento-card-large"><!-- 主功能卡 --></div>
  <div class="bento-card-tall"><!-- 统计卡 --></div>
  <div class="bento-card-small"><!-- 快捷操作 --></div>
  <div class="bento-card-small"><!-- 快捷操作 --></div>
  <div class="bento-card-wide"><!-- 图表卡 --></div>
  <div class="bento-card-small"><!-- 指标卡 --></div>
  <div class="bento-card-small"><!-- 指标卡 --></div>
</div>
```

---

## 2. 层叠交错 (Overlapping Staggered)

卡片互相重叠交错排列，创造深度感。

**特征:**
- 卡片使用负 margin 或 translate 实现重叠
- z-index 创建层次
- 通常配合玻璃态或柔和阴影使用

**CSS 实现:**
```css
.stack-row {
  display: flex;
  align-items: center;
  position: relative;
}

.stack-card {
  flex-shrink: 0;
  width: 320px;
  border-radius: 20px;
  transition: transform 0.3s ease;
}

.stack-card:nth-child(1) { z-index: 3; }
.stack-card:nth-child(2) {
  z-index: 2;
  margin-left: -40px;
  transform: translateY(-30px);
}
.stack-card:nth-child(3) {
  z-index: 1;
  margin-left: -40px;
}

.stack-card:hover {
  transform: translateY(-40px);
  z-index: 10;
}
```

---

## 3. 全屏分段 (Full-Screen Sections)

每个区域占满整个视口高度，配合滚动视差。

**特征:**
- `height: 100vh` 或 `min-height: 100vh` 的分段
- 每段使用不同的背景色/布局
- 滚动触发内容渐入

**CSS 实现:**
```css
.section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  padding: 80px 0;
  position: relative;
  overflow: hidden;
}

/* 交替背景 */
.section:nth-child(odd) { background: var(--bg-primary); }
.section:nth-child(even) { background: var(--bg-secondary); }
```

---

## 4. 不对称分栏 (Asymmetric Split)

不是简单的 50/50 分栏，而是使用 60/40、70/30 或更极端的比例。

**CSS 实现:**
```css
.split-60-40 {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 60px;
  align-items: center;
}

.split-70-30 {
  display: grid;
  grid-template-columns: 7fr 3fr;
  gap: 40px;
  align-items: center;
}

.split-reverse {
  direction: rtl;
}
.split-reverse > * {
  direction: ltr;
}
```

**关键:** 文字侧不要总是放在左边——交替左右打破单调。

---

## 5. 中心聚焦 + 环绕装饰 (Center Focus)

主内容置中，周围环绕装饰元素（渐变光斑、图标、线条）。

**特征:**
- 主内容区窄而集中 (max-width: 600-800px)
- 周围大面积留白 + 装饰元素
- 装饰元素半透明、非侵入式

**CSS 实现:**
```css
.hero-focus {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 120px 0;
  position: relative;
  overflow: hidden;
}

.hero-focus > * {
  max-width: 720px;
}

/* 装饰元素绝对定位在四周 */
.hero-decor-left {
  position: absolute;
  left: 5%;
  top: 20%;
  opacity: 0.08;
}

.hero-decor-right {
  position: absolute;
  right: 3%;
  bottom: 15%;
  opacity: 0.06;
}
```

---

## 6. 杂志式布局 (Editorial / Magazine)

适用于内容密集型页面：博客、作品集、媒体。

**特征:**
- 大号首图/首屏
- 正文区窄列 (max-width: 680px)
- 引用块/图片穿插
- 不对称的图片与文字搭配

**CSS 实现:**
```css
.editorial-hero {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 80px;
  min-height: 80vh;
  align-items: center;
}

.editorial-hero-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
  /* 注意：不是大圆角——杂志风是小圆角 */
}

.editorial-body {
  max-width: 680px;
  margin: 0 auto;
  font-size: 1.125rem;
  line-height: 1.8;
}
```

---

## 7. 水平滚动卡片 (Horizontal Scroll)

卡片横向排列，可滚动或自动轮播。

**CSS 实现:**
```css
.h-scroll {
  display: flex;
  gap: 24px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding: 20px 0;
  -webkit-overflow-scrolling: touch;
}

.h-scroll::-webkit-scrollbar { display: none; }

.h-scroll-card {
  flex-shrink: 0;
  width: 340px;
  scroll-snap-align: start;
  border-radius: 20px;
  transition: transform 0.3s ease;
}
```

---

## 布局选择决策树

```
内容类型是什么？
├── 数据/Dashboard → Bento Grid 或 水平滚动卡片
├── 产品展示 → 全屏分段 或 层叠交错
├── 内容/博客 → 杂志式布局
├── 工具/功能 → 不对称分栏 或 Bento Grid
├── 品牌/Hero → 中心聚焦 + 环绕装饰
└── 社交媒体 → 层叠交错 或 水平滚动
```

---

## 反模式（避免）

| 反模式 | 原因 |
|--------|------|
| `grid-template-columns: repeat(3, 1fr)` | 最明显的 AI 布局 |
| 左右对称 50/50 分栏 | 缺乏视觉张力 |
| 全部内容居中 | 缺少节奏和呼吸感 |
| 所有卡片等高 | 像模板而非设计 |
| 无视差/动效 | 静态页面缺乏层次感 |
