import { Edges } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { clamp, lerp, smoothstep } from '../lib.js'

const OUTLINE = '#666666'
const FILL_DARK = '#0a0a0a'
const FILL_DARKER = '#050505'
const ACCENT = '#ff3700'
const LAMP = '#c9a227'
const BOARD_FILL = '#0d0d0d'

function OutlineBox({ position, size, color = FILL_DARK, outline = OUTLINE }) {
  return (
    <mesh position={position}>
      <boxGeometry args={size} />
      <meshBasicMaterial color={color} />
      <Edges threshold={15} color={outline} />
    </mesh>
  )
}

function seeded(seed) {
  let s = seed % 2147483647
  if (s <= 0) s += 2147483646
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function Building({ position, width, height, depth, seed = 1 }) {
  const windows = useMemo(() => {
    const rnd = seeded(seed * 7919 + 31)
    const cols = Math.max(2, Math.floor(width / 1.1))
    const rows = Math.max(2, Math.floor(height / 1.3))
    const cells = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (rnd() < 0.14) continue
        const x = -width / 2 + 0.55 + c * ((width - 1.1) / Math.max(1, cols - 1))
        const y = -height / 2 + 0.7 + r * ((height - 1.4) / Math.max(1, rows - 1))
        cells.push({ x, y, accent: rnd() < 0.07 })
      }
    }
    return cells
  }, [width, height, seed])

  return (
    <group position={position}>
      <OutlineBox position={[0, height / 2, 0]} size={[width, height, depth]} color={FILL_DARKER} />
      {windows.map((w, i) => (
        <mesh key={i} position={[w.x, w.y, depth / 2 + 0.01]}>
          <planeGeometry args={[0.4, 0.5]} />
          <meshBasicMaterial color={w.accent ? ACCENT : '#111111'} />
          <Edges threshold={15} color={w.accent ? ACCENT : '#444444'} />
        </mesh>
      ))}
    </group>
  )
}

function Street() {
  const left = useMemo(() => {
    const rnd = seeded(11)
    const items = []
    let z = 30
    while (z > 4) {
      const w = 2.6 + rnd() * 1.4
      const h = 4 + rnd() * 3
      const d = 2.4 + rnd() * 1.2
      items.push({ x: -(8 + rnd() * 1), z, w, h, d, seed: Math.floor(z * 13) + 1 })
      z -= 3.8
    }
    return items
  }, [])

  const right = useMemo(() => {
    const rnd = seeded(23)
    const items = []
    let z = 28
    while (z > 3) {
      const w = 2.6 + rnd() * 1.4
      const h = 4 + rnd() * 3
      const d = 2.4 + rnd() * 1.2
      items.push({ x: 8 + rnd() * 1, z, w, h, d, seed: Math.floor(z * 17) + 50 })
      z -= 3.6
    }
    return items
  }, [])

  return (
    <group>
      {left.map((b, i) => (
        <Building key={`l${i}`} position={[b.x, 0, b.z]} width={b.w} height={b.h} depth={b.d} seed={b.seed} />
      ))}
      {right.map((b, i) => (
        <Building key={`r${i}`} position={[b.x, 0, b.z]} width={b.w} height={b.h} depth={b.d} seed={b.seed} />
      ))}
    </group>
  )
}

