import { Component, Input, OnDestroy, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { ClusterResponse } from '../models/ml.models';
import * as THREE from 'three';

const PALETTE = [
  0x6366f1, 0xec4899, 0x14b8a6, 0xf97316, 0x22c55e,
  0xeab308, 0xa855f7, 0x06b6d4, 0xef4444, 0x8b5cf6,
];

const ALGO_LABEL: Record<string, string> = {
  kmeans: 'Standard',
  dbscan: 'Flexible',
};

function hexToRgb(hex: number) {
  return { r: ((hex >> 16) & 0xff) / 255, g: ((hex >> 8) & 0xff) / 255, b: (hex & 0xff) / 255 };
}

function safe(v: number | null | undefined, fallback = '—'): string {
  return v != null ? String(v) : fallback;
}

@Component({
  selector: 'app-cluster-chart',
  standalone: false,
  template: `
    <div class="cluster-3d-root">
      <div #renderContainer class="cluster-canvas"></div>

      <div class="ch-hud-top">
        <div class="ch-badge">
          <span class="ch-dot" [style.background]="assignedColorHex"></span>
          <span class="ch-name">{{ groupName }}</span>
        </div>
      </div>

      <div class="ch-hud-bottom">
        <div class="ch-stat">
          <span class="ch-val">{{ safeN(n_clusters_detected) }}</span>
          <span class="ch-lbl">Groups Found</span>
        </div>
        <div class="ch-stat ch-stat-accent" *ngIf="silhouette_score != null">
          <span class="ch-val">{{ silhouette_score != null ? (silhouette_score | number:'1.2-2') : '—' }}</span>
          <span class="ch-lbl">Group Clarity</span>
        </div>
        <div class="ch-stat" *ngIf="davies_bouldin_score != null">
          <span class="ch-val">{{ davies_bouldin_score != null ? (davies_bouldin_score | number:'1.2-2') : '—' }}</span>
          <span class="ch-lbl">Separation</span>
        </div>
        <div class="ch-stat">
          <span class="ch-val">{{ safeN(noise_points) }}</span>
          <span class="ch-lbl">Unclassified</span>
        </div>
        <div class="ch-stat">
          <span class="ch-val ch-algo">{{ algoLabel }}</span>
          <span class="ch-lbl">Method</span>
        </div>
      </div>

      <div class="ch-hint">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        <span>Drag to explore · Scroll to zoom</span>
      </div>
    </div>
  `,
  styles: [`
    .cluster-3d-root {
      position: relative; width: 100%; border-radius: 12px;
      overflow: hidden; background: #060a14; min-height: 320px;
    }
    .cluster-canvas { width: 100%; height: 320px; display: block; cursor: grab; }
    .cluster-canvas:active { cursor: grabbing; }

    .ch-hud-top {
      position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
      pointer-events: none; z-index: 2;
    }
    .ch-badge {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 20px 6px 14px; border-radius: 100px;
      background: rgba(6, 10, 20, 0.65); backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.06);
      font-size: 13px; font-weight: 600; color: #e8edf5; letter-spacing: 0.01em;
    }
    .ch-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 8px currentColor; }
    .ch-name { white-space: nowrap; }

    .ch-hud-bottom {
      position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
      display: flex; gap: 3px; pointer-events: none; z-index: 2;
    }
    .ch-stat {
      text-align: center; padding: 7px 14px 6px; border-radius: 8px;
      background: rgba(6, 10, 20, 0.55); backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.04); min-width: 64px;
    }
    .ch-stat-accent {
      border-color: rgba(99, 102, 241, 0.25);
      background: rgba(99, 102, 241, 0.08);
    }
    .ch-val { display: block; font-size: 14px; font-weight: 700; color: #e8edf5; line-height: 1.3; }
    .ch-algo { font-size: 11px; font-weight: 600; }
    .ch-lbl {
      display: block; font-size: 8.5px; color: rgba(255,255,255,0.35);
      text-transform: uppercase; letter-spacing: 0.07em; margin-top: 1px;
    }

    .ch-hint {
      position: absolute; top: 16px; right: 14px; z-index: 2;
      display: flex; align-items: center; gap: 5px;
      font-size: 10px; color: rgba(255,255,255,0.2);
      pointer-events: none; opacity: 0.6;
    }
  `]
})
export class ClusterChartComponent implements AfterViewInit, OnDestroy {
  @ViewChild('renderContainer', { static: true }) container!: ElementRef<HTMLDivElement>;

  assignedColorHex = '#6366f1';
  groupName = '';
  algoLabel = 'Standard';
  n_clusters_detected: number | null = null;
  noise_points: number | null = null;
  silhouette_score: number | null = null;
  davies_bouldin_score: number | null = null;

  private _data: ClusterResponse | null = null;
  @Input() set data(v: ClusterResponse | null) {
    this._data = v;
    if (v) {
      this.n_clusters_detected = v.n_clusters_detected ?? null;
      this.noise_points = v.noise_points ?? null;
      this.silhouette_score = v.silhouette_score ?? null;
      this.davies_bouldin_score = v.davies_bouldin_score ?? null;
      this.groupName = v.cluster_name || `Group ${v.cluster_id}`;
      this.algoLabel = ALGO_LABEL[v.algorithm?.toLowerCase()] || v.algorithm || 'Standard';
      this.assignedColorHex = '#' + PALETTE[(v.cluster_id ?? 0) % PALETTE.length].toString(16).padStart(6, '0');
      if (this.renderer) this.buildScene();
    }
  }
  get data(): ClusterResponse | null { return this._data; }

  private scene!: THREE.Scene;
  private camera!: THREE.PerspectiveCamera;
  private renderer!: THREE.WebGLRenderer;
  private animId = 0;
  private clock = new THREE.Clock();
  private particles: THREE.Points[] = [];
  private glows: THREE.Sprite[] = [];
  private rings: THREE.Line[] = [];
  private connections: THREE.Line[] = [];

  private spherical = { theta: 0.6, phi: 0.5, radius: 6.5 };
  private targetTheta = 0.6;
  private targetPhi = 0.5;
  private velocityTheta = 0;
  private velocityPhi = 0;
  private isDragging = false;
  private prevMouse = { x: 0, y: 0 };

  ngAfterViewInit(): void {
    this.initScene();
    if (this._data) this.buildScene();
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.animId);
    this.disposeScene();
    this.renderer?.dispose();
  }

  private initScene(): void {
    const el = this.container.nativeElement;
    const w = el.clientWidth || 480;
    const h = 320;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x060a14);

    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 100);
    this.updateCamera();

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x060a14, 1);
    el.appendChild(this.renderer.domElement);

    const amb = new THREE.AmbientLight(0x444466, 0.5);
    this.scene.add(amb);
    const dir = new THREE.DirectionalLight(0x8888ff, 0.8);
    dir.position.set(4, 8, 6);
    this.scene.add(dir);
    const fill = new THREE.DirectionalLight(0xff8888, 0.3);
    fill.position.set(-4, 2, -6);
    this.scene.add(fill);

    const pts: number[] = [];
    const segs = 64;
    const r = 3.8;
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(Math.cos(a) * r, -1.8, Math.sin(a) * r);
    }
    const fgeo = new THREE.BufferGeometry();
    fgeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    const fmat = new THREE.LineBasicMaterial({ color: 0x8888ff, transparent: true, opacity: 0.08 });
    this.scene.add(new THREE.Line(fgeo, fmat));

    el.addEventListener('pointerdown', this.onPointerDown);
    el.addEventListener('pointermove', this.onPointerMove);
    el.addEventListener('pointerup', this.onPointerUp);
    el.addEventListener('wheel', this.onWheel, { passive: true });

    this.animate();
  }

  private updateCamera(): void {
    const { theta, phi, radius } = this.spherical;
    this.camera.position.set(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.sin(theta),
    );
    this.camera.lookAt(0, 0, 0);
  }

  private onPointerDown = (e: PointerEvent): void => {
    this.isDragging = true;
    this.prevMouse = { x: e.clientX, y: e.clientY };
    this.velocityTheta = 0;
    this.velocityPhi = 0;
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (!this.isDragging) return;
    const dx = e.clientX - this.prevMouse.x;
    const dy = e.clientY - this.prevMouse.y;
    this.velocityTheta = -dx * 0.006;
    this.velocityPhi = dy * 0.006;
    this.targetTheta += this.velocityTheta;
    this.targetPhi = Math.max(0.15, Math.min(Math.PI - 0.15, this.targetPhi + this.velocityPhi));
    this.prevMouse = { x: e.clientX, y: e.clientY };
  };

  private onPointerUp = (): void => {
    this.isDragging = false;
  };

  private onWheel = (e: WheelEvent): void => {
    this.spherical.radius = Math.max(3.5, Math.min(16, this.spherical.radius + e.deltaY * 0.012));
  };

  private buildScene(): void {
    this.clearVisuals();
    const d = this._data;
    if (!d) return;
    const n = Math.max(d.n_clusters_detected ?? 3, 1);
    const assigned = d.cluster_id;
    const silhouette = d.silhouette_score ?? 0;
    const algo = (d.algorithm || '').toLowerCase();

    const spread = 0.35 + Math.max(0, 1 - Math.abs(silhouette)) * 0.7;
    const positions: { cx: number; cy: number; cz: number; color: number; isAssigned: boolean }[] = [];

    const radius = 2.2 + (silhouette > 0 ? silhouette * 0.5 : 0.1);
    const yOff = algo === 'dbscan' ? 1.2 : 0.4;

    for (let i = 0; i < n; i++) {
      const isAssigned = i === assigned;
      const color = PALETTE[i % PALETTE.length];
      const angle = (i / n) * Math.PI * 2;
      const cx = Math.cos(angle) * radius;
      const cz = Math.sin(angle) * radius;
      const cy = (Math.random() - 0.5) * yOff;
      positions.push({ cx, cy, cz, color, isAssigned });
      this.addGlow(cx, cy, cz, color, isAssigned);
      this.addParticleCluster(cx, cy, cz, color, isAssigned, spread, isAssigned ? 320 : 140);
      if (isAssigned) this.addRing(cx, cy, cz, color);
    }

    const assignedPos = positions.find(p => p.isAssigned);
    if (assignedPos) {
      for (const p of positions) {
        if (p === assignedPos) continue;
        const geo = new THREE.BufferGeometry();
        const v = new Float32Array([
          assignedPos.cx, assignedPos.cy, assignedPos.cz,
          p.cx, p.cy, p.cz,
        ]);
        geo.setAttribute('position', new THREE.BufferAttribute(v, 3));
        const mat = new THREE.LineBasicMaterial({ color: assignedPos.color, transparent: true, opacity: 0.06 });
        const line = new THREE.Line(geo, mat);
        this.scene.add(line);
        this.connections.push(line);
      }
    }
  }

  private addParticleCluster(cx: number, cy: number, cz: number, color: number, isAssigned: boolean, spread: number, count: number): void {
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = Math.cbrt(Math.random()) * spread * (isAssigned ? 1.0 : 0.7);
      pos[i * 3] = cx + r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = cy + r * Math.cos(phi) * 0.55;
      pos[i * 3 + 2] = cz + r * Math.sin(phi) * Math.sin(theta);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({
      color, size: isAssigned ? 0.15 : 0.10, transparent: true,
      opacity: isAssigned ? 0.92 : 0.50, blending: THREE.AdditiveBlending,
      depthWrite: false, sizeAttenuation: true,
    });
    const points = new THREE.Points(geo, mat);
    this.scene.add(points);
    this.particles.push(points);
  }

  private addGlow(cx: number, cy: number, cz: number, color: number, isAssigned: boolean): void {
    const canvas = document.createElement('canvas');
    canvas.width = 128; canvas.height = 128;
    const ctx = canvas.getContext('2d')!;
    const rgb = hexToRgb(color);
    const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, `rgba(${rgb.r * 255},${rgb.g * 255},${rgb.b * 255},1)`);
    grad.addColorStop(0.15, `rgba(${rgb.r * 255},${rgb.g * 255},${rgb.b * 255},${isAssigned ? 0.7 : 0.3})`);
    grad.addColorStop(0.5, `rgba(${rgb.r * 255},${rgb.g * 255},${rgb.b * 255},${isAssigned ? 0.35 : 0.1})`);
    grad.addColorStop(1, `rgba(${rgb.r * 255},${rgb.g * 255},${rgb.b * 255},0)`);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 128, 128);
    const tex = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({
      map: tex, blending: THREE.AdditiveBlending, transparent: true,
      depthWrite: false, opacity: isAssigned ? 0.85 : 0.40,
    });
    const sprite = new THREE.Sprite(mat);
    sprite.position.set(cx, cy, cz);
    const s = isAssigned ? 2.4 : 1.3;
    sprite.scale.set(s, s, 1);
    this.scene.add(sprite);
    this.glows.push(sprite);
  }

  private addRing(cx: number, cy: number, cz: number, color: number): void {
    const segs = 48;
    const geo = new THREE.BufferGeometry();
    const pos: number[] = [];
    const r = 0.9;
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pos.push(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.25, cz + Math.sin(a) * r * 0.4);
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.12 });
    const line = new THREE.Line(geo, mat);
    this.scene.add(line);
    this.rings.push(line);
  }

  private clearVisuals(): void {
    for (const p of this.particles) { this.scene.remove(p); p.geometry.dispose(); (p.material as THREE.Material).dispose(); }
    for (const g of this.glows) { this.scene.remove(g); g.material.dispose(); }
    for (const r of this.rings) { this.scene.remove(r); r.geometry.dispose(); (r.material as THREE.Material).dispose(); }
    for (const c of this.connections) { this.scene.remove(c); c.geometry.dispose(); (c.material as THREE.Material).dispose(); }
    this.particles = [];
    this.glows = [];
    this.rings = [];
    this.connections = [];
  }

  private disposeScene(): void {
    this.clearVisuals();
  }

  safeN(v: number | null | undefined): string {
    return safe(v);
  }

  private animate = (): void => {
    this.animId = requestAnimationFrame(this.animate);
    const t = this.clock.getElapsedTime();

    if (!this.isDragging) {
      this.velocityTheta *= 0.92;
      this.velocityPhi *= 0.92;
      this.targetTheta += this.velocityTheta;
      this.targetPhi += this.velocityPhi;
      this.targetPhi = Math.max(0.15, Math.min(Math.PI - 0.15, this.targetPhi));
    }

    this.spherical.theta += (this.targetTheta - this.spherical.theta) * 0.10;
    this.spherical.phi += (this.targetPhi - this.spherical.phi) * 0.10;
    this.updateCamera();

    this.particles.forEach((p, i) => {
      const s = 1 + Math.sin(t * 0.5 + i * 0.7) * 0.02;
      p.scale.set(s, s, s);
    });
    this.glows.forEach((g, i) => {
      const pulse = 1 + Math.sin(t * 0.65 + i * 0.8) * 0.06;
      g.scale.setScalar(pulse);
    });

    this.renderer.render(this.scene, this.camera);
  };
}
