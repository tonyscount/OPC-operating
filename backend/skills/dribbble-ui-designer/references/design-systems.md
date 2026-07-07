# 六大质感系统实现指南

选择 1-2 种质感系统用于设计。不要全选——质感是为品牌服务的，不是越多越好。

---

## 1. 玻璃态 (Glassmorphism)

**适用**: SaaS 后台、Dashboard 卡片、模态框、导航栏

**CSS 核心:**
```css
.glass-card {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}
```

**关键点:**
- 背后必须有色彩丰富的内容（纯白底 + 玻璃态 = 无效）
- 边框必须半透明（`rgba(255,255,255,0.1-0.2)`）
- blur 值 10-30px 之间
- saturate(150-200%) 让背景色透过后更鲜艳

**AI 感警告:** 玻璃卡片 + 蓝紫渐变背景 = 最大 AI 感组合。如果选玻璃态，背景用深色或丰富色彩，别用渐变。

---

## 2. 柔和投影 (Soft UI / Neumorphism 改良版)

**适用**: 设置面板、控制按钮、卡片（需谨慎使用——新拟态可访问性差）

**改良版 CSS（非纯 neumorphism，保留足够对比度）:**
```css
.soft-card {
  background: #F0EEEA;
  border-radius: 24px;
  box-shadow:
    12px 12px 24px #D9D7D3,
    -12px -12px 24px #FFFFFF;
  /* 仅用于背景色区域，文字/交互元素使用正常对比度 */
}

.soft-card-dark {
  background: #1E1E24;
  border-radius: 24px;
  box-shadow:
    12px 12px 24px #121216,
    -12px -12px 24px #2A2A32;
}
```

**改良原则:**
- 只用于非交互的背景装饰区域
- 按钮/链接等交互元素必须有清晰的视觉提示（颜色 + 阴影 + hover 状态）
- 不要在纯 neumorphism 中操作——用户很难分辨什么是可按的

---

## 3. 渐变弥散 (Gradient Diffusion)

**适用**: Hero 区域、特色模块背景、品牌区域

**CSS 核心:**
```css
.diffuse-bg {
  position: relative;
  overflow: hidden;
}

.diffuse-bg::before {
  content: '';
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(255,107,53,0.3), transparent 70%);
  top: -200px;
  right: -100px;
  pointer-events: none;
}

.diffuse-bg::after {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(79,70,229,0.15), transparent 70%);
  bottom: -100px;
  left: -50px;
  pointer-events: none;
}
```

**关键点:**
- 使用 `radial-gradient` 做弥散光斑，不是线性渐变
- 叠加多个不同颜色、不同位置的光斑
- 透明度控制在 0.1-0.3，不能太浓
- 光斑颜色从主色/辅色中提取

**禁止:** 作为页面唯一背景的大面积线性渐变（90% AI 特征）

---

## 4. 网格/线条装饰 (Grid & Line Decor)

**适用**: 科技感、数据平台、创意工具页面

**4A — 背景网格:**
```css
.grid-bg {
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 60px 60px;
}
```

**4B — 装饰线条动画:**
```css
.decor-line {
  position: absolute;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  animation: line-slide 4s ease-in-out infinite;
}

@keyframes line-slide {
  0%, 100% { transform: translateX(-100%); opacity: 0; }
  50% { transform: translateX(100%); opacity: 1; }
}
```

**4C — SVG 几何图案:**
```html
<svg class="decor-pattern" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <path d="M40,-20 L180,-20 L220,120 L0,120 Z" fill="none" stroke="currentColor" stroke-width="0.5" opacity="0.1"/>
  <circle cx="100" cy="100" r="80" fill="none" stroke="currentColor" stroke-width="0.5" opacity="0.1"/>
</svg>
```

---

## 5. 粗野主义 (Brutalism)

**适用**: 设计师作品集、创意机构、年轻人品牌、反主流调性

**核心特征:**
- 大号、粗体、无衬线标题（3rem+）
- 硬黑边框 (`border: 3px solid #000`)
- 高对比度原色（红/黄/蓝直接碰撞）
- 非对称布局、故意打破网格
- `box-shadow: 8px 8px 0 #000` 硬阴影
- 等宽字体大量使用

**CSS 示例:**
```css
.brutal-card {
  background: #FFE600;
  border: 3px solid #000;
  box-shadow: 8px 8px 0 #000;
  padding: 2rem;
  font-family: 'Space Mono', monospace;
}

.brutal-card:hover {
  transform: translate(-4px, -4px);
  box-shadow: 12px 12px 0 #000;
}

.brutal-btn {
  background: #000;
  color: #FFE600;
  border: 3px solid #000;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 2px;
  transition: all 0.15s ease;
}

.brutal-btn:hover {
  background: #FF3D00;
  color: #FFF;
  transform: scale(1.05);
}
```

---

## 6. 有机曲线 (Organic Blobs & Curves)

**适用**: 生活方式品牌、健康、教育、创意工具

**6A — CSS blob 形状:**
```css
.blob {
  width: 400px;
  height: 400px;
  border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
  background: linear-gradient(135deg, var(--accent), var(--primary));
  animation: blob-morph 8s ease-in-out infinite;
}

@keyframes blob-morph {
  0%, 100% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }
  50% { border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%; }
}
```

**6B — SVG 波浪分割线:**
```html
<svg viewBox="0 0 1440 120" preserveAspectRatio="none" class="wave-divider">
  <path d="M0,60 C360,120 720,0 1080,60 C1260,90 1380,30 1440,40 L1440,120 L0,120 Z"
        fill="var(--bg-secondary)"/>
</svg>
```

**6C — 有机装饰元素:**
```css
.organic-ring {
  width: 300px;
  height: 300px;
  border: 2px solid var(--accent);
  border-radius: 40% 60% 55% 45% / 45% 55% 60% 40%;
  opacity: 0.15;
  animation: ring-rotate 20s linear infinite;
}

@keyframes ring-rotate {
  to { transform: rotate(360deg); }
}
```

---

## 质感系统选择指南

| 品牌调性 | 推荐质感 |
|----------|----------|
| 现代科技/SaaS | 玻璃态 + 网格装饰 |
| 金融/企业 | 柔和投影 + 渐变弥散 |
| 创意/设计 | 粗野主义 或 有机曲线 |
| 健康/生活 | 有机曲线 + 柔和投影 |
| 电商/消费 | 渐变弥散 + 柔和投影 |
| 游戏/娱乐 | 玻璃态 + 粗野主义 |

**黄金规则:** 最多 2 种质感系统同时使用。1 种主导 + 1 种点缀。