function LibraryShell() {
  const hallX = -8
  const halfW = 4
  const zFront = 4
  const zBack = -13
  const height = 7
  const gapZ0 = 1.2
  const gapZ1 = 3.4

  return (
    <group>
      <OutlineBox position={[hallX - halfW, height / 2, (zFront + zBack) / 2]} size={[0.3, height, zFront - zBack]} color={FILL_DARKER} />
      <OutlineBox position={[hallX + halfW, height / 2, (zFront + gapZ1) / 2]} size={[0.3, height, zFront - gapZ1]} color={FILL_DARKER} />
      <OutlineBox position={[hallX + halfW, height / 2, (gapZ0 + zBack) / 2]} size={[0.3, height, gapZ0 - zBack]} color={FILL_DARKER} />
      <OutlineBox position={[hallX + halfW, height - 0.15, (zFront + zBack) / 2]} size={[0.4, 0.3, zFront - zBack]} color="#111111" />
      <OutlineBox position={[hallX - halfW, height - 0.15, (zFront + zBack) / 2]} size={[0.4, 0.3, zFront - zBack]} color="#111111" />
      <OutlineBox position={[hallX, height - 0.15, zFront]} size={[halfW * 2, 0.3, 0.3]} color="#111111" />
      <OutlineBox position={[hallX, height / 2, zFront]} size={[halfW * 2 - 0.3, height, 0.25]} color={FILL_DARKER} />
      <OutlineBox position={[hallX, (gapZ1 - gapZ0) / 2 + 3.4, zFront]} size={[gapZ1 - gapZ0 + 0.3, 0.3, 0.3]} color="#151515" />
      <OutlineBox position={[hallX - halfW / 2 - 0.8, height / 2, zFront + 0.02]} size={[1.6, 2.2, 0.12]} color="#0d0d0d" outline={ACCENT} />
      <mesh position={[hallX, height - 0.3, (zFront + zBack) / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[halfW * 2, zFront - zBack]} />
        <meshBasicMaterial color="#040404" side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

function Table({ position }) {
  return (
    <group position={position}>
      <OutlineBox position={[0, 0.78, 0]} size={[1.8, 0.08, 0.9]} color="#121212" />
      {[[-0.8, -0.35], [0.8, -0.35], [-0.8, 0.35], [0.8, 0.35]].map(([x, z], i) => (
        <OutlineBox key={i} position={[x, 0.39, z]} size={[0.08, 0.78, 0.08]} color="#0e0e0e" />
      ))}
      {[-0.7, 0.7].map((x) => (
        <group key={x}>
          <OutlineBox position={[x, 0.45, 0.85]} size={[0.55, 0.06, 0.5]} color="#101010" />
          <OutlineBox position={[x, 0.72, 1.08]} size={[0.55, 0.5, 0.06]} color="#101010" />
          {[[-0.22, 0.7], [0.22, 0.7], [-0.22, 1.0], [0.22, 1.0]].map(([lx, lz], i) => (
            <OutlineBox key={i} position={[x + lx, 0.22, lz]} size={[0.06, 0.45, 0.06]} color="#0c0c0c" />
          ))}
        </group>
      ))}
    </group>
  )
}

function ReadingLamp({ position }) {
  return (
    <group position={position}>
      <OutlineBox position={[0, 0.02, 0]} size={[0.22, 0.04, 0.22]} color="#151515" />
      <mesh position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.02, 0.02, 0.5, 6]} />
        <meshBasicMaterial color="#222222" />
        <Edges threshold={15} color="#555555" />
      </mesh>
      <mesh position={[0, 0.58, 0]}>
        <coneGeometry args={[0.16, 0.14, 8, 1, true]} />
        <meshBasicMaterial color={LAMP} side={THREE.DoubleSide} transparent opacity={0.85} />
        <Edges threshold={15} color={LAMP} />
      </mesh>
    </group>
  )
}

function LowShelf({ position, rotation = [0, 0, 0], seed = 1 }) {
  const books = useMemo(() => {
    const rnd = seeded(seed * 331 + 7)
    const items = []
    let x = -1.1
    while (x < 1.1) {
      const w = 0.1 + rnd() * 0.12
      items.push({ x: x + w / 2, h: 0.4 + rnd() * 0.2, w })
      x += w + 0.03
    }
    return items
  }, [seed])

  return (
    <group position={position} rotation={rotation}>
      <OutlineBox position={[0, 0.55, 0]} size={[2.4, 1.1, 0.5]} color={FILL_DARKER} />
      <OutlineBox position={[0, 0.55, 0]} size={[2.3, 0.05, 0.45]} color="#111111" />
      {books.map((b, i) => (
        <mesh key={i} position={[b.x, 0.58 + b.h / 2, 0.02]}>
          <boxGeometry args={[b.w, b.h, 0.32]} />
          <meshBasicMaterial color={i % 6 === 0 ? '#1a1a1a' : FILL_DARK} />
          <Edges threshold={15} color={i % 6 === 0 ? ACCENT : '#4a4a4a'} />
        </mesh>
      ))}
    </group>
  )
}

function Bookshelf({ position, rotation = [0, 0, 0], height = 5.5, depth = 0.6, width = 2.8, seed = 1 }) {
  const books = useMemo(() => {
    const rnd = seeded(seed * 9973 + 17)
    const rows = 6
    const items = []
    for (let r = 0; r < rows; r++) {
      const y = -height / 2 + 0.45 + r * ((height - 0.9) / (rows - 1))
      let x = -width / 2 + 0.12
      while (x < width / 2 - 0.12) {
        const w = 0.1 + rnd() * 0.13
        const h = 0.48 + rnd() * 0.22
        items.push({ x: x + w / 2, y: y + h / 2 - 0.24, w, h, d: depth * 0.7 })
        x += w + 0.025
      }
    }
    return items
  }, [height, depth, width, seed])

  return (
    <group position={position} rotation={rotation}>
      <OutlineBox position={[0, 0, 0]} size={[width, height, depth]} color={FILL_DARKER} />
      {Array.from({ length: 6 }, (_, i) => (
        <OutlineBox
          key={`shelf-${i}`}
          position={[0, -height / 2 + 0.45 + i * ((height - 0.9) / 5), 0]}
          size={[width - 0.06, 0.05, depth * 0.95]}
          color="#111111"
        />
      ))}
      {books.map((b, i) => (
        <mesh key={i} position={[b.x, b.y, 0.05]}>
          <boxGeometry args={[b.w, b.h, b.d]} />
          <meshBasicMaterial color={i % 7 === 0 ? '#1a1a1a' : FILL_DARK} />
          <Edges threshold={15} color={i % 7 === 0 ? ACCENT : '#555555'} />
        </mesh>
      ))}
    </group>
  )
}

function LibraryHall() {
  const hallX = -8
  const shelves = useMemo(() => {
    const rows = []
    for (let z = 2; z > -12; z -= 2.4) {
      rows.push({ position: [hallX - 3.4, 2.75, z], rotation: [0, 0.15, 0], seed: Math.abs(Math.floor(z * 10)) + 1 })
      rows.push({ position: [hallX + 3.4, 2.75, z], rotation: [0, -0.15, 0], seed: Math.abs(Math.floor(z * 10)) + 40 })
    }
    return rows
  }, [hallX])

  const tables = useMemo(() => {
    const items = []
    for (let z = 1; z > -11; z -= 3.2) {
      items.push({ position: [hallX, 0, z], lamp: [hallX + 0.35, 0.82, z - 0.1] })
    }
    return items
  }, [hallX])

  return (
    <group>
      {shelves.map((s, i) => (
        <Bookshelf key={i} position={s.position} rotation={s.rotation} seed={s.seed} />
      ))}
      {tables.map((t, i) => (
        <group key={i}>
          <Table position={t.position} />
          <ReadingLamp position={t.lamp} />
        </group>
      ))}
      <LowShelf position={[hallX - 1.8, 0, -2]} rotation={[0, 0.4, 0]} seed={3} />
      <LowShelf position={[hallX + 1.6, 0, -5.5]} rotation={[0, -0.3, 0]} seed={9} />
      <LowShelf position={[hallX - 1.5, 0, -9]} rotation={[0, 0.2, 0]} seed={15} />
    </group>
  )
}

function Stairs() {
  const hallX = -8
  const steps = useMemo(() => {
    const items = []
    const count = 10
    const rise = 0.36
    const run = 0.38
    for (let i = 0; i < count; i++) {
      items.push({
        y: rise * (i + 0.5),
        z: -11.5 - run * i,
        w: 2.2,
        h: rise,
        d: run,
      })
    }
    return items
  }, [])

  return (
    <group>
      {steps.map((s, i) => (
        <OutlineBox key={i} position={[hallX, s.y, s.z]} size={[s.w, s.h, s.d]} color={i % 2 === 0 ? '#0c0c0c' : FILL_DARKER} />
      ))}
      <OutlineBox position={[hallX - 1.25, 1.8, -13.2]} size={[0.08, 3.6, 3.6]} color="#151515" outline="#555555" />
      <OutlineBox position={[hallX + 1.25, 1.8, -13.2]} size={[0.08, 3.6, 3.6]} color="#151515" outline="#555555" />
    </group>
  )
}

function UpstairsRoom() {
  const hallX = -8
  const floorY = 3.6

  return (
    <group>
      <mesh position={[hallX, floorY + 0.01, -17]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[7.5, 12]} />
        <meshBasicMaterial color="#050505" side={THREE.DoubleSide} />
      </mesh>
      <OutlineBox position={[hallX - 3.8, floorY + 1.8, -17]} size={[0.25, 3.6, 12]} color={FILL_DARKER} />
      <OutlineBox position={[hallX + 3.8, floorY + 1.8, -17]} size={[0.25, 3.6, 12]} color={FILL_DARKER} />
      <OutlineBox position={[hallX, floorY + 1.8, -23]} size={[7.8, 3.6, 0.25]} color={FILL_DARKER} />
      <mesh position={[hallX, floorY + 3.5, -17]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[7.8, 12]} />
        <meshBasicMaterial color="#030303" side={THREE.DoubleSide} />
      </mesh>
      <OutlineBox position={[hallX - 1.5, floorY + 0.45, -15.5]} size={[1.4, 0.9, 0.7]} color="#0e0e0e" />
      <OutlineBox position={[hallX + 1.4, floorY + 0.45, -18.5]} size={[1.2, 0.9, 0.7]} color="#0e0e0e" />
      <ReadingLamp position={[hallX - 1.2, floorY + 0.9, -15.5]} />
    </group>
  )
}

function writeText(ctx, text, progress, x, y, fontSize = 42, color = '#f5f5e6') {
  const visible = Math.floor(text.length * clamp(progress, 0, 1))
  if (visible <= 0) return
  ctx.save()
  ctx.fillStyle = color
  ctx.font = `${fontSize}px "Segoe Script", "Comic Sans MS", cursive`
  ctx.textBaseline = 'top'
  ctx.fillText(text.slice(0, visible), x, y)
  ctx.restore()
}

function Blackboard({
  position,
  rotation = [0, 0, 0],
  width = 3.2,
  height = 1.8,
  lines = [],
  writeStart = 0.75,
  writeEnd = 0.88,
  scrollProgress,
}) {
  const canvasTex = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1024
    canvas.height = 576
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    return tex
  }, [])

  const lastDraw = useRef(-1)

  useFrame(() => {
    const p = clamp((scrollProgress - writeStart) / (writeEnd - writeStart), 0, 1)
    const quant = Math.round(p * 120)
    if (quant === lastDraw.current) return
    lastDraw.current = quant
    const canvas = canvasTex.image
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = BOARD_FILL
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Crisp chalkboard border
    ctx.strokeStyle = '#222824'
    ctx.lineWidth = 10
    ctx.strokeRect(5, 5, canvas.width - 10, canvas.height - 10)

    // Subtle chalk eyebrow header
    ctx.fillStyle = '#ff3700'
    ctx.font = '600 22px "Helvetica Neue", Arial, sans-serif'
    ctx.textBaseline = 'top'
    ctx.fillText('LIVE LESSON · CHECKPOINT', 50, 42)

    for (let i = 0; i < lines.length; i++) {
      const lineProgress = clamp((p - i * 0.18) / 0.35, 0, 1)
      writeText(ctx, lines[i], lineProgress, 50, 95 + i * 120, 52)
    }
    canvasTex.needsUpdate = true
  })

  return (
    <group position={position} rotation={rotation}>
      <OutlineBox position={[0, 0, 0]} size={[width, height, 0.08]} color={FILL_DARKER} />
      <mesh position={[0, 0, 0.05]}>
        <planeGeometry args={[width - 0.16, height - 0.16]} />
        <meshBasicMaterial map={canvasTex} />
      </mesh>
      <OutlineBox position={[0, -height / 2 - 0.05, 0.06]} size={[width * 0.4, 0.08, 0.12]} color="#151515" />
    </group>
  )
}



