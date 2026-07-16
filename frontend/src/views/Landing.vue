<template>
  <div class="ink-landing" ref="rootEl">
    <!-- 右侧滚动墨进度 -->
    <div class="scroll-rail" aria-hidden="true">
      <div class="scroll-ink" :style="{ height: `${scrollProgress * 100}%` }"></div>
    </div>

    <!-- 鼠标跟随墨迹画布 -->
    <canvas ref="inkCanvas" class="ink-canvas"></canvas>

    <!-- 顶栏 -->
    <header class="ink-nav">
      <div class="nav-brand">
        <span class="brand-seal">墨</span>
        <span class="brand-name">xIaoShuo</span>
      </div>
      <nav class="nav-links">
        <a href="#features">特性</a>
        <a href="#funnel">质量门禁</a>
        <a href="#flow">创作流</a>
        <router-link :to="studyTarget" class="nav-cta">进入书房</router-link>
      </nav>
    </header>

    <!-- 第一屏：书法主视觉 -->
    <section class="hero">
      <div class="hero-inner" :style="tiltStyle">
        <div class="hero-brush">
          <!-- hanzi-writer-data 真实笔画轮廓 + 权威笔顺，逐笔落墨 -->
          <div class="brush-col" ref="brushCol" role="img" aria-label="落笔生花">
            <div class="glyph" v-for="(ch, ci) in '落笔生花'" :key="ci" :ref="el => setGlyphEl(el, ci)" aria-hidden="true">
              <span class="glyph-fallback">{{ ch }}</span>
            </div>
            <!-- 精致毛笔：竹杆 + 铜箍 + 白毫笔锋 -->
            <svg class="brush-pen" viewBox="0 0 40 210" aria-hidden="true">
              <defs>
                <linearGradient id="penBamboo" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0" stop-color="#8a6a3f" />
                  <stop offset="0.4" stop-color="#c9a063" />
                  <stop offset="0.55" stop-color="#e3c48a" />
                  <stop offset="0.7" stop-color="#b98f52" />
                  <stop offset="1" stop-color="#6f4f2a" />
                </linearGradient>
                <linearGradient id="penFerrule" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0" stop-color="#7d6a3a" />
                  <stop offset="0.5" stop-color="#d9c07a" />
                  <stop offset="1" stop-color="#6a5628" />
                </linearGradient>
                <linearGradient id="penBristle" x1="0.5" y1="0" x2="0.5" y2="1">
                  <stop offset="0" stop-color="#e9dcc4" />
                  <stop offset="0.45" stop-color="#8a7c62" />
                  <stop offset="0.8" stop-color="#2a2620" />
                  <stop offset="1" stop-color="#141118" />
                </linearGradient>
              </defs>
              <rect x="15" y="2" width="10" height="120" rx="5" fill="url(#penBamboo)" />
              <line x1="15" y1="44" x2="25" y2="44" stroke="rgba(60,40,20,.45)" stroke-width="1.4" />
              <line x1="15" y1="84" x2="25" y2="84" stroke="rgba(60,40,20,.45)" stroke-width="1.4" />
              <rect x="13" y="120" width="14" height="12" rx="2" fill="url(#penFerrule)" />
              <path d="M13 132 L27 132 C30 160 24 192 20 208 C16 192 10 160 13 132 Z" fill="url(#penBristle)" />
              <path d="M20 175 C21 188 20.5 198 20 208 C19.5 198 19 188 20 175 Z" fill="#0e0b12" />
            </svg>
          </div>
        </div>
        <div class="hero-side">
          <p class="hero-sub">AI 网络小说 · 多智能体共创平台</p>
          <p class="hero-desc">
            基于 LangGraph 多智能体协同流与活态时空知识图谱，<br>
            从一缕创意到整部长篇 —— 大纲、人物、章节、校验、评审，一气呵成。
          </p>
          <div class="hero-actions">
            <router-link :to="createTarget" class="btn-ink">开始创作</router-link>
            <a href="#about" class="btn-plain">向下研墨 ↓</a>
          </div>
        </div>
        <div class="hero-seal" aria-hidden="true">共创</div>
      </div>
      <div class="hero-hint">移动鼠标，落墨成痕</div>
    </section>

    <!-- 项目介绍 -->
    <section id="about" class="section section-essay">
      <div class="essay-col reveal">
        <h2 class="section-title"><span class="stroke-bg">何为</span>此处是书房，亦是工坊</h2>
        <p class="essay-p">
          一部网络小说，死于细节崩塌：吃设定、死人复活、战力通胀、伏笔遗忘。xIaoShuo 不只是「让 AI 写字」，
          而是让一群各司其职的智能体像编辑部一样协作 —— 规划大纲、设计角色、逐章生成、反向校验、择优改写，
          每一章都经过规则与 LLM 双重审稿，再落进持续更新的知识图谱与故事圣经。
        </p>
        <p class="essay-p">
          它把长篇创作里最易被忽略的「连贯性」工程化：每章抽取结构化状态增量作为下一章的记忆，而非粗暴截取正文；
          每次重写都留有版本快照，候选不达标则永不激活。失败即标记 unverified，绝不伪造合格分。
        </p>
        <p class="essay-quote reveal">「写一本能让人追到底的书，而不是写到一半连作者都忘了前面写什么。」</p>
      </div>
      <aside class="essay-aside reveal">
        <div class="stat">
          <span class="stat-num">6</span><span class="stat-unit">大智能体节点</span>
        </div>
        <p class="stat-note">大纲 · 人设 · 章节 · 校验 · 评审 · 落库，StateGraph 非线性编排</p>
        <div class="stat">
          <span class="stat-num">L0→L3</span><span class="stat-unit">四级质量漏斗</span>
        </div>
        <p class="stat-note">规则做闸门，LLM 仅在风险处出手，Token 成本由风险决定</p>
        <div class="stat">
          <span class="stat-num">3</span><span class="stat-unit">种质量模式</span>
        </div>
        <p class="stat-note">均衡 / 成本优先 / 质量优先，按场景切换评审强度</p>
      </aside>
    </section>

    <!-- 核心特性 -->
    <section id="features" class="section">
      <h2 class="section-title reveal"><span class="stroke-bg">六艺</span>核心特性</h2>
      <div class="feature-grid">
        <article v-for="(f, i) in features" :key="f.title" class="feature-card reveal" :style="{ transitionDelay: `${(i % 3) * 0.12}s` }">
          <div class="feature-glyph">{{ f.glyph }}</div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
        </article>
      </div>
    </section>

    <!-- 质量门禁漏斗 -->
    <section id="funnel" class="section section-dark">
      <h2 class="section-title reveal"><span class="stroke-bg light">四关</span>分级漏斗式质量门禁</h2>
      <p class="section-lead reveal">规则做闸门，LLM 做裁判，成本由风险决定。失败一律标记 unverified，绝不伪造合格分。</p>
      <div class="funnel">
        <div v-for="(l, i) in funnelLevels" :key="l.tag" class="funnel-level reveal" :style="{ width: `${100 - i * 14}%`, transitionDelay: `${i * 0.15}s` }">
          <span class="funnel-tag">{{ l.tag }}</span>
          <div class="funnel-body">
            <strong>{{ l.title }}</strong>
            <p>{{ l.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 创作流 -->
    <section id="flow" class="section">
      <h2 class="section-title reveal"><span class="stroke-bg">一脉</span>逐章创作循环</h2>
      <ol class="flow-line">
        <li v-for="(s, i) in flowSteps" :key="s" class="flow-step reveal" :style="{ transitionDelay: `${i * 0.1}s` }">
          <span class="flow-dot">{{ i + 1 }}</span>{{ s }}
        </li>
      </ol>
    </section>

    <!-- 技术栈 & 诚实质量 -->
    <section class="section section-dark">
      <h2 class="section-title reveal"><span class="stroke-bg light">诚</span>诚实优先 · 技术底座</h2>
      <div class="tech-grid">
        <div class="tech-block reveal">
          <h3 class="tech-h">不伪造合格</h3>
          <p class="tech-p">任何环节未通过即标记 <code>unverified</code>，前端质量面板如实展示未评估章节，绝不以「已完成」掩盖瑕疵。</p>
        </div>
        <div class="tech-block reveal" style="transition-delay:.12s">
          <h3 class="tech-h">候选不抢先激活</h3>
          <p class="tech-p">L3 改写产出候选后先入库不生效，只有在各维度确认改善且保护维度不下降时才激活，否则保留基线。</p>
        </div>
        <div class="tech-block reveal" style="transition-delay:.24s">
          <h3 class="tech-h">实时可见</h3>
          <p class="tech-p">Vue 3 + WebSocket 推送进度 + 流式打字效果 + 三层图谱可视化，创作过程全程透明可介入。</p>
        </div>
      </div>
      <ul class="stack-list reveal">
        <li><span>运行时</span>Python 3.11 · FastAPI · LangGraph</li>
        <li><span>存储</span>PostgreSQL · SQLAlchemy · Redis · Celery</li>
        <li><span>前端</span>Vue 3 · WebSocket · 知识图谱可视化</li>
        <li><span>模型</span>DeepSeek API 驱动</li>
        <li><span>工程</span>pytest · ruff · mypy · Docker · Alembic</li>
      </ul>
    </section>

    <!-- 尾声 CTA -->
    <section class="section outro">
      <p class="outro-text reveal">「墨已研好，纸已铺开。」</p>
      <router-link :to="createTarget" class="btn-ink big reveal">执笔入局</router-link>
      <footer class="ink-footer">xIaoShuo · Python 3.11 / FastAPI / LangGraph / Vue 3 · DeepSeek 驱动</footer>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

const rootEl = ref(null)
const inkCanvas = ref(null)
const brushCol = ref(null)
const tilt = ref({ x: 0, y: 0 })
const scrollProgress = ref(0)

function hasSession() {
  try {
    return Boolean(localStorage.getItem('session_token'))
  } catch {
    return false
  }
}

const signedIn = ref(hasSession())
const studyTarget = '/shelf'
const createTarget = '/create'

// 权威字形 + 笔顺数据：运行时按需加载（不依赖 npm 包，避免安装/路径问题）
const charData = []
async function loadCharData() {
  const chars = ['落', '笔', '生', '花']
  const base = 'https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0/'
  const results = await Promise.all(
    chars.map((c) =>
      fetch(base + encodeURIComponent(c) + '.json')
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
    )
  )
  results.forEach((d, i) => { charData[i] = d })
  return results.every(Boolean)
}

const glyphEls = []
function setGlyphEl(el, i) { if (el) glyphEls[i] = el }

function onScroll() {
  const max = document.documentElement.scrollHeight - window.innerHeight
  scrollProgress.value = max > 0 ? window.scrollY / max : 0
  revealInView()
}

// 兜底显现：主动扫描视口内的 .reveal（IntersectionObserver 的双保险）
function revealInView() {
  if (!rootEl.value) return
  const vh = window.innerHeight
  rootEl.value.querySelectorAll('.reveal:not(.shown)').forEach((el) => {
    const r = el.getBoundingClientRect()
    if (r.top < vh * 0.92 && r.bottom > 0) el.classList.add('shown')
  })
}

const SVG_NS = 'http://www.w3.org/2000/svg'

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag)
  Object.entries(attrs).forEach(([name, value]) => el.setAttribute(name, String(value)))
  return el
}

