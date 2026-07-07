# 字体配对与排版系统

## 核心原则

- **标题与正文必须使用不同字体**——这是最直接消除 AI 感的手段
- **有衬线字体不是老气**——恰当使用 Serif 能极大提升高级感
- **字号阶梯不能等比例**——使用 modular scale (1.25 或 1.333)

---

## 字体配对方案

### 现代科技感
| 角色 | 字体 | 引入方式 |
|------|------|----------|
| 标题 | Space Grotesk | `Space+Grotesk:wght@500;600;700` (Google Fonts) |
| 标题备选 | Satoshi | `https://api.fontshare.com/v2/css?f[]=satoshi@700,500,400` (Fontshare CDN) |
| 正文 | Inter / Plus Jakarta Sans | `Inter:wght@400;500;600` |
| 数字 | JetBrains Mono | `JetBrains+Mono:wght@500` |

> **Satoshi 使用说明**: Satoshi 不在 Google Fonts 上，需通过 Fontshare CDN 引入。如果无法访问 Fontshare，使用 Space Grotesk 作为零配置替代。

### 编辑/出版风格
| 角色 | 字体 | Google Fonts 链接 |
|------|------|-------------------|
| 标题 | Playfair Display / Cormorant Garamond | `Playfair+Display:wght@700;900` |
| 正文 | Source Serif 4 / Lora | `Source+Serif+4:wght@400;600` |
| 数字 | DM Mono | `DM+Mono:wght@400` |

### 创意/大胆风格
| 角色 | 字体 | Google Fonts 链接 |
|------|------|-------------------|
| 标题 | Clash Display / Syne | `Syne:wght@600;700;800` |
| 正文 | DM Sans / Work Sans | `DM+Sans:wght@400;500` |
| 数字 | Space Mono | `Space+Mono:wght@400;700` |

### 经典高级感
| 角色 | 字体 | Google Fonts 链接 |
|------|------|-------------------|
| 标题 | DM Serif Display / Bodoni Moda | `DM+Serif+Display` |
| 正文 | Public Sans / Figtree | `Public+Sans:wght@400;500` |
| 数字 | Red Hat Mono | `Red+Hat+Mono:wght@500` |

### 金融/企业稳重
| 角色 | 字体 | Google Fonts 链接 |
|------|------|-------------------|
| 标题 | Manrope / Lexend | `Manrope:wght@600;700;800` |
| 正文 | IBM Plex Sans / Nunito Sans | `IBM+Plex+Sans:wght@400;500` |
| 数字 | Fira Mono | `Fira+Mono:wght@500` |

### 中文界面

#### 中文字体资源

| 字体 | 风格 | 字重 | 引入方式 |
|------|------|------|----------|
| 思源黑体 (Noto Sans SC) | 现代无衬线 | 250/300/400/500/700/900 | Google Fonts: `Noto+Sans+SC:wght@400;500;700` |
| 思源宋体 (Noto Serif SC) | 传统衬线 | 400/500/700/900 | Google Fonts: `Noto+Serif+SC:wght@400;700` |
| 阿里巴巴普惠体 | 现代无衬线 | 300/400/500/700 | CDN: `https://cdn.jsdelivr.net/npm/alibaba-puhuiti@3.0/AlibabaPuHuiTi-3-55-Regular.woff2` |
| ZCOOL 站酷快乐体 | 手写/创意 | 400 | Google Fonts: `ZCOOL+KuaiLe` |
| ZCOOL 站酷小薇 | 毛笔/艺术 | 400 | Google Fonts: `ZCOOL+XiaoWei` |
| Ma Shan Zheng (马山正) | 书法 | 400 | Google Fonts: `Ma+Shan+Zheng` |
| LXGW WenKai (霞鹜文楷) | 楷体/人文 | 300/400/500/700 | Google Fonts: `LXGW+WenKai:wght@400;700` |
| 得意黑 (Smiley Sans) | 现代圆体 | 400 | CDN: `https://cdn.jsdelivr.net/npm/smiley-sans@1.1.1/fonts/SmileySans-Oblique.woff2` |

> **加载策略**: 中文字体文件大（5-15MB），推荐 `font-display: swap` + 预加载关键字体。Google Fonts 上的中文字体通常做了子集化，加载更快。

#### 中英混排配对方案