const PIPELINE_STAGES = [
  {
    n: '01',
    title: 'Ingest',
    body: 'PDFs → structured text blocks',
    detail: 'Extracts headings, paragraphs & formulas locally',
    license: 'Apache-2.0 · Docling',
  },
  {
    n: '02',
    title: 'Embed',
    body: 'text → dense semantic vectors',
    detail: 'Local multilingual high-dimensional embeddings',
    license: 'MIT · BGE-M3',
  },
  {
    n: '03',
    title: 'Retrieve',
    body: 'query → grounded context + rerank',
    detail: 'Retrieves textbook chunks with neural reranking',
    license: 'Apache-2.0 · BGE-reranker',
  },
  {
    n: '04',
    title: 'Generate',
    body: 'topic + context → blackboard JSON',
    detail: 'Compact local SLM plans narration & board strokes',
    license: 'Apache-2.0 · Qwen3-4B',
  },
  {
    n: '05',
    title: 'Speak',
    body: 'narration → neural speech',
    detail: 'Multi-lingual audio synced to chalk stroke timing',
    license: 'Apache-2.0 · Kokoro-82M',
  },
  {
    n: '06',
    title: 'Render',
    body: 'actions → chalk strokes + checks',
    detail: 'Vector chalk drawing physics with active checkpoints',
    license: 'CC-BY-4.0 · Vector Engine',
  },
]