// 构建单字 SVG：直接使用权威笔画轮廓，中轴线仅负责按笔序揭示
// 返回按笔顺排列的 [{ reveal, len }]
function buildGlyph(el, data, ci, ch) {
  if (!data?.strokes?.length || data.strokes.length !== data.medians?.length) return []

  const svg = svgEl('svg', {
    viewBox: '0 0 1024 1024',
    role: 'presentation',
    'data-character': ch,
  })
  svg.style.width = '100%'
  svg.style.height = '100%'
  svg.style.overflow = 'visible'
  svg.style.mixBlendMode = 'multiply'
  const defs = svgEl('defs')
  svg.appendChild(defs)

  const inkGradientId = `ink-gradient-${ci}`
  const inkGradient = svgEl('linearGradient', {
    id: inkGradientId,
    x1: '0',
    y1: '0',
    x2: '1',
    y2: '1',
  })
  const inkStops = [
    ['0%', '#0e0d0c'],
    ['42%', '#29231d'],
    ['68%', '#151310'],
    ['100%', '#080807'],
  ]
  inkStops.forEach(([offset, color]) => inkGradient.appendChild(svgEl('stop', {
    offset,
    'stop-color': color,
  })))
  defs.appendChild(inkGradient)

  // 纸张纤维让墨边出现轻微不规则，避免纯矢量的塑料感。
  const inkFilterId = `ink-texture-${ci}`
  const inkFilter = svgEl('filter', {
    id: inkFilterId,
    x: '-12%',
    y: '-12%',
    width: '124%',
    height: '124%',
    'color-interpolation-filters': 'sRGB',
  })
  inkFilter.appendChild(svgEl('feTurbulence', {
    type: 'fractalNoise',
    baseFrequency: '0.012 0.075',
    numOctaves: '2',
    seed: String(17 + ci * 7),
    result: 'paperFibers',
  }))
  inkFilter.appendChild(svgEl('feDisplacementMap', {
    in: 'SourceGraphic',
    in2: 'paperFibers',
    scale: '3.2',
    xChannelSelector: 'R',
    yChannelSelector: 'G',
  }))
  defs.appendChild(inkFilter)

  const shadowFilterId = `ink-shadow-${ci}`
  const shadowFilter = svgEl('filter', {
    id: shadowFilterId,
    x: '-20%',
    y: '-20%',
    width: '150%',
    height: '150%',
  })
  shadowFilter.appendChild(svgEl('feGaussianBlur', { stdDeviation: '5.5' }))
  defs.appendChild(shadowFilter)

  const items = []
  data.medians.forEach((pts, si) => {
    const clipId = `ink-reveal-${ci}-${si}`
    const clip = svgEl('clipPath', { id: clipId, clipPathUnits: 'userSpaceOnUse' })
    const reveal = svgEl('path', {
      class: 'stroke-reveal',
      'data-stroke-key': `${ci}-${si}`,
      fill: 'none',
      stroke: '#fff',
      'stroke-width': '300',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
    })
    // 中轴线与笔画轮廓保持同一坐标系；目标 path 的 transform 会统一完成 Y 轴转换。
    reveal.setAttribute('d', 'M' + pts.map(([x, y]) => `${x} ${y}`).join(' L'))
    clip.appendChild(reveal)
    defs.appendChild(clip)

    const shadow = svgEl('path', {
      class: 'ink-stroke-shadow',
      d: data.strokes[si],
      fill: '#2a211a',
      opacity: '0.2',
      transform: 'translate(8 911) scale(1 -1)',
      'clip-path': `url(#${clipId})`,
      filter: `url(#${shadowFilterId})`,
    })
    const stroke = svgEl('path', {
      class: 'ink-stroke',
      'data-stroke-key': `${ci}-${si}`,
      d: data.strokes[si],
      fill: `url(#${inkGradientId})`,
      stroke: '#100f0d',
      'stroke-width': '2.4',
      'paint-order': 'stroke',
      opacity: String(0.9 + ((ci * 5 + si * 3) % 8) / 100),
      transform: 'translate(0 900) scale(1 -1)',
      'clip-path': `url(#${clipId})`,
      filter: `url(#${inkFilterId})`,
    })
    svg.appendChild(shadow)
    svg.appendChild(stroke)
    items.push({ reveal, len: 0 })
  })

  el.replaceChildren(svg)
  // 插入 DOM 后测量每笔长度并初始隐藏
  items.forEach((it) => {
    const len = it.reveal.getTotalLength()
    it.len = len
    it.reveal.style.strokeDasharray = String(len)
    it.reveal.style.strokeDashoffset = String(len)
  })
  return items
}

