# 图标资源指南 — 告别 AI 感图标

## 核心原则

AI 生成的 UI 几乎 100% 使用 Heroicons/Feather Icons/Lucide 等通用 outline 图标——这是暴露 AI 身份的最快方式。要消除 AI 感，图标必须多样化且与品牌匹配。

---

## 图标选择层级（按推荐优先级排列）

| 优先级 | 方案 | AI 感 | 适用场景 |
|--------|------|-------|----------|
| ⭐⭐⭐ | 阿里 iconfont 精选图标 | 极低 | 中文界面、电商/餐饮/金融/企业 |
| ⭐⭐⭐ | Emoji（系统原生） | 极低 | 卡片装饰、标签、情感化表达 |
| ⭐⭐ | 自定义 SVG 内联绘制 | 极低 | Logo、品牌图形、特色装饰 |
| ⭐⭐ | CSS 纯绘制图标 | 极低 | 简单几何图标（箭头、汉堡菜单等） |
| ⭐ | Google Material Symbols | 中等 | 英文界面、工具类产品 |
| ❌ | Heroicons / Feather / Lucide | 极高 | **禁止使用** |

---

## 阿里 iconfont 实战指南

阿里图标库 (iconfont.cn) 拥有 800 万+ 图标，是中文 UI 环境下消除 AI 感的最佳选择。

### 使用方式对比

| 方式 | 难度 | 灵活度 | 推荐场景 |
|------|------|--------|----------|
| **Symbol 引用** | ⭐⭐ | ⭐⭐⭐ | ✅ 首选 — 支持多色、CSS 控制、按需加载 |
| **Font-Class** | ⭐ | ⭐⭐ | 快速原型、图标不多时 |
| **Unicode** | ⭐ | ⭐ | 兼容性最好（不推荐，语义差） |
| **SVG 下载** | ⭐⭐⭐ | ⭐⭐⭐ | 图标极少（< 5 个）时直接用 |

### 方案一：Symbol 引用（首选）

```html
<!-- 1. 引入 iconfont.js（从 iconfont.cn 项目生成） -->
<script src="//at.alicdn.com/t/c/font_XXXXXXX.js"></script>

<!-- 2. 通用 CSS -->
<style>
.icon {
  width: 1em; height: 1em;
  vertical-align: -0.15em;
  fill: currentColor;
  overflow: hidden;
}
</style>

<!-- 3. 使用 -->
<svg class="icon" aria-hidden="true">
  <use xlink:href="#icon-hotpot"></use>
</svg>
```

**优点**: 支持多色图标、可用 CSS `fill`/`color` 控制颜色、按需加载。

### 方案二：Font-Class（快速原型）

```html
<!-- 1. 引入 CSS -->
<link rel="stylesheet" href="//at.alicdn.com/t/c/font_XXXXXXX.css">

<!-- 2. 使用 -->
<i class="iconfont icon-hotpot"></i>
```

**优点**: 使用简单，像字体一样控制大小/颜色。
**缺点**: 只支持单色。

### 方案三：独立 SVG 内联（最灵活）

从 iconfont 下载单个 SVG，直接内联到 HTML：

```html
<!-- 从 iconfont 下载的火锅图标 SVG -->
<svg viewBox="0 0 1024 1024" width="24" height="24" fill="currentColor">
  <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z"/>
</svg>
```

**优点**: 零外部依赖、完全可控、可动画化、SEO 友好。

---

## 按行业推荐图标关键字（iconfont 搜索词）

### 1. 餐饮/火锅/中餐
```
火锅、锅底、食材、牛肉、毛肚、蔬菜、饮料、餐厅、厨师帽、菜单、外卖、排队、桌号、
点餐、套餐、筷子、碗碟、围裙、灶台、辣椒、花椒、火苗、米饭、面条
搜索技巧: "火锅 图标"、"餐饮 矢量"、"中餐 icon"
```

### 2. 茶饮/咖啡/酒吧
```
奶茶、咖啡、茶、杯子、吸管、冰块、果糖、奶盖、珍珠、外卖杯、奶泡、手冲、
啤酒、酒杯、调酒、冰块桶、柠檬片、薄荷叶、气泡
搜索技巧: "茶饮 图标"、"饮品 矢量"、"咖啡 icon"、"酒吧 图标"
```

### 3. 零售/便利店/超市
```
购物、扫码、会员、收银、库存、货架、快递、包裹、优惠券、条形码、购物车、
价签、称重、收银台、小票、塑料袋、购物篮、打折
搜索技巧: "零售 icon"、"便利店 矢量图标"、"超市 图标"
```