const BOARD_CX = -8
const BOARD_CY = 1.25
const BOARD_CZ = -6.5
const TILE_W = 1.55
const TILE_H = 0.74
const PITCH = 1.08 // vertical distance between each board in the 1x6 grid

function drawFormulas(ctx, w, h) {
  ctx.fillStyle = BOARD_FILL
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = '#2a2a2a'
  ctx.lineWidth = 6
  ctx.strokeRect(4, 4, w - 8, h - 8)
  ctx.fillStyle = '#f5f5e6'
  ctx.textBaseline = 'top'
  ctx.font = `${Math.round(h * 0.11)}px "Segoe Script", "Comic Sans MS", cursive`
  ctx.fillText('F = m · a', w * 0.06, h * 0.1)
  ctx.fillText('E = m c²', w * 0.42, h * 0.1)
  ctx.fillText('ΣF = dp/dt', w * 0.7, h * 0.1)
  ctx.fillText('∫ f(x) dx', w * 0.06, h * 0.42)
  ctx.fillText('d/dx xⁿ', w * 0.42, h * 0.42)
  ctx.fillText('V = I R', w * 0.7, h * 0.42)
  ctx.fillText('Σ 1/n² = π²/6', w * 0.18, h * 0.72)
}

function drawStageChalk(ctx, stage, wp, w, h) {
  ctx.fillStyle = BOARD_FILL
  ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = '#2d3830'
  ctx.lineWidth = 6
  ctx.strokeRect(4, 4, w - 8, h - 8)

  // Subtle chalk grid
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.025)'
  ctx.lineWidth = 1
  for (let x = 0; x < w; x += 64) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y < h; y += 64) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }

  // Header: Step number & Title
  writeText(ctx, `${stage.n}`, clamp(wp * 1.5, 0, 1), w * 0.06, h * 0.1, Math.round(h * 0.18), '#ffd154')
  writeText(ctx, `${stage.title}`, clamp(wp * 1.4, 0, 1), w * 0.18, h * 0.1, Math.round(h * 0.18), '#f5f5e6')
  writeText(ctx, stage.license, clamp((wp - 0.2) * 2, 0, 1), w * 0.62, h * 0.12, Math.round(h * 0.08), '#888888')

  // Chalk divider line
  ctx.globalAlpha = clamp(wp * 2, 0, 0.4)
  ctx.strokeStyle = '#666666'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(w * 0.06, h * 0.36)
  ctx.lineTo(w * 0.94, h * 0.36)
  ctx.stroke()
  ctx.globalAlpha = 1

  // Body
  writeText(ctx, stage.body, clamp((wp - 0.25) * 1.8, 0, 1), w * 0.06, h * 0.45, Math.round(h * 0.14), '#f5f5e6')

  // Detail
  writeText(ctx, stage.detail, clamp((wp - 0.5) * 2, 0, 1), w * 0.06, h * 0.72, Math.round(h * 0.1), '#aaaaaa')
}