// 正常写字节奏：中轴线速度（1024 坐标单位/ms）与停顿
const WRITE_SPEED = 1.1
const STROKE_PAUSE = 180  // 笔画间停顿
const CHAR_PAUSE = 420    // 字与字之间停顿

function runBrushWriting() {
  const col = brushCol.value
  if (!col || !glyphEls.length) return
  const pen = col.querySelector('.brush-pen')

  // 组装全部笔画（按字序 + 笔顺），记录每笔所属字，便于字间停顿
  const CHARS = '落笔生花'
  const queue = []
  glyphEls.forEach((el, ci) => {
    try {
      buildGlyph(el, charData[ci], ci, CHARS[ci]).forEach((it, si, arr) => {
        queue.push({ ...it, lastOfChar: si === arr.length - 1 })
      })
    } catch { /* 单字构建失败跳过 */ }
  })
  if (!queue.length) return

  let idx = 0
  let strokeStart = null
  if (pen) pen.style.opacity = '0' // 字体与笔顺数据坐标不同源，毛笔不展示避免错位感

  const step = (ts) => {
    if (idx >= queue.length) return
    if (strokeStart === null) strokeStart = ts
    const { reveal, len, lastOfChar } = queue[idx]
    const dur = Math.max(260, len / WRITE_SPEED)
    const prog = Math.min(1, (ts - strokeStart) / dur)
    reveal.style.strokeDashoffset = String(len * (1 - prog))
    if (prog >= 1) {
      idx += 1
      strokeStart = null
      penTimer = setTimeout(
        () => { penRaf = requestAnimationFrame(step) },
        lastOfChar ? CHAR_PAUSE : STROKE_PAUSE
      )
      return
    }
    penRaf = requestAnimationFrame(step)
  }
  penRaf = requestAnimationFrame(step)
}