### 4. 电商/购物/直播
```
购物袋、快递箱、好评、退换货、秒杀、直播、主播、礼物、关注、粉丝、店铺、
上新、预售、满减、红包、拼团、砍价、分享
搜索技巧: "电商 icon"、"直播 图标"、"购物 矢量"
```

### 5. 酒店/民宿/旅游
```
酒店、民宿、房卡、前台、行李、门锁、WiFi、游泳池、温泉、景点、地图、
机票、护照、行李箱、帐篷、日出、海滩、缆车、滑雪
搜索技巧: "酒店 图标"、"民宿 icon"、"旅游 矢量"
```

### 6. 医疗/健康/养生
```
医院、医生、护士、药品、处方、体检、心率、血压、体温计、口罩、急救、
中医、针灸、推拿、养生、太极、艾灸、瑜伽垫、冥想
搜索技巧: "医疗 图标"、"健康 icon"、"养生 矢量"、"中医 图标"
```

### 7. 教育/培训/知识付费
```
书本、毕业帽、黑板、课程、讲师、学生、考试、证书、在线学习、视频课、
专栏、打卡、作业、图书馆、实验室、画笔、钢琴、足球
搜索技巧: "教育 icon"、"培训 图标"、"在线教育 矢量"、"知识付费 图标"
```

### 8. 房产/物业/家居装修
```
房子、楼盘、钥匙、合同、房贷、装修、家具、沙发、灯具、卫浴、地板、
户型图、测量、工具箱、安全帽、电梯、门禁、监控
搜索技巧: "房产 图标"、"物业 icon"、"家居 矢量"、"装修 图标"
```

### 9. 汽车/出行/交通
```
汽车、方向盘、轮胎、加油、充电桩、停车场、红绿灯、公交车、地铁、
自行车、电动车、导航、定位、行程、洗车、保养、保险
搜索技巧: "汽车 icon"、"出行 图标"、"交通 矢量"、"新能源 图标"
```

### 10. 物流/快递/仓储
```
快递车、包裹、仓库、货架、条形码、扫码枪、封箱、称重、配送员、路线、
签收、冷链、集装箱、叉车、传送带、分拣
搜索技巧: "物流 图标"、"快递 icon"、"仓储 矢量"、"供应链 图标"
```

### 11. 农业/生鲜/社区团购
```
蔬菜、水果、农场、种植、收割、温室、种子、有机、生鲜、冷链、团长、
自提点、菜篮子、鸡蛋、牛奶、鲜肉、海鲜、大米
搜索技巧: "农业 icon"、"生鲜 图标"、"农场 矢量"、"社区团购 图标"
```

### 12. 运动/健身/户外
```
跑步、健身、哑铃、瑜伽、游泳、篮球、足球、羽毛球、骑行、登山、
滑雪、冲浪、马拉松、奖牌、秒表、体脂秤、心率带
搜索技巧: "运动 图标"、"健身 icon"、"户外 矢量"、"体育 图标"
```

### 13. 美业/宠物/生活服务
```
美容、美发、剪刀、吹风机、化妆、美甲、水疗、宠物、猫狗、骨头、
美容院、理发店、洗衣、家政、保洁、维修、开锁、鲜花
搜索技巧: "美业 icon"、"宠物 图标"、"生活服务 矢量"、"美容 图标"
```

### 14. 通用 Dashboard/后台管理
```
数据、统计、图表、报表、设置、用户、权限、通知、消息、日历、搜索、
筛选、导出、导入、上传、下载、删除、编辑、新增、保存、刷新、打印
搜索技巧: "数据看板 图标"、"后台管理 icon"、"Dashboard 矢量"
```

### 15. 金融/财务/保险
```
人民币、钱包、账单、发票、对账、银行卡、理财、保险、税率、股票、
基金、贷款、利率、计算器、公章、合同、报表、审计
搜索技巧: "金融 icon"、"财务 矢量图标"、"保险 图标"、"银行 矢量"
```

---

## iconfont 图标选择反模式

### ❌ 避免的图标类型
- 细线条 outline 风格（太像 Heroicons）
- 过于通用抽象的图标（如 ⚙️ 齿轮、🔍 放大镜的矢量版本）
- 全部使用同一粗细/风格的图标