function GiantBoard({ progress }) {
  const appear = clamp((progress - 0.32) / 0.04, 0, 1)
  const fadeOut = clamp((progress - 0.58) / 0.04, 0, 1)
  const totalOpacity = appear * (1 - fadeOut)

  const morph = smoothstep(clamp((progress - 0.345) / 0.02, 0, 1))

  const scrollFrac = clamp((progress - 0.35) / 0.23, 0, 1)
  const currentCenterIdx = scrollFrac * 5
  const stackY = BOARD_CY + currentCenterIdx * PITCH

  const bigTex = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1536
    canvas.height = 1024
    const ctx = canvas.getContext('2d')
    drawFormulas(ctx, canvas.width, canvas.height)
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    return tex
  }, [])

  const chalkCanvases = useMemo(
    () =>
      PIPELINE_STAGES.map(() => {
        const canvas = document.createElement('canvas')
        canvas.width = 1024
        canvas.height = 480
        const tex = new THREE.CanvasTexture(canvas)
        tex.colorSpace = THREE.SRGBColorSpace
        return { canvas, tex }
      }),
    [],
  )

  const arrowTex = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 256
    const ctx = canvas.getContext('2d')
    ctx.strokeStyle = '#ff3700'
    ctx.lineWidth = 5
    ctx.lineCap = 'round'
    ctx.setLineDash([10, 8])
    ctx.beginPath()
    ctx.moveTo(128, 20)
    ctx.lineTo(128, 175)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(92, 150)
    ctx.lineTo(128, 215)
    ctx.lineTo(164, 150)
    ctx.stroke()
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    return tex
  }, [])

  const lastWrites = useRef(PIPELINE_STAGES.map(() => -1))

  useFrame(() => {
    for (let i = 0; i < chalkCanvases.length; i++) {
      const stageStart = 0.34 + i * 0.038
      const wp = clamp((progress - stageStart) / 0.03, 0, 1)
      const quant = Math.round(wp * 80)
      if (quant === lastWrites.current[i]) continue
      lastWrites.current[i] = quant
      const { canvas, tex } = chalkCanvases[i]
      const ctx = canvas.getContext('2d')
      drawStageChalk(ctx, PIPELINE_STAGES[i], wp, canvas.width, canvas.height)
      tex.needsUpdate = true
    }
  })

  if (totalOpacity <= 0.01) return null

  return (
    <group position={[BOARD_CX, 0, BOARD_CZ]}>
      {morph < 0.99 && (
        <group position={[0, BOARD_CY, 0]} scale={lerp(0.5, 1, appear)}>
          <OutlineBox position={[0, 0, -0.02]} size={[TILE_W + 0.1, TILE_H + 0.1, 0.04]} color="#141414" outline="#383838" />
          <mesh renderOrder={2}>
            <planeGeometry args={[TILE_W, TILE_H]} />
            <meshBasicMaterial
              map={bigTex}
              transparent
              opacity={(1 - morph) * totalOpacity}
              depthTest={false}
              depthWrite={false}
            />
          </mesh>
        </group>
      )}

      {morph > 0.01 && (
        <group position={[0, stackY, 0]}>
          {PIPELINE_STAGES.map((stage, i) => {
            const boardY = -i * PITCH
            const appearAt = 0.34 + i * 0.038
            const boardAppear = smoothstep(clamp((progress - appearAt) / 0.02, 0, 1))
            const boardOpacity = morph * boardAppear * totalOpacity

            const arrowAppearAt = appearAt + 0.015
            const arrowAppear = smoothstep(clamp((progress - arrowAppearAt) / 0.018, 0, 1))
            const arrowOpacity = morph * arrowAppear * totalOpacity

            if (boardOpacity <= 0.01) return null

            return (
              <group key={stage.n} position={[0, boardY, 0]}>
                <OutlineBox
                  position={[0, 0, -0.015]}
                  size={[TILE_W + 0.08, TILE_H + 0.08, 0.035]}
                  color="#111111"
                  outline="#383838"
                />
                <OutlineBox
                  position={[0, -TILE_H / 2 - 0.02, 0.015]}
                  size={[TILE_W * 0.65, 0.025, 0.035]}
                  color="#1a1a1a"
                />
                <OutlineBox
                  position={[0.2, -TILE_H / 2 - 0.005, 0.028]}
                  size={[0.07, 0.015, 0.015]}
                  color="#f5f5e6"
                />
                <OutlineBox
                  position={[0.3, -TILE_H / 2 - 0.005, 0.028]}
                  size={[0.05, 0.015, 0.015]}
                  color="#ffd154"
                />

                <mesh position={[0, 0, 0.01]} renderOrder={3}>
                  <planeGeometry args={[TILE_W, TILE_H]} />
                  <meshBasicMaterial
                    map={chalkCanvases[i].tex}
                    transparent
                    opacity={boardOpacity}
                    depthTest={false}
                    depthWrite={false}
                  />
                </mesh>

                {i < PIPELINE_STAGES.length - 1 && arrowOpacity > 0.01 && (
                  <mesh position={[0, -PITCH / 2, 0.02]} renderOrder={4}>
                    <planeGeometry args={[0.36, 0.3]} />
                    <meshBasicMaterial
                      map={arrowTex}
                      transparent
                      opacity={arrowOpacity}
                      depthTest={false}
                      depthWrite={false}
                    />
                  </mesh>
                )}
              </group>
            )
          })}
        </group>
      )}
    </group>
  )
}