const tiltStyle = computed(() => ({
  transform: `perspective(900px) rotateY(${tilt.value.x * 4}deg) rotateX(${-tilt.value.y * 4}deg)`,
}))

const features = [
  { glyph: '编', title: '多智能体图流编排', desc: 'LangGraph StateGraph 非线性流程控制，任意步骤人工介入（HITL 中断/恢复 + 持久化 checkpointer）。' },
  { glyph: '鉴', title: '分级质量门禁', desc: 'L0 零 Token 规则闸门 → L1 风险分级 → L2 LLM 全文评审 → L3 候选改写择优，成本由风险决定。' },
  { glyph: '谱', title: '活态知识图谱', desc: '每章生成前自动抽取实体三元组，防范「吃设定」「死人复活」「战力崩溃」等长篇顽疾。' },
  { glyph: '典', title: '故事圣经约束', desc: '精准注入本章相关人物、伏笔、时间线；生成后反向更新圣经，检测性格漂移与设定矛盾。' },
  { glyph: '忆', title: '结构化长期记忆', desc: '逐章抽取 state_delta（关键事件 / 人物状态 / 伏笔 / 未解决冲突），替代正文截取做衔接上下文。' },
  { glyph: '卷', title: '章节版本管理', desc: '每次生成或重写自动快照，支持版本对比、激活、回滚；候选先存不激活，确认改善才上位。' },
]

