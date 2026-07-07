/**
 * iconfont Symbol 图标 — 阿里矢量图库
 * 项目: font_5204882 (12 icons)
 */

const MAP = {
  AI: 'icon-AI',
  devices: 'icon-shebei',
  community: 'icon-shequ',
  discover: 'icon-faxian',
  user: 'icon-yonghu',
  data: 'icon-shuju',
  ops: 'icon-yunying',
  knowledge: 'icon-zhishi',
  home: 'icon-shouye',
  online: 'icon-shebeizaixian',
  offline: 'icon-shebeilixian',
}

export default function Icon({ name, size = 22, color = '#888', style = {} }) {
  const id = MAP[name] || `icon-${name}`
  return (
    <svg style={{ width: size, height: size, fill: color, flexShrink: 0, verticalAlign: 'middle', ...style }}>
      <use xlinkHref={`#${id}`} />
    </svg>
  )
}