function BlackoutPlane({ progress }) {
  const fadeIn = clamp((progress - 0.34) / 0.04, 0, 1)
  const fadeOut = clamp((progress - 0.59) / 0.04, 0, 1)
  const opacity = fadeIn * (1 - fadeOut)
  if (opacity <= 0.01) return null
  return (
    <mesh position={[BOARD_CX, 1.2, -7.5]} renderOrder={1}>
      <planeGeometry args={[80, 50]} />
      <meshBasicMaterial
        color="#000000"
        transparent
        opacity={opacity * 0.92}
        depthWrite={false}
        depthTest={false}
      />
    </mesh>
  )
}

function LibraryWorld({ blackout, children }) {
  const ref = useRef()
  useFrame(() => {
    if (ref.current) ref.current.visible = blackout < 0.92
  })
  return <group ref={ref}>{children}</group>
}

function Laptop({ position, progress }) {
  const screenTex = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 512
    canvas.height = 300
    const ctx = canvas.getContext('2d')
    drawFormulas(ctx, canvas.width, canvas.height)
    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    return tex
  }, [])

  const screenOn = clamp((progress - 0.2) / 0.08, 0, 1)

  return (
    <group position={position}>
      <OutlineBox position={[0, 0.03, 0]} size={[0.95, 0.05, 0.62]} color="#101010" />
      <OutlineBox position={[0, 0.055, 0.05]} size={[0.5, 0.01, 0.35]} color="#0c0c0c" outline="#444444" />
      <group position={[0, 0.05, -0.3]} rotation={[-Math.PI * 0.58, 0, 0]}>
        <OutlineBox position={[0, 0.28, 0]} size={[0.95, 0.56, 0.035]} color="#0c0c0c" />
        <mesh position={[0, 0.28, 0.02]}>
          <planeGeometry args={[0.86, 0.5]} />
          <meshBasicMaterial color={BOARD_FILL} />
        </mesh>
        <mesh position={[0, 0.28, 0.021]}>
          <planeGeometry args={[0.86, 0.5]} />
          <meshBasicMaterial
            map={screenTex}
            transparent
            opacity={0.15 + 0.85 * screenOn}
          />
        </mesh>
      </group>
    </group>
  )
}