const funnelLevels = [
  { tag: 'L0', title: '零 Token 规则门禁 · 每章必过', desc: '字数 / 段落重复 / 句式复用 / 大纲覆盖率，纯规则秒判。' },
  { tag: 'L1', title: '风险分级', desc: '基于 L0 结果 + 结构化状态增量 + 章节类型，决定是否请 LLM 出手。' },
  { tag: 'L2', title: 'LLM 全文评审 · 仅高风险章', desc: '八维打分 + 人物/世界观一致性硬门禁。' },
  { tag: 'L3', title: '候选改写择优 · 仅不达标章', desc: '基线 vs 候选对比，改善且保护维度不下降才激活。' },
]

const flowSteps = [
  '初始化状态', '大纲与卷规划', '人机共创干预', '章节精细生成',
  '质量门禁漏斗', 'LLM 评审 / 候选择优', '落库 & 更新知识图谱', '循环至全书完成',
]

// —— 鼠标跟随水墨笔触 ——
let ctx, raf, observer
let penRaf = null
let penTimer = null
let last = null
const strokes = [] // { x, y, r, alpha }

function resize() {
  const c = inkCanvas.value
  if (!c) return
  c.width = window.innerWidth * devicePixelRatio
  c.height = window.innerHeight * devicePixelRatio
  ctx = c.getContext('2d')
  ctx.scale(devicePixelRatio, devicePixelRatio)
}

function onMove(e) {
  const x = e.clientX, y = e.clientY
  tilt.value = { x: x / window.innerWidth - 0.5, y: y / window.innerHeight - 0.5 }
  if (last) {
    const dx = x - last.x, dy = y - last.y
    const dist = Math.hypot(dx, dy)
    const speed = Math.min(dist, 60)
    // 速度快 → 笔锋细而飞白；慢 → 墨浓而饱满
    const steps = Math.max(1, Math.floor(dist / 3))
    for (let i = 0; i < steps; i++) {
      const t = i / steps
      const jitter = (Math.sin((x + y + i) * 0.7) + Math.cos(i * 1.3)) * 1.2
      strokes.push({
        x: last.x + dx * t + jitter,
        y: last.y + dy * t + jitter,
        r: Math.max(1.2, 9 - speed * 0.13) * (0.7 + Math.abs(Math.sin(t * Math.PI)) * 0.5),
        alpha: Math.max(0.06, 0.5 - speed * 0.006),
      })
    }
    if (strokes.length > 900) strokes.splice(0, strokes.length - 900)
  }
  last = { x, y }
}

function loop() {
  if (ctx) {
    // 旧墨渐渐洇散淡去
    ctx.save()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.globalCompositeOperation = 'destination-out'
    ctx.fillStyle = 'rgba(0,0,0,0.045)'
    ctx.fillRect(0, 0, inkCanvas.value.width, inkCanvas.value.height)
    ctx.restore()

    ctx.globalCompositeOperation = 'source-over'
    while (strokes.length) {
      const s = strokes.shift()
      ctx.beginPath()
      ctx.fillStyle = `rgba(24, 24, 28, ${s.alpha})`
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
      ctx.fill()
      // 飞白副毫
      ctx.beginPath()
      ctx.fillStyle = `rgba(24, 24, 28, ${s.alpha * 0.35})`
      ctx.arc(s.x + s.r * 1.4, s.y - s.r * 0.8, s.r * 0.4, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  raf = requestAnimationFrame(loop)
}

onMounted(() => {
  // 滚动显现（最先注册，确保内容一定能显现）
  observer = new IntersectionObserver(
    (entries) => entries.forEach((en) => en.isIntersecting && en.target.classList.add('shown')),
    { threshold: 0.01 }
  )
  rootEl.value.querySelectorAll('.reveal').forEach((el) => observer.observe(el))
  // 初始 + 兜底：主动扫描视口内元素，避免个别未触发
  revealInView()
  setTimeout(revealInView, 200)
  setTimeout(revealInView, 800)

  // 装饰动画（出错不影响内容展示）
  try {
    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })
    raf = requestAnimationFrame(loop)
    // 毛笔按笔顺书写：先加载笔顺数据，成功后开写
    loadCharData().then((ok) => { if (ok) setTimeout(runBrushWriting, 300) })
  } catch { /* 装饰层失败不阻塞内容 */ }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  if (penRaf) cancelAnimationFrame(penRaf)
  if (penTimer) clearTimeout(penTimer)
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('scroll', onScroll)
  observer?.disconnect()
})
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600;900&display=swap');
</style>

<style scoped>
.ink-landing {
  --paper: #f5f0e6;
  --paper-2: #ece4d4;
  --ink: #1b1b1f;
  --ink-soft: #4a4a50;
  --cinnabar: #b03a2e;
  font-family: 'Noto Serif SC', serif;
  color: var(--ink);
  background:
    radial-gradient(ellipse at 20% 10%, rgba(176, 58, 46, 0.05), transparent 50%),
    radial-gradient(ellipse at 85% 80%, rgba(27, 27, 31, 0.06), transparent 55%),
    var(--paper);
  min-height: 100vh;
  overflow-x: hidden;
}

/* 右侧滚动墨进度条 */
.scroll-rail {
  position: fixed;
  top: 12vh;
  right: 1.4rem;
  bottom: 12vh;
  width: 3px;
  background: rgba(27, 27, 31, 0.1);
  border-radius: 3px;
  z-index: 9;
}
.scroll-ink {
  width: 100%;
  background: linear-gradient(var(--cinnabar), var(--ink));
  border-radius: 3px;
  transition: height 0.1s linear;
}

.ink-canvas {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 1;                 /* 位于内容下方，不遮挡文字 */
  mix-blend-mode: multiply;
}

/* 顶栏 */
.ink-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.9rem 3rem;
  background: rgba(245, 240, 230, 0.85);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(27, 27, 31, 0.08);
}
.nav-brand { display: flex; align-items: center; gap: 0.7rem; }
.brand-seal {
  font-family: 'Ma Shan Zheng', cursive;
  background: var(--cinnabar);
  color: #fff;
  width: 2.2rem;
  height: 2.2rem;
  display: grid;
  place-items: center;
  border-radius: 4px;
  font-size: 1.3rem;
  box-shadow: 2px 2px 0 rgba(27, 27, 31, 0.15);
}
.brand-name { font-weight: 900; letter-spacing: 0.05em; }
.nav-links { display: flex; gap: 2rem; align-items: center; }
.nav-links a { color: var(--ink-soft); text-decoration: none; font-size: 0.95rem; transition: color 0.2s; }
.nav-links a:hover { color: var(--cinnabar); }
.nav-cta {
  border: 1.5px solid var(--ink);
  padding: 0.35rem 1.1rem;
  border-radius: 2px;
  color: var(--ink) !important;
}
.nav-cta:hover { background: var(--ink); color: var(--paper) !important; }

