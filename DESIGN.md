---
name: "LocalLink"
description: "清晰、克制的局域网文件工作台"
colors:
  bg: "#f4f6fa"
  surface: "#fff"
  soft: "#edf1f7"
  ink: "#202d42"
  muted: "#5e6d82"
  line: "#e0e6ef"
  primary: "#2761d8"
  tint: "#eaf0ff"
  success: "#187753"
  danger: "#b33443"
  graphite: "#182438"
typography:
  display:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "42px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  title:
    fontSize: "18px"
    fontWeight: 700
  body:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontSize: "14px"
    fontWeight: 600
rounded:
  compact: "8px"
  control: "10px"
  row: "12px"
  panel: "14px"
  surface: "16px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  section: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  input-search:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
  card-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "24px"
  nav-mobile-active:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.primary}"
    rounded: "{rounded.control}"
  history-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.row}"
    padding: "22px"
---

# Design System: LocalLink

## Overview

**Creative North Star: "文件索引工作台"**

LocalLink 以石墨导航、灰白工作面和钴蓝操作构成清晰的本地工具。内容、设备身份与下一步操作保持可读，技术感来自精确分隔、稳定层级和短促反馈，而非持续环境动画。

本规范提取自已加载的 `locallink/static/workspace.css`、页面方向契约与 Android 主题。旧 `style.css` 未加载，不是当前视觉权威。Android 窗口与系统栏采用同一灰白底色、蓝色强调和系统 sans 字体；原生布局不能由 Web 尺寸直接推定。

**Key Characteristics:**

- 石墨导航与灰白内容面
- 钴蓝操作、文字辅助的状态语义
- 平面细描边与适度圆角
- 桌面侧栏、手机四项底部导航
- 短促微交互与减少动画支持

## Colors

主色负责行动，冷灰中性色负责阅读和结构；成功绿与危险红是状态色，不是装饰性副主色。

### Primary

- **操作钴蓝**：主按钮、链接、焦点、进度和活动筛选。
- **淡蓝选中面**：手机活动导航与文件投放交互背景。

### Neutral

- **灰白工作底 / 白色内容面 / 柔灰面**：依次承载页面、内容容器和次级状态。
- **石墨导航**：桌面任务导航的稳定深色区域。
- **深墨正文 / 灰蓝次文 / 浅灰边线**：区分内容、元数据和区域边界。

**The Action Color Rule.** 蓝色表示操作或当前选择；连接状态仍需明确文字，不能只靠颜色判断。

## Typography

**Body Font:** Segoe UI、Microsoft YaHei、系统无衬线回退；Android 使用系统 sans。校验和使用 Consolas 等宽字体。

概览标题使用 display 层级，移动端降至 32px；区块标题使用 headline 层级，移动端为 26px。面板标题为 18px，文件名为 16px 半粗，元数据为 12–13px。正文不使用装饰字距；日期与统计数值采用等宽数字。记录正文限制摘要长度，完整文字在可选择、可换行的阅读层展示。

## Layout

桌面固定侧栏宽 224px，主工作区最大宽 1200px、水平留白 40px。1200px 以下侧栏降至 200px、水平留白 28px。860px 以下改为 68px 粘性浅色顶栏和带安全区的四项底部导航，主要双栏变单栏，水平留白 20px；520px 以下留白降至 16px。

概览、发送、记录、设备是独立任务视图。记录页的“搜索与排序 → 类型筛选 → 日期分组 → 记录行 → 分页”是该表面的信息架构，不是所有未来页面的必选模板。窄屏记录操作移到内容下方，最窄屏占整行；类型筛选变为三列网格。Web 主要操作目标至少 48px，Android 保持至少 48dp。

## Elevation & Depth

默认内容面依赖纯色和 1px 描边，无常驻卡片阴影或背景模糊。模态使用遮罩与高位阴影，toast 使用较轻阴影；准确值记录于 sidecar。当前 Web 环境装饰层隐藏。

**The Flat Workspace Rule.** 普通静止内容面保持平面；阴影留给覆盖内容的浮层。

## Shapes

控件采用轻圆角矩形，紧凑按钮、标准控件、记录行、面板和大容器分别使用 frontmatter 中的圆角层级。状态点为小圆点。文件投放区与空状态使用虚线，表达可接收内容或当前缺少内容。

## Components

### Buttons

主按钮是白字钴蓝，次按钮是白面细描边，文字按钮保持透明；危险操作使用危险红文字。最小高度 48px，悬停改变底色，按下缩至 0.98，过渡 160ms。焦点为 3px 钴蓝外轮廓、偏移 3px；禁用降至 50% 不透明度。

### Cards / Containers

面板内边距 24px，手机收为 20px 16px。主机卡和模态采用最大圆角。容器应让长地址、文件名和文字换行，不允许内容撑破布局。

### Inputs / Fields

搜索框为白面、细边线与标准控件圆角，输入高度 48px；焦点改变边线并保留键盘轮廓。文字区为浅色输入面、可纵向调整，桌面高 260px、窄屏 220px。文件投放区保持相同高度和虚线轮廓。

### Navigation

桌面侧栏四项链接为 48px 最小高度、14px 半粗；当前项用较亮石墨面、白字及小圆点表达。手机底栏四等分，活动项淡蓝底与蓝字，单项最小高度 56px。声音与连接状态留在应用框架中。

### Transfer Records

记录页以日期分组，以文件类型图标或图片缩略图引导扫描，内容、时间、来源与去向保持分层。文字摘要桌面最多三行、窄屏四行，文件名最多两行；完整阅读、预览与详情在模态中展开。搜索、类型筛选、排序和分页共同限定结果，空状态提供说明与恢复操作。

### Feedback

成功、错误与连接问题同时提供文字。模态进入为 200ms ease-out，toast 为 180ms；系统减少动画时取消动画、过渡与平滑滚动。声音可关闭，不作为唯一反馈。

## Do's and Don'ts

### Do:

- Do 使用浅色阅读面、细分隔和明确的操作层级。
- Do 让长内容可换行、摘要可展开、状态有文字。
- Do 保持键盘焦点、48px 主要操作目标及减少动画支持。

### Don't:

- Don't 从未加载的旧样式恢复深色控制舱、背景轨道或玻璃面板。
- Don't 把记录页的日期索引与分页强制应用到所有表面。
- Don't 让装饰、声音或持续动画争夺内容阅读的注意力。