function FloorGrid() {
  const grid = useMemo(() => {
    const pts = []
    const size = 60
    const step = 2
    for (let i = -size; i <= size; i += step) {
      pts.push(new THREE.Vector3(-size, 0, i), new THREE.Vector3(size, 0, i))
      pts.push(new THREE.Vector3(i, 0, -size), new THREE.Vector3(i, 0, size))
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts)
    return geo
  }, [])

  return (
    <lineSegments geometry={grid} position={[0, -0.01, 0]}>
      <lineBasicMaterial color="#1c1c1c" />
    </lineSegments>
  )
}

const CAMERA_KEYS = [
  { p: 0.0, pos: [0, 2.4, 34], look: [0, 2.0, 10] },
  { p: 0.08, pos: [0.2, 2.35, 28], look: [0, 1.95, 8] },
  { p: 0.16, pos: [0.3, 2.25, 18], look: [0, 1.85, 4] },
  { p: 0.22, pos: [-2, 2.0, 8], look: [-6, 1.6, 0] },
  { p: 0.26, pos: [-6.5, 1.7, 2], look: [-8, 1.0, -4.5] },
  { p: 0.3, pos: [-7.5, 1.45, -0.5], look: [-8, 1.05, -5.2] },
  { p: 0.35, pos: [-8, 1.25, -3.3], look: [-8, 1.25, -6.5] },
  { p: 0.42, pos: [-8, 1.25, -3.3], look: [-8, 1.25, -6.5] },
  { p: 0.5, pos: [-8, 1.25, -3.3], look: [-8, 1.25, -6.5] },
  { p: 0.58, pos: [-8, 1.25, -3.3], look: [-8, 1.25, -6.5] },
  { p: 0.62, pos: [-8, 1.5, 0.5], look: [-8, 1.2, -4.0] },
  { p: 0.68, pos: [-8, 1.7, 1.5], look: [-8, 1.4, -6] },
  { p: 0.74, pos: [-8, 1.9, -7.5], look: [-8, 1.9, -12] },
  { p: 0.8, pos: [-8, 2.5, -11.8], look: [-8, 3.1, -14.5] },
  { p: 0.86, pos: [-8, 3.5, -13.4], look: [-8, 4.0, -16.5] },
  { p: 0.92, pos: [-8.4, 4.25, -16.5], look: [-8.3, 4.35, -20] },
  { p: 1.0, pos: [-8.75, 4.45, -19.4], look: [-8.75, 4.45, -23.2] },
]