/* Hero */
.hero {
  min-height: 100vh;
  display: grid;
  place-items: center;
  position: relative;
  z-index: 2;
  padding: 6rem 2rem 2rem;
}
.hero-inner {
  display: flex;
  align-items: center;
  gap: 4rem;
  transition: transform 0.25s ease-out;
  will-change: transform;
  position: relative;
}
/* Hero 毛笔逐字书写 */
.hero-brush {
  position: relative;
  width: clamp(180px, 24vw, 320px);
  flex-shrink: 0;
  isolation: isolate;
}
.hero-brush::before {
  content: '';
  position: absolute;
  inset: -1.5rem -1rem;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 43% 18%, rgba(48, 37, 27, 0.07), transparent 26%),
    radial-gradient(ellipse at 58% 51%, rgba(48, 37, 27, 0.045), transparent 34%),
    repeating-linear-gradient(84deg, rgba(86, 68, 48, 0.028) 0 1px, transparent 1px 7px);
  filter: blur(0.35px);
  mask-image: radial-gradient(ellipse, #000 30%, transparent 76%);
}
.brush-col {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}
.glyph {
  width: clamp(5.5rem, min(13vw, 18vh), 10.5rem);
  height: clamp(5.5rem, min(13vw, 18vh), 10.5rem);
  margin: -0.6rem 0;
  position: relative;
  isolation: isolate;
}
.glyph:nth-child(2) { transform: translateX(0.14rem) rotate(0.35deg); }
.glyph:nth-child(3) { transform: translateX(-0.1rem) rotate(-0.45deg); }
.glyph:nth-child(4) { transform: translateX(0.08rem) rotate(0.25deg); }
.glyph :deep(svg) {
  width: 100%;
  height: 100%;
  overflow: visible;
  mix-blend-mode: multiply;
}
.glyph :deep(.ink-stroke) {
  mix-blend-mode: multiply;
}
.glyph :deep(.ink-stroke-shadow) {
  mix-blend-mode: multiply;
}
.glyph-fallback {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #171411;
  font-family: 'Ma Shan Zheng', cursive;
  font-size: clamp(5.2rem, 12.4vw, 10rem);
  line-height: 1;
  opacity: 0;
  filter: drop-shadow(0.18rem 0.28rem 0.22rem rgba(37, 28, 20, 0.2));
  animation: showGlyphFallback 0.35s ease 1.2s forwards;
}
@keyframes showGlyphFallback { to { opacity: 0.94; } }
/* 精致毛笔：绝对定位，笔尖锚定到当前笔画位置（JS 驱动 left/top） */
.brush-pen {
  position: absolute;
  top: 0;
  left: 0;
  width: 26px;
  height: 136px;
  /* 让笔尖(底部中点)对准锚点：向上、向左偏移半个笔宽 */
  transform: translate(-13px, -128px) rotate(14deg);
  transform-origin: 50% 100%;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.4s;
  z-index: 4;
  filter: drop-shadow(-2px 4px 4px rgba(27, 27, 31, 0.28));
}
.hero-side { max-width: 34rem; }
.hero-sub {
  font-size: 1.4rem;
  font-weight: 900;
  letter-spacing: 0.35em;
  border-left: 4px solid var(--cinnabar);
  padding-left: 1rem;
  margin-bottom: 1.2rem;
}
.hero-desc { color: var(--ink-soft); line-height: 2.1; margin-bottom: 2.2rem; }
.hero-actions { display: flex; gap: 1.2rem; align-items: center; }
.btn-ink {
  background: var(--ink);
  color: var(--paper);
  padding: 0.8rem 2.4rem;
  text-decoration: none;
  border-radius: 2px;
  letter-spacing: 0.3em;
  position: relative;
  transition: background 0.25s, transform 0.25s;
}
.btn-ink:hover { background: var(--cinnabar); transform: translateY(-2px); }
.btn-ink.big { font-size: 1.25rem; padding: 1rem 3.5rem; }
.btn-plain { color: var(--ink-soft); text-decoration: none; }
.btn-plain:hover { color: var(--cinnabar); }
.hero-seal {
  position: absolute;
  right: -1rem;
  bottom: -2.5rem;
  font-family: 'Ma Shan Zheng', cursive;
  writing-mode: vertical-rl;
  color: #fff;
  background: var(--cinnabar);
  padding: 0.5rem 0.35rem;
  font-size: 1.5rem;
  border-radius: 3px;
  opacity: 0.9;
  transform: rotate(4deg);
  box-shadow: 3px 3px 0 rgba(27, 27, 31, 0.12);
}
.hero-hint {
  position: absolute;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  color: var(--ink-soft);
  font-size: 0.85rem;
  letter-spacing: 0.4em;
  opacity: 0.7;
  animation: floatHint 2.6s ease-in-out infinite;
}
@keyframes floatHint { 50% { transform: translate(-50%, -8px); } }

