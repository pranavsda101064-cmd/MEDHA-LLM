import { Canvas } from '@react-three/fiber'
import { Suspense } from 'react'
import LibraryScene from './LibraryScene.jsx'

export default function LibraryCanvas({ progress, isOverBackground = false }) {
  return (
    <div
      className={`pointer-events-none fixed inset-0 z-0 transition-transform duration-700 ease-out ${
        isOverBackground ? 'scale-[1.03]' : 'scale-100'
      }`}
      style={{
        transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: 0.9,
      }}
    >
      <Canvas
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        camera={{ fov: 50, near: 0.1, far: 140, position: [0, 2.6, 24] }}
        style={{ width: '100%', height: '100%' }}
      >
        <Suspense fallback={null}>
          <LibraryScene progress={progress} isOverBackground={isOverBackground} />
        </Suspense>
      </Canvas>
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.55) 75%, rgba(0,0,0,0.92) 100%)',
        }}
      />
    </div>
  )
}