function sampleCamera(progress) {
  const p = clamp(progress, 0, 1)
  let i = 0
  while (i < CAMERA_KEYS.length - 2 && p > CAMERA_KEYS[i + 1].p) i++
  const a = CAMERA_KEYS[i]
  const b = CAMERA_KEYS[i + 1]
  const t = smoothstep((p - a.p) / (b.p - a.p || 1))
  return {
    pos: [lerp(a.pos[0], b.pos[0], t), lerp(a.pos[1], b.pos[1], t), lerp(a.pos[2], b.pos[2], t)],
    look: [lerp(a.look[0], b.look[0], t), lerp(a.look[1], b.look[1], t), lerp(a.look[2], b.look[2], t)],
  }
}

function CameraRig({ progress, isOverBackground }) {
  const target = useRef(new THREE.Vector3(0, 2, 0))
  useFrame(({ camera, pointer }) => {
    const shot = sampleCamera(progress)
    
    // Interactive mouse parallax movement
    const px = (pointer?.x || 0) * 0.95
    const py = (pointer?.y || 0) * 0.55
    
    // Dynamic subtle zoom when cursor is over the background (enlarges scene by ~3.5%)
    const zoomOffset = isOverBackground ? 0.75 : 0

    const destPos = new THREE.Vector3(
      shot.pos[0] + px,
      shot.pos[1] + py,
      shot.pos[2] - zoomOffset
    )
    const destLook = new THREE.Vector3(
      shot.look[0] + px * 0.35,
      shot.look[1] + py * 0.25,
      shot.look[2]
    )

    camera.position.lerp(destPos, 0.05)
    target.current.lerp(destLook, 0.05)
    camera.lookAt(target.current)
  })
  return null
}

export default function LibraryScene({ progress, isOverBackground }) {
  const hallX = -8
  const floorY = 3.6
  const blackoutIn = clamp((progress - 0.34) / 0.04, 0, 1)
  const blackoutOut = clamp((progress - 0.59) / 0.04, 0, 1)
  const blackout = blackoutIn * (1 - blackoutOut)

  return (
    <>
      <color attach="background" args={['#000000']} />
      <CameraRig progress={progress} isOverBackground={isOverBackground} />
      <LibraryWorld blackout={blackout}>
        <FloorGrid />
        <Street />
        <LibraryShell />
        <LibraryHall />
        <Laptop position={[-8, 0.82, -5.4]} progress={progress} />
        <Stairs />
        <UpstairsRoom />
      </LibraryWorld>
      <BlackoutPlane progress={progress} />
      <GiantBoard progress={progress} />

      <Blackboard
        position={[hallX - 3.55, floorY + 1.0, -17]}
        rotation={[0, Math.PI / 2, 0]}
        width={3.2}
        height={1.8}
        lines={['F = m · a', 'ΣF = dp/dt']}
        writeStart={0.88}
        writeEnd={0.92}
        scrollProgress={progress}
      />
      <Blackboard
        position={[hallX + 3.55, floorY + 1.0, -17]}
        rotation={[0, -Math.PI / 2, 0]}
        width={3.2}
        height={1.8}
        lines={['E = m c²', 'ΔE = mc²']}
        writeStart={0.9}
        writeEnd={0.94}
        scrollProgress={progress}
      />
      <Blackboard
        position={[hallX + 0.65, floorY + 1.1, -22.75]}
        rotation={[0, -0.06, 0]}
        width={3.0}
        height={1.85}
        lines={['∫ f(x) dx = F(b) − F(a)', 'd/dx xⁿ = n xⁿ⁻¹', 'Σ 1/n² = π²/6']}
        writeStart={0.93}
        writeEnd={0.99}
        scrollProgress={progress}
      />
    </>
  )
}