/* 章节区块 */
.section { padding: 7rem 8vw; position: relative; z-index: 2; }
.section-title {
  font-size: clamp(1.8rem, 3.5vw, 2.6rem);
  font-weight: 900;
  letter-spacing: 0.2em;
  margin-bottom: 3.5rem;
  position: relative;
  padding-bottom: 1rem;
}
/* 标题下方毛笔横锋扫过 */
.section-title::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  height: 6px;
  width: 0;
  background:
    radial-gradient(ellipse at 0% 50%, rgba(176, 58, 46, 0.9), rgba(27, 27, 31, 0.7) 40%, transparent 95%);
  border-radius: 50%;
  opacity: 0.85;
  transition: width 1.1s cubic-bezier(0.2, 0.85, 0.3, 1) 0.15s, opacity 0.6s;
}
.reveal.shown .section-title::after,
.section-title.shown::after { width: clamp(6rem, 22vw, 16rem); }
.stroke-bg {
  font-family: 'Ma Shan Zheng', cursive;
  color: rgba(176, 58, 46, 0.18);
  font-size: 1.6em;
  margin-right: 0.4rem;
  vertical-align: -0.15em;
}
.stroke-bg.light { color: rgba(176, 58, 46, 0.18); }
.section-lead { color: inherit; opacity: 0.75; max-width: 42rem; margin: -2rem 0 3rem; line-height: 2; }

/* 滚动显现（笔刷扫入） */
.reveal {
  opacity: 0;
  transform: translateY(28px);
  clip-path: inset(0 100% 0 0);
  transition: opacity 0.8s ease, transform 0.8s ease, clip-path 0.9s cubic-bezier(0.25, 0.9, 0.3, 1);
  /* 兜底：即使 JS 未加 .shown，5s 后也强制显现，绝不留白 */
  animation: revealFallback 0.01s linear 5s forwards;
}
.reveal.shown {
  opacity: 1;
  transform: none;
  clip-path: inset(0 0 0 0);
  animation: none;
}
@keyframes revealFallback {
  to { opacity: 1; transform: none; clip-path: inset(0 0 0 0); }
}

/* 特性卡片 */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 2rem;
}
.feature-card {
  background: rgba(255, 253, 248, 0.75);
  border: 1px solid rgba(27, 27, 31, 0.1);
  border-radius: 4px;
  padding: 2rem 1.8rem;
  transition: transform 0.3s, box-shadow 0.3s, opacity 0.8s, clip-path 0.9s;
  position: relative;
}
.feature-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 14px 30px rgba(27, 27, 31, 0.12);
}
.feature-glyph {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 2.6rem;
  color: var(--cinnabar);
  line-height: 1;
  margin-bottom: 1rem;
}
.feature-card h3 { font-size: 1.15rem; font-weight: 900; margin: 0 0 0.8rem; letter-spacing: 0.08em; }
.feature-card p { color: var(--ink-soft); line-height: 1.9; font-size: 0.92rem; margin: 0; }