| 场景 | 中文标题 | 英文/Latin 标题 | 正文 | 数字 |
|------|----------|-----------------|------|------|
| 现代企业/SaaS | 思源黑体 Bold | Space Grotesk Bold | Inter 400 | JetBrains Mono |
| 内容/出版 | 思源宋体 Bold | Playfair Display | Source Serif 4 | DM Mono |
| 创意/潮流 | 站酷快乐体 | Syne Bold | DM Sans | Space Mono |
| 金融/数据 | 阿里巴巴普惠体 Bold | Manrope Bold | IBM Plex Sans | Fira Mono |
| 人文/文艺 | 霞鹜文楷 Bold | DM Serif Display | Public Sans | Red Hat Mono |

#### 中英混排 CSS 技巧

```css
/* 字体栈顺序：中文优先 → 英文 fallback → 系统兜底 */
--font-heading-cn: 'Noto Sans SC', 'Space Grotesk', sans-serif;
--font-heading-en: 'Space Grotesk', 'Noto Sans SC', sans-serif;
--font-body: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

/* 中文字重对齐：中文 Regular(400) ≈ 英文 Medium(500) 的视觉粗细 */
.cn-title { font-family: var(--font-heading-cn); font-weight: 700; }
.en-subtitle { font-family: var(--font-heading-en); font-weight: 400; }

/* 中文行高适当加大，因为中文字符视觉密度更高 */
.cn-body { line-height: 1.8; }  /* 中文舒适阅读 */
.en-body { line-height: 1.6; }  /* 英文舒适阅读 */
```

---

## 字号阶梯 (Modular Scale)

使用 modular scale 1.25 (Major Third):

```css
/* 基于 16px 根字号 */
--text-xs:    0.75rem;   /* 12px */
--text-sm:    0.875rem;  /* 14px */
--text-base:  1rem;      /* 16px */
--text-lg:    1.125rem;  /* 18px */
--text-xl:    1.25rem;   /* 20px */
--text-2xl:   1.563rem;  /* 25px */
--text-3xl:   1.953rem;  /* 31px */
--text-4xl:   2.441rem;  /* 39px */
--text-5xl:   3.052rem;  /* 49px */
--text-6xl:   3.815rem;  /* 61px */
```

或使用 1.333 (Perfect Fourth) 获得更激进的字号对比：

```css
--text-2xl:   1.333rem;  /* ~21px */
--text-3xl:   1.777rem;  /* ~28px */
--text-4xl:   2.369rem;  /* ~38px */
--text-5xl:   3.157rem;  /* ~51px */
--text-6xl:   4.209rem;  /* ~67px */
```

---

## 排版黄金法则

### 1. 字重阶梯
每个场景至少使用 2 种字重：
- 标题: Bold (700) → 常规还是加粗取决于场景
- 正文: Regular (400)
- 强调: Medium/SemiBold (500/600)
- **禁止**: 全页只有 Regular 400

### 2. 行高规则
```css
标题: line-height: 1.1-1.2;   /* 紧凑 */
正文: line-height: 1.5-1.6;   /* 舒适阅读 */
小字: line-height: 1.4;       /* 中等 */
代码: line-height: 1.7;       /* 宽松 */
```

### 3. 字间距
```css
大写标题: letter-spacing: -0.02em ~ -0.04em;   /* 负间距，收紧 */
正文:     letter-spacing: 0;                     /* 默认 */
小字/标签: letter-spacing: 0.02em ~ 0.05em;      /* 正间距，呼吸感 */
```

### 4. 段落间距
段落间距不应等于行高（那是 Word 风格）。
```css
段落间距 = 行高 × 1.5 ~ 2
如行高 1.6 × 16px = 25.6px，段落间距取 24~32px
```

### 5. 标题与正文间距
标题下方间距 = 标题字号 × 0.5 ~ 0.75
```
H1 (39px) → 下方 20-30px
H2 (31px) → 下方 16-24px
H3 (25px) → 下方 12-20px
```

---

## 避免反模式

| 反模式 | 正确做法 |
|--------|----------|
| 全页 Inter 400 | 标题用 Display 字体 |
| 全页 Roboto | 至少加一种衬线或个性字体 |
| 只用 14px 和 16px | 至少 4 种字号层级 |
| 行高全 1.5 | 标题紧凑(1.1-1.2)，正文舒适(1.5-1.6) |
| 无 letter-spacing 控制 | 大写标题收紧，小字标签放宽 |
| 中文用纯系统默认字体 | 引入至少一款高质量中文字体 |

---

## Google Fonts 引入模板

```html
<!-- 现代科技三件套 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
```

```html
<!-- 编辑风格 -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
```