### ✅ 推荐的图标类型
- **填充风格 (Filled)**: 视觉重量感强，有设计感
- **双色/多色**: 层次丰富，不像模板
- **手绘风格**: 温暖、有个性，适合餐饮/教育/生活方式
- **品牌定制风格**: iconfont 上有大量店铺/行业专用图标

### 混合使用策略
```
同一页面的图标不必全来自 iconfont：
- 功能图标（导航、按钮）→ iconfont Symbol
- 装饰图标（卡片氛围）→ Emoji
- 品牌图形（Logo、特色）→ 内联 SVG
- 数据指标 → CSS 绘制小圆点/短线
```
这种混合策略本身就是反 AI 的——AI 倾向于全用一种图标方案。

---

## 实战代码模板

### 完整 HTML 模板（iconfont Symbol + Emoji 混合）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>门店看板</title>

<!-- [ICON] iconfont Symbol 方式 -->
<script src="//at.alicdn.com/t/c/font_XXXXXXX.js"></script>

<style>
/* [ICON] 基础样式 */
.icon { width: 1em; height: 1em; vertical-align: -0.15em; fill: currentColor; overflow: hidden; }

/* [ICON] 不同尺寸 */
.icon-sm  { font-size: 16px; }
.icon-md  { font-size: 24px; }
.icon-lg  { font-size: 32px; }
.icon-xl  { font-size: 48px; }

/* [ICON] 品牌色图标 */
.icon-primary { color: var(--color-primary); }
.icon-accent  { color: var(--color-accent); }

/* [ICON] 图标按钮 */
.icon-btn {
  width: 40px; height: 40px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  transition: all 0.2s var(--ease-out-expo);
  cursor: pointer; border: none;
}
.icon-btn:hover { background: var(--border-subtle); transform: scale(1.1); }
.icon-btn .icon { font-size: 20px; }
</style>
</head>
<body>

<!-- 导航图标 -->
<nav>
  <a href="#">
    <svg class="icon icon-md"><use xlink:href="#icon-dashboard"></use></svg>
    数据看板
  </a>
</nav>

<!-- 卡片装饰 — Emoji + iconfont 混合 -->
<div class="stat-card">
  <span style="font-size:2rem">🔥</span>           <!-- Emoji 装饰 -->
  <span>今日翻台率 4.2</span>
</div>

<div class="stat-card">
  <svg class="icon icon-lg icon-primary"><use xlink:href="#icon-hotpot"></use></svg>
  <span>锅底消耗 182 份</span>
</div>

</body>
</html>
```

### 无 iconfont CDN 时的纯 SVG fallback

如果网络环境无法访问 iconfont CDN，降级为系统 emoji + 纯 CSS 图标：

```css
/* [FALLBACK] CSS 纯绘制图标（无外部依赖） */
.icon-css-arrow {
  display: inline-block;
  width: 0; height: 0;
  border-left: 6px solid currentColor;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
}

.icon-css-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.icon-css-close {
  display: inline-block; position: relative;
  width: 16px; height: 16px;
}
.icon-css-close::before, .icon-css-close::after {
  content: ''; position: absolute;
  width: 100%; height: 2px; background: currentColor;
  top: 50%; left: 0;
}
.icon-css-close::before { transform: rotate(45deg); }
.icon-css-close::after  { transform: rotate(-45deg); }
```

---

## 快速上手 iconfont 三步走

1. **建项目**: 打开 [iconfont.cn](https://www.iconfont.cn)，创建项目，设置 `FontClass/Symbol` 前缀为 `icon-`
2. **挑图标**: 搜索行业关键词 → 加入购物车 → 添加到项目，选 **填充风格 (Filled)** 优先
3. **生成代码**: 项目设置 → 生成 Symbol 链接 → 复制 `<script>` 标签到 HTML

> ⚠️ 提醒用户: iconfont 链接需要用户自己创建项目后获取。生成 HTML 时使用占位符 `font_XXXXXXX`，并在注释中说明替换方法。

---

## 与本 Skill 的其他图标方案协同

| 场景 | 方案 | 理由 |
|------|------|------|
| 导航/功能按钮 | iconfont Symbol | 统一风格、可换色、矢量无损 |
| 卡片氛围装饰 | Emoji | 零依赖、跨平台一致、有温度 |
| 品牌特色图形 | 内联 SVG | 完全定制、可做动画 |
| 数据指示点 | CSS 圆点/短线 | 不需要图标库，纯 CSS 更快 |
| 加载/空状态 | iconfont 插画图标 | 比通用空状态图更有辨识度 |