/* 漏斗（米白纸面，无黑色） */
.section-dark {
  background:
    radial-gradient(ellipse at 70% 20%, rgba(176, 58, 46, 0.06), transparent 55%),
    var(--paper-2);
  color: var(--ink);
}
.funnel { display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.funnel-level {
  display: flex;
  align-items: center;
  gap: 1.4rem;
  background: rgba(255, 253, 248, 0.7);
  border: 1px solid rgba(27, 27, 31, 0.12);
  border-radius: 3px;
  padding: 1.1rem 1.8rem;
}
.funnel-tag {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.8rem;
  color: var(--cinnabar);
  background: var(--paper);
  border-radius: 3px;
  padding: 0.1rem 0.6rem;
  flex-shrink: 0;
}
.funnel-body strong { display: block; letter-spacing: 0.1em; margin-bottom: 0.3rem; }
.funnel-body p { margin: 0; color: var(--ink-soft); opacity: 0.85; font-size: 0.9rem; line-height: 1.8; }

/* 项目介绍（散文+侧栏数据） */
.section-essay {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 4rem;
  align-items: start;
}
.essay-p {
  color: var(--ink-soft);
  line-height: 2.3;
  font-size: 1.02rem;
  margin: 0 0 1.5rem;
  text-align: justify;
}
.essay-quote {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: clamp(1.4rem, 2.6vw, 2rem);
  color: var(--ink);
  margin: 2.5rem 0 0;
  padding-left: 1.2rem;
  border-left: 3px solid var(--cinnabar);
  line-height: 1.7;
}
.essay-aside {
  position: sticky;
  top: 6rem;
  border-left: 1px solid rgba(27,27,31,0.15);
  padding-left: 2rem;
}
.stat {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
.stat:first-of-type { margin-top: 0; }
.stat-num {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 2.6rem;
  color: var(--cinnabar);
  line-height: 1;
}
.stat-unit { font-size: 0.95rem; font-weight: 900; letter-spacing: 0.1em; }
.stat-note { color: var(--ink-soft); font-size: 0.85rem; line-height: 1.8; margin: 0.3rem 0 1.2rem; }

/* 技术栈 & 诚实质量 */
.tech-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 2rem;
  margin-bottom: 4rem;
}
.tech-block {
  border-left: 2px solid var(--cinnabar);
  padding-left: 1.4rem;
}
.tech-h { font-size: 1.1rem; font-weight: 900; margin: 0 0 0.7rem; letter-spacing: 0.1em; }
.tech-p { color: var(--ink-soft); line-height: 2; font-size: 0.92rem; margin: 0; }
.tech-p code {
  background: rgba(27,27,31,0.08);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.85em;
}
.stack-list {
  list-style: none;
  padding: 2rem 0 0;
  margin: 0;
  border-top: 1px solid rgba(27,27,31,0.15);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.8rem 2rem;
}
.stack-list li { color: var(--ink-soft); font-size: 0.9rem; line-height: 1.9; }
.stack-list li span {
  display: inline-block;
  min-width: 3.5rem;
  color: var(--cinnabar);
  font-weight: 900;
  letter-spacing: 0.1em;
  margin-right: 0.5rem;
}

/* 创作流 */
.flow-line { list-style: none; padding: 0; margin: 0; position: relative; max-width: 40rem; }
.flow-line::before {
  content: '';
  position: absolute;
  left: 1.1rem;
  top: 0.5rem;
  bottom: 0.5rem;
  width: 2px;
  background: linear-gradient(var(--cinnabar), var(--ink));
  opacity: 0.35;
}
.flow-step {
  display: flex;
  align-items: center;
  gap: 1.2rem;
  padding: 0.9rem 0;
  font-size: 1.05rem;
  letter-spacing: 0.1em;
}
.flow-dot {
  width: 2.2rem;
  height: 2.2rem;
  border-radius: 50%;
  background: var(--paper);
  border: 2px solid var(--ink);
  display: grid;
  place-items: center;
  font-weight: 900;
  flex-shrink: 0;
  z-index: 1;
}

/* 尾声 */
.outro { text-align: center; padding-bottom: 3rem; }
.outro-text {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: clamp(1.8rem, 4vw, 3rem);
  margin-bottom: 2.5rem;
}
.ink-footer { margin-top: 5rem; color: var(--ink-soft); font-size: 0.8rem; letter-spacing: 0.15em; opacity: 0.7; }

@media (max-width: 860px) {
  .hero-inner { flex-direction: column; gap: 2rem; text-align: center; }
  .hero-brush { width: 140px; height: 280px; }
  .hero-sub { border-left: none; padding-left: 0; }
  .hero-actions { justify-content: center; }
  .ink-nav { padding: 1rem 1.2rem; }
  .section-essay { grid-template-columns: 1fr; gap: 2.5rem; }
  .essay-aside { position: static; border-left: none; padding-left: 0; border-top: 1px solid rgba(27,27,31,0.15); padding-top: 1.5rem; }
  .nav-links { gap: 1rem; }
  .section { padding: 5rem 6vw; }
}
</style>
