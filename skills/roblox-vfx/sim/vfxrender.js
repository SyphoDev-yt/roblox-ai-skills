/* vfxrender.js - draws a VFXSIM.World with three.js r128.
 *
 * Blend model (the one property that decides how an effect reads):
 * Roblox's LightEmission interpolates normal alpha blending (0) and additive
 * (1). With premultiplied output rgb = c*a, alpha = a*(1-LightEmission) and
 * blend (ONE, ONE_MINUS_SRC_ALPHA) the result is
 *     dst' = c*a + dst*(1 - a*(1 - LightEmission))
 * i.e. exactly alpha blend at 0 and exactly additive at 1.
 *
 * Post: scene renders to a half-float target, then a bloom pass (Lighting's
 * BloomEffect) and a ColorCorrectionEffect pass, then to the canvas.
 */
(function (root) {
  "use strict";
  const SIM = root.VFXSIM;
  const T = root.THREE;
  const { V, CF, nsAt, csAt, flipFrame, flipGrid } = SIM;

  // Stock rbxasset textures the sim approximates with its own sprites.
  const STOCK = {
    "rbxasset://textures/particles/sparkles_main.dds": "star4",
    "rbxasset://textures/particles/fire_main.dds": "soft_dot",
    "rbxasset://textures/particles/smoke_main.dds": "soft_dot",
    "rbxasset://textures/explosion.png": "soft_dot",
    "rbxasset://textures/sparkle.png": "star4",
  };

  const PVERT = `
    attribute vec2 uvA; attribute vec2 uvB; attribute vec4 rgba; attribute float blend;
    varying vec2 vA; varying vec2 vB; varying vec4 vC; varying float vBl;
    void main(){ vA=uvA; vB=uvB; vC=rgba; vBl=blend;
      gl_Position = projectionMatrix * viewMatrix * vec4(position,1.0); }`;
  const PFRAG = `
    uniform sampler2D map; uniform float le; uniform float hasMap;
    varying vec2 vA; varying vec2 vB; varying vec4 vC; varying float vBl;
    void main(){
      vec4 t = hasMap > 0.5 ? mix(texture2D(map,vA), texture2D(map,vB), vBl) : vec4(1.0);
      float a = t.a * vC.a;
      if (a < 0.002) discard;
      gl_FragColor = vec4(t.rgb * vC.rgb * a, a * (1.0 - le));
    }`;

  // SurfaceAppearance on a MeshPart: ColorMap (alpha used only when AlphaMode
  // is Transparency) tinted by Color, lit by a simple sun/sky term, plus
  // EmissiveMask * EmissiveTint pushes toward white with a saturating curve in EmissiveStrength,
  // capped at 1 (no HDR, so no bloom), as measured in Roblox.
  const SA_VERT = `varying vec2 vUv; varying vec3 vN;
    void main(){ vUv=uv; vN=normalize(mat3(modelMatrix)*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
  const SA_FRAG = `uniform sampler2D map; uniform float hasMap; uniform sampler2D emask; uniform float hasMask;
    uniform vec3 tint; uniform vec3 partColor; uniform vec3 eTint; uniform float eStr; uniform float opacity; uniform float alphaMode; uniform float ambient;
    varying vec2 vUv; varying vec3 vN;
    void main(){
      vec4 t = hasMap > 0.5 ? texture2D(map, vUv) : vec4(1.0);
      vec3 base = alphaMode > 0.5 ? t.rgb : mix(partColor, t.rgb, t.a);
      // ambient: 1 by day, lower at night (Studio round 2: unlit surfaces go much darker at ClockTime 0)
      float lam = ambient * (0.62 + 0.38 * max(dot(normalize(vN), normalize(vec3(0.5,1.0,0.35))), 0.0));
      vec3 c = base * tint * lam;
      float m = hasMask > 0.5 ? texture2D(emask, vUv).r * texture2D(emask, vUv).a : 0.0;
      // Roblox SurfaceAppearance emissive saturates and never reaches HDR (measured 2026-10-27:
      // lum 114 / 195 / 222 at strength 0 / 1 / 2.5, no bloom halo even with BloomEffect on).
      // colour comes from EmissiveTint (not the ColorMap); fit: daylight probe lum 114/195/222 at
      // strength 0/1/2.5 and a white-hot dome at night at 2.6 (Studio round 2).
      // emission = surface colour (ColorMap x Color) x EmissiveTint x strength, saturating (fit to Studio:
      // daylight probe lum 114/195/222 at 0/1/2.5, cream-tinted dome white at night, orange dome stays orange)
      vec3 e = base * tint * eTint * eStr * m;
      c = min(c + (vec3(1.0) - c) * (vec3(1.0) - exp(-1.3 * e)), vec3(1.0));
      float a = (alphaMode > 0.5 ? t.a : 1.0) * opacity;
      if (a < 0.003) discard;
      gl_FragColor = vec4(c, a);
    }`;

  function fsMat(frag, uniforms) {
    return new T.ShaderMaterial({
      uniforms, depthTest: false, depthWrite: false,
      vertexShader: "varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }",
      fragmentShader: frag,
    });
  }

  class Renderer {
    constructor(canvas, opts) {
      this.opts = Object.assign({ base: "", assetMap: {}, libTex: null }, opts || {});
      this.canvas = canvas;
      this.gl = new T.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true, alpha: false });
      this.gl.setPixelRatio(Math.min(2, root.devicePixelRatio || 1));
      this.gl.autoClear = true;
      this.scene = new T.Scene();
      this.camera = new T.PerspectiveCamera(70, 1, 0.1, 2000);
      this.cam = { at: [0, 3, 0], yaw: 0.6, pitch: 0.25, dist: 16 };
      this.tex = {};
      this.meshGeo = {};
      this.pending = 0;
      this.objs = new Map();
      this.warnings = new Set();
      this.view = { ground: "light", dummy: true, bloom: true, greyscale: false };
      this.buildStage();
      this.buildPost();
      this.resize();
    }
    // -------------------------------------------------- assets
    texURL(name) {
      if (!name) return null;
      if (STOCK[name]) name = "sim:" + STOCK[name];
      if (name.startsWith("sim:")) return this.opts.base + "textures/" + name.slice(4) + ".png";
      const m = name.match(/(\d{5,})/);
      if (m) {
        if (this.opts.assetMap[m[1]]) return this.opts.assetMap[m[1]];
        if (this.opts.libTex) return this.opts.libTex + m[1] + ".png";
      }
      this.warnings.add(`texture not available offline: ${name} (drawn as a soft dot)`);
      return this.opts.base + "textures/soft_dot.png";
    }
    getTex(name) {
      const url = this.texURL(name);
      if (!url) return null;
      if (this.tex[url]) return this.tex[url];
      this.pending++;
      const t = new T.TextureLoader().load(url, () => { this.pending--; }, undefined, () => {
        this.pending--; this.warnings.add(`failed to load ${url}`);
      });
      t.wrapS = t.wrapT = T.RepeatWrapping;
      t.anisotropy = 4;
      this.tex[url] = t;
      return t;
    }
    getMesh(id) {
      if (this.meshGeo[id] !== undefined) return this.meshGeo[id];
      this.meshGeo[id] = null;
      const name = id.startsWith("sim:") ? id.slice(4) : null;
      if (!name) { this.warnings.add(`mesh not available offline: ${id}`); return null; }
      this.pending++;
      fetch(this.opts.base + "meshes/" + name + ".obj").then((r) => r.text()).then((txt) => {
        this.meshGeo[id] = parseOBJ(txt);
        this.pending--;
      }).catch(() => { this.pending--; this.warnings.add(`failed to load mesh ${name}`); });
      return null;
    }
    ready() {
      return new Promise((res) => {
        const tick = () => (this.pending <= 0 ? res() : setTimeout(tick, 30));
        tick();
      });
    }
    // -------------------------------------------------- stage
    buildStage() {
      const s = this.scene;
      const skyGeo = new T.SphereGeometry(900, 32, 16);
      this.skyMat = new T.ShaderMaterial({
        side: T.BackSide, depthWrite: false,
        uniforms: { top: { value: new T.Color(0.3, 0.52, 0.85) }, bottom: { value: new T.Color(0.62, 0.74, 0.88) } },
        vertexShader: "varying vec3 p; void main(){ p=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
        fragmentShader: "uniform vec3 top; uniform vec3 bottom; varying vec3 p; void main(){ gl_FragColor=vec4(mix(bottom,top,clamp(p.y*1.6,0.0,1.0)),1.0); }",
      });
      s.add(new T.Mesh(skyGeo, this.skyMat));
      this.hemi = new T.HemisphereLight(0xdfe8ff, 0x6d6a66, 0.5);
      s.add(this.hemi);
      this.sun = new T.DirectionalLight(0xffffff, 0.5);
      this.sun.position.set(30, 60, 20);
      s.add(this.sun);
      // baseplate with a stud grid, like the default Baseplate
      const c = document.createElement("canvas");
      c.width = c.height = 256;
      const g = c.getContext("2d");
      g.fillStyle = "#fff"; g.fillRect(0, 0, 256, 256);
      g.strokeStyle = "rgba(0,0,0,0.09)"; g.lineWidth = 4; g.strokeRect(0, 0, 256, 256);
      this.gridTex = new T.CanvasTexture(c);
      this.gridTex.wrapS = this.gridTex.wrapT = T.RepeatWrapping;
      this.gridTex.repeat.set(64, 64);
      this.groundMat = new T.MeshLambertMaterial({ map: this.gridTex, color: 0xa3a2a5 });
      const ground = new T.Mesh(new T.PlaneGeometry(4096, 4096), this.groundMat);
      this.gridTex.repeat.set(512, 512);
      ground.rotation.x = -Math.PI / 2;
      s.add(ground);
      // R6 dummy, feet at y=0, facing -Z
      this.dummy = new T.Group();
      const dm = new T.MeshLambertMaterial({ color: 0xa3a2a5 });
      const box = (nm, w, h, d, x, y, z) => { const m = new T.Mesh(new T.BoxGeometry(w, h, d), dm); m.position.set(x, y, z); m.name = nm; this.dummy.add(m); return m; };
      box("LeftLeg", 1, 2, 1, -0.5, 1, 0); box("RightLeg", 1, 2, 1, 0.5, 1, 0);
      box("Torso", 2, 2, 1, 0, 3, 0);
      box("LeftArm", 1, 2, 1, -1.5, 3, 0); box("RightArm", 1, 2, 1, 1.5, 3, 0);
      const head = new T.Mesh(new T.CylinderGeometry(0.62, 0.62, 1.2, 20), dm); head.position.set(0, 4.6, 0); head.name = "Head"; this.dummy.add(head);
      // rubber-arm tubes (hidden unless a pose reaches)
      for (const nm of ["RightTube", "LeftTube"]) { const m = new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 1, 16), dm); m.name = nm; m.visible = false; this.dummy.add(m); }
      this.rigMesh = {};
      for (const m of this.dummy.children) this.rigMesh[m.name] = m;
      this.ghostPool = [];
      s.add(this.dummy);
    }
    setView(v) {
      Object.assign(this.view, v);
      const g = this.view.ground;
      this.groundMat.color.set(g === "dark" ? 0x2a2c30 : g === "grass" ? 0x4b8f3a : 0xa3a2a5);
      const night = this.view.sky === "night";
      this.skyMat.uniforms.top.value.set(night ? 0x05070d : 0x4d85d9);
      this.skyMat.uniforms.bottom.value.set(night ? 0x141824 : 0x9ebde0);
      this.hemi.intensity = night ? 0.2 : 0.5;
      this.sun.intensity = night ? 0.1 : 0.5;
      this.dummy.visible = !!this.view.dummy;
      // distance haze for big, far effects (Atmosphere stand-in): [near, far, rgb]
      const f = this.view.fog;
      this.scene.fog = f ? new T.Fog(new T.Color(f[2][0], f[2][1], f[2][2]), f[0], f[1]) : null;
      if (this.view.dummyAt) this.dummy.position.set(...this.view.dummyAt);
    }
    // -------------------------------------------------- post
    buildPost() {
      const opt = { type: T.HalfFloatType, minFilter: T.LinearFilter, magFilter: T.LinearFilter };
      const isGL2 = this.gl.capabilities.isWebGL2;
      this.rtScene = isGL2 && T.WebGLMultisampleRenderTarget ? new T.WebGLMultisampleRenderTarget(4, 4, opt) : new T.WebGLRenderTarget(4, 4, opt);
      this.rtBright = new T.WebGLRenderTarget(4, 4, opt);
      this.rtA = [0, 1, 2].map(() => new T.WebGLRenderTarget(4, 4, opt));
      this.rtB = [0, 1, 2].map(() => new T.WebGLRenderTarget(4, 4, opt));
      this.fsScene = new T.Scene();
      this.fsCam = new T.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      this.fsQuad = new T.Mesh(new T.PlaneGeometry(2, 2), null);
      this.fsScene.add(this.fsQuad);
      this.matBright = fsMat(`uniform sampler2D src; uniform float thr; varying vec2 vUv;
        void main(){ vec3 c=texture2D(src,vUv).rgb; float l=max(c.r,max(c.g,c.b));
          gl_FragColor=vec4(c*smoothstep(thr*0.5,thr*0.8,l),1.0); }`, { src: { value: null }, thr: { value: 2 } });
      this.matBlur = fsMat(`uniform sampler2D src; uniform vec2 dir; varying vec2 vUv;
        void main(){ vec3 s=texture2D(src,vUv).rgb*0.227;
          s+=texture2D(src,vUv+dir*1.384).rgb*0.316; s+=texture2D(src,vUv-dir*1.384).rgb*0.316;
          s+=texture2D(src,vUv+dir*3.230).rgb*0.070; s+=texture2D(src,vUv-dir*3.230).rgb*0.070;
          gl_FragColor=vec4(s,1.0); }`, { src: { value: null }, dir: { value: new T.Vector2() } });
      this.matComp = fsMat(`uniform sampler2D src; uniform sampler2D b0; uniform sampler2D b1; uniform sampler2D b2;
        uniform float bloom; uniform float ccB; uniform float ccC; uniform float ccS; uniform vec3 ccT; uniform float grey;
        varying vec2 vUv;
        void main(){
          vec3 c=texture2D(src,vUv).rgb + bloom*(texture2D(b0,vUv).rgb*0.5+texture2D(b1,vUv).rgb*0.35+texture2D(b2,vUv).rgb*0.25);
          c = c + ccB;
          c = (c-0.5)*(1.0+ccC)+0.5;
          float l = dot(c, vec3(0.299,0.587,0.114));
          c = mix(vec3(l), c, 1.0+ccS);
          c *= ccT;
          if (grey > 0.5) c = vec3(dot(c, vec3(0.299,0.587,0.114)));
          gl_FragColor=vec4(clamp(c,0.0,1.0),1.0); }`,
      { src: { value: null }, b0: { value: null }, b1: { value: null }, b2: { value: null }, bloom: { value: 1 },
        ccB: { value: 0 }, ccC: { value: 0 }, ccS: { value: 0 }, ccT: { value: new T.Vector3(1, 1, 1) }, grey: { value: 0 } });
    }
    resize() {
      const w = this.canvas.clientWidth || this.canvas.width || 960, h = this.canvas.clientHeight || this.canvas.height || 540;
      this.setSize(w, h);
    }
    setSize(w, h) {
      this.gl.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      const pr = this.gl.getPixelRatio();
      const W = Math.floor(w * pr), H = Math.floor(h * pr);
      this.rtScene.setSize(W, H);
      this.rtBright.setSize(W >> 1, H >> 1);
      for (let i = 0; i < 3; i++) { this.rtA[i].setSize(W >> (i + 1), H >> (i + 1)); this.rtB[i].setSize(W >> (i + 1), H >> (i + 1)); }
    }
    fs(mat, target) { this.fsQuad.material = mat; this.gl.setRenderTarget(target); this.gl.render(this.fsScene, this.fsCam); }
    // -------------------------------------------------- camera
    setCamera(c) {
      if (!c) return;
      if (c.pos && c.at) {
        const d = V.sub(c.pos, c.at);
        this.cam.at = c.at.slice();
        this.cam.dist = V.len(d);
        this.cam.yaw = Math.atan2(d[0], d[2]);
        this.cam.pitch = Math.asin(d[1] / this.cam.dist);
      }
      if (c.fov) { this.camera.fov = c.fov; this.camera.updateProjectionMatrix(); }
    }
    applyCamera(shake) {
      const c = this.cam;
      const cp = Math.cos(c.pitch);
      const pos = [c.at[0] + Math.sin(c.yaw) * cp * c.dist, c.at[1] + Math.sin(c.pitch) * c.dist, c.at[2] + Math.cos(c.yaw) * cp * c.dist];
      const sh = shake || [0, 0, 0];
      this.camera.position.set(pos[0] + sh[0], pos[1] + sh[1], pos[2] + sh[2]);
      this.camera.lookAt(c.at[0] + sh[0], c.at[1] + sh[1], c.at[2] + sh[2]);
      if (this.camRoll) this.camera.rotateZ(this.camRoll * Math.PI / 180);
      this.camera.updateMatrixWorld();
      const e = this.camera.matrixWorld.elements;
      this.camRight = [e[0], e[1], e[2]];
      this.camUp = [e[4], e[5], e[6]];
      this.camFwd = [-e[8], -e[9], -e[10]];
      this.camPos = [this.camera.position.x, this.camera.position.y, this.camera.position.z];
    }
    // -------------------------------------------------- per-frame sync
    obj(it, make) {
      let o = this.objs.get(it);
      if (!o) { o = make(); this.objs.set(it, o); if (o.mesh) this.scene.add(o.mesh); if (o.light) this.scene.add(o.light); }
      return o;
    }
    clearObjects() {
      for (const o of this.objs.values()) {
        if (o.mesh) { this.scene.remove(o.mesh); o.mesh.geometry && o.mesh.geometry.dispose(); }
        if (o.light) this.scene.remove(o.light);
        if (o.extra) for (const m of o.extra) this.scene.remove(m);
      }
      this.objs.clear();
    }
    draw(world) {
      this.world = world;
      if (world.cam && !this.view.freeCam) {
        // the effect's own (cinematic) camera drives the view
        this.setCamera({ pos: world.cam.pos, at: world.cam.at });
        this.camRoll = world.cam.roll || 0;
        if (world.cam.fov && Math.abs(this.camera.fov - world.cam.fov) > 0.01) { this.camera.fov = world.cam.fov; this.camera.updateProjectionMatrix(); }
      }
      // FOV punch rides on top of whatever fov the camera has (restored before the next frame's sync)
      const fd = world.fovOffset ? world.fovOffset() : 0;
      if (this._fovPunch) { this.camera.fov -= this._fovPunch; this._fovPunch = 0; }
      if (fd) { this.camera.fov += fd; this._fovPunch = fd; }
      this.camera.updateProjectionMatrix();
      this.applyCamera(world.shakeOffset());
      this.syncRig(world);
      let cc ={ Brightness: 0, Contrast: 0, Saturation: 0, TintColor: [1, 1, 1] };
      let bloom = { Intensity: 1, Size: 24, Threshold: 2 };
      const seen = new Set();
      for (const it of world.all) {
        seen.add(it);
        const c = it.ClassName;
        if (c === "Part" || c === "MeshPart") this.syncPart(it);
        else if (c === "ParticleEmitter") this.syncEmitter(it);
        else if (c === "Beam") this.syncBeam(it);
        else if (c === "Trail") this.syncTrail(it);
        else if (c === "PointLight" || c === "SpotLight") this.syncLight(it);
        else if (c === "Highlight") this.syncHighlight(it);
        else if (c === "ColorCorrectionEffect" && it.p.Enabled && !it.hidden) {
          cc.Brightness += it.p.Brightness; cc.Contrast += it.p.Contrast; cc.Saturation += it.p.Saturation;
          cc.TintColor = cc.TintColor.map((v, i) => v * it.p.TintColor[i]);
        } else if (c === "BloomEffect" && it.p.Enabled) bloom = it.p;
      }
      // drop scene objects whose instance no longer exists (a reset/seek
      // rebuilds the instance tree; stale meshes must not linger)
      for (const [it, o] of this.objs) {
        if (seen.has(it)) continue;
        if (o.mesh) { this.scene.remove(o.mesh); }
        if (o.light) this.scene.remove(o.light);
        if (o.extra) for (const m of o.extra) this.scene.remove(m);
        this.objs.delete(it);
      }
      // render
      const u = this.matComp.uniforms;
      u.ccB.value = cc.Brightness; u.ccC.value = cc.Contrast; u.ccS.value = Math.max(-1, cc.Saturation);   // two greyscale grades must not invert chroma
      u.ccT.value.set(cc.TintColor[0], cc.TintColor[1], cc.TintColor[2]);
      u.grey.value = this.view.greyscale ? 1 : 0;
      this.gl.setRenderTarget(this.rtScene);
      this.gl.render(this.scene, this.camera);
      const src = this.rtScene.texture;
      if (this.view.bloom && bloom.Intensity > 0 && !(world.bloomSuppressed && world.bloomSuppressed())) {
        this.matBright.uniforms.src.value = src;
        this.matBright.uniforms.thr.value = bloom.Threshold;
        this.fs(this.matBright, this.rtBright);
        let prev = this.rtBright.texture;
        const spread = Math.max(0.2, bloom.Size / 24);
        for (let i = 0; i < 3; i++) {
          const w = this.rtA[i].width, h = this.rtA[i].height;
          this.matBlur.uniforms.src.value = prev; this.matBlur.uniforms.dir.value.set(spread / w, 0); this.fs(this.matBlur, this.rtA[i]);
          this.matBlur.uniforms.src.value = this.rtA[i].texture; this.matBlur.uniforms.dir.value.set(0, spread / h); this.fs(this.matBlur, this.rtB[i]);
          prev = this.rtB[i].texture;
        }
        u.b0.value = this.rtB[0].texture; u.b1.value = this.rtB[1].texture; u.b2.value = this.rtB[2].texture;
        u.bloom.value = bloom.Intensity * 0.9;
      } else u.bloom.value = 0;
      u.src.value = src;
      this.fs(this.matComp, null);
      this.drawOverlays(world);
    }
    // screen overlays (Studio: ScreenGui): focus lines re-rolled at 30 Hz, letterbox bars
    drawOverlays(world) {
      const list = world.activeOverlays ? world.activeOverlays() : [];
      if (!this.ovScene) {
        this.ovScene = new T.Scene();
        this.ovCam = new T.OrthographicCamera(-1, 1, 1, -1, -1, 1);
        this.ovPool = [];
      }
      for (const m of this.ovPool) m.visible = false;
      if (!list.length) return;
      const W = this.gl.domElement.width, H = this.gl.domElement.height, asp = W / H;
      this.ovCam.left = -asp; this.ovCam.right = asp; this.ovCam.updateProjectionMatrix();
      let n = 0;
      const quad = () => { let m = this.ovPool[n++]; if (!m) { m = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false })); this.ovPool.push(m); this.ovScene.add(m); } m.visible = true; m.rotation.set(0, 0, 0); return m; };
      const rnd = (seed, k) => { const x = Math.sin(seed * 127.1 + k * 311.7) * 43758.5453; return x - Math.floor(x); };
      for (const o of list) {
        if (o.kind === "bars") {
          const inF = Math.min(1, o.age / Math.max(o.fin, 1e-3)), outF = Math.min(1, (o.time - o.age) / Math.max(o.fout, 1e-3));
          const qo = 1 - Math.pow(1 - inF, 4), qi = outF * outF;
          const hgt = 2 * o.size * Math.min(qo, qi);
          for (const sgn of [1, -1]) { const m = quad(); m.material.map = null; m.material.color.setRGB(...o.color); m.material.opacity = 1 - o.transparency; m.material.blending = T.NormalBlending; m.material.needsUpdate = true; m.scale.set(2 * asp + 0.01, Math.max(hgt, 1e-4), 1); m.position.set(0, sgn * (1 - hgt / 2), 0); }
          continue;
        }
        const m = quad();
        m.material.map = this.getTex(o.image); m.material.needsUpdate = true; m.material.blending = T.NormalBlending;
        m.material.color.setRGB(...o.color); m.material.opacity = (1 - o.transparency) * o.fade;
        const D = Math.sqrt(4 * asp * asp + 4) * o.scale * (1 + (rnd(o.seed, o.frame + 7) - 0.5) * 0.08);
        m.scale.set(D, D, 1); m.rotation.z = o.spin ? rnd(o.seed, o.frame) * Math.PI * 2 : -(o.rot || 0) * Math.PI / 180;
      }
      this.gl.autoClear = false;
      this.gl.render(this.ovScene, this.ovCam);
      this.gl.autoClear = true;
    }
    // -------------------------------------------------- animated rig + afterimages
    syncRig(world) {
      const cfs = world.rigCF;
      const sc = (c, nm) => { if (c && c._tube && c._tube[nm]) return c._tube[nm]; const k = (c && c._scale) || 1; const s = c && c._stretch && c._stretch[nm]; return s ? [s[1] * k, s[0] * k, s[1] * k] : [k, k, k]; };
      // fade (0 shown .. 1 gone): the caster's own material, one material per actor
      const fadeMat = (mat, f) => { const o = 1 - Math.max(0, Math.min(1, f || 0)); if (mat.opacity !== o) { mat.transparent = o < 1; mat.opacity = o; mat.depthWrite = o > 0.99; mat.needsUpdate = true; } return o > 0.004; };
      const isTube = (nm) => nm.endsWith("Tube");
      for (const nm in this.rigMesh) {
        const m = this.rigMesh[nm];
        if (isTube(nm)) { m.visible = !!(cfs && cfs[nm]); if (m.visible) setMatrix(m, cfs[nm], sc(cfs, nm)); continue; }
        if (cfs && cfs[nm]) { setMatrix(m, cfs[nm], sc(cfs, nm)); this.rigOn = true; m.visible = fadeMat(m.material, cfs._fade); }
        else if (this.rigOn) { m.matrixAutoUpdate = true; m.updateMatrix(); }
      }
      if (!cfs) this.rigOn = false;
      // extra rigs (clones): the same dummy geometry and material as the caster
      this.actorPool = this.actorPool || {};
      const acf = world.actorCF || {};
      const live = new Set((world.actors || []).map((a) => a.name));
      for (const nm in this.actorPool) if (!live.has(nm) || this.actorPool[nm].userData.world !== world) { this.scene.remove(this.actorPool[nm]); delete this.actorPool[nm]; }   // a previous effect's actors
      for (const a of world.actors || []) {
        let grp = this.actorPool[a.name];
        if (!grp) {
          grp = new T.Group();
          const amat = this.rigMesh.Torso.material.clone();
          for (const nm in this.rigMesh) { const m = new T.Mesh(this.rigMesh[nm].geometry, amat); m.name = nm; grp.add(m); }
          grp.userData.mat = amat;
          if (a.col) amat.color.setRGB(a.col[0], a.col[1], a.col[2]);   // e.g. a copy of the target ("@target") in the stand-in's colour
          this.scene.add(grp);
          grp.userData.world = world;
          this.actorPool[a.name] = grp;
        }
        const c = acf[a.name];
        grp.visible = !!c && this.dummy.visible;
        const on = c ? fadeMat(grp.userData.mat, c._fade) : false;
        if (c) for (const m of grp.children) { m.visible = on && !!c[m.name]; if (c[m.name]) setMatrix(m, c[m.name], sc(c, m.name)); }
      }
      const gs = world.ghosts || [];
      while (this.ghostPool.length < gs.length) {
        const grp = new T.Group();
        const mat = new T.MeshBasicMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending });
        for (const nm in this.rigMesh) { const m = new T.Mesh(this.rigMesh[nm].geometry, mat); m.name = nm; grp.add(m); }
        grp.userData.mat = mat;
        this.scene.add(grp);
        this.ghostPool.push(grp);
      }
      this.ghostPool.forEach((grp, i) => {
        const g = gs[i];
        grp.visible = !!g && this.dummy.visible;
        if (!g) return;
        // keep = the real look (grey dummy material, normal blend), else an additive coloured silhouette
        if (!grp.userData.keepMat) grp.userData.keepMat = new T.MeshLambertMaterial({ color: 0xa3a2a5, transparent: true, depthWrite: false });
        const mat = g.keep ? grp.userData.keepMat : grp.userData.mat;
        for (const m of grp.children) { m.material = mat; m.visible = !!g.cfs[m.name] && (!g.parts || g.parts.includes(m.name) || (m.name.endsWith("Tube") && g.parts.includes(m.name.replace("Tube", "Arm")))); }
        const a = Math.max(0, 1 - (world.time - g.t0) / g.life);
        if (!g.keep) grp.userData.mat.color.setRGB(g.color[0], g.color[1], g.color[2]);
        mat.opacity = a * (1 - g.tr0);
        for (const m of grp.children) if (g.cfs[m.name]) setMatrix(m, g.cfs[m.name], sc(g.cfs, m.name));
      });
    }
    lightFactor(p) {
      const li = Math.max(0, Math.min(1, p.LightInfluence || 0));
      return (1 - li) * (p.Brightness == null ? 1 : p.Brightness) + li * 0.85;
    }
    // -------------------------------------------------- parts
    syncPart(it) {
      const p = it.p;
      const o = this.obj(it, () => ({ mesh: new T.Mesh(new T.BufferGeometry(), new T.MeshLambertMaterial()), key: "" }));
      const neon = p.Material === "Neon";
      const ff = p.Material === "ForceField";
      const sa = it.children.find((c) => c.ClassName === "SurfaceAppearance");
      const key = [it.ClassName, p.Shape, p.MeshId, p.Material, p.TextureID, p.DoubleSided, sa ? sa.p.ColorMap + sa.p.EmissiveMask : ""].join("|");
      if (o.key !== key || (it.ClassName === "MeshPart" && o.mesh.geometry.attributes.position === undefined)) {
        let geo;
        if (it.ClassName === "MeshPart") geo = p.MeshId ? this.getMesh(p.MeshId) : null;
        else if (p.Shape === "Ball") geo = new T.SphereGeometry(0.5, 32, 16);
        else if (p.Shape === "Cylinder") { geo = new T.CylinderGeometry(0.5, 0.5, 1, 32); geo.rotateZ(Math.PI / 2); }
        else geo = new T.BoxGeometry(1, 1, 1);
        if (geo) {
          o.mesh.geometry = geo;
          const map = p.TextureID ? this.getTex(p.TextureID) : null;
          const side = p.DoubleSided || ff ? T.DoubleSide : T.FrontSide;
          if (sa) {
            const cm = sa.p.ColorMap ? this.getTex(sa.p.ColorMap) : null;
            const em = sa.p.EmissiveMask ? this.getTex(sa.p.EmissiveMask) : null;
            o.mesh.material = new T.ShaderMaterial({
              vertexShader: SA_VERT, fragmentShader: SA_FRAG, side, transparent: true,
              uniforms: { map: { value: cm }, hasMap: { value: cm ? 1 : 0 }, emask: { value: em }, hasMask: { value: em ? 1 : 0 },
                tint: { value: new T.Color(1, 1, 1) }, partColor: { value: new T.Color(1, 1, 1) }, eTint: { value: new T.Color(1, 1, 1) },
                eStr: { value: 1 }, opacity: { value: 1 }, alphaMode: { value: 0 }, ambient: { value: 1 } },
            });
            o.sa = true;
          } else if (neon) o.mesh.material = new T.MeshBasicMaterial({ map, side });
          else if (ff) o.mesh.material = new T.MeshBasicMaterial({ map, side, blending: T.AdditiveBlending, transparent: true, depthWrite: false });
          else o.mesh.material = new T.MeshLambertMaterial({ map, side });
          o.key = key;
        }
      }
      const m = o.mesh;
      const tr = it.hidden ? 1 : p.Transparency;
      m.visible = tr < 0.999 && !!m.geometry.attributes.position;
      if (!m.visible) return;
      const col = p.Color;
      if (o.sa && sa) {
        const u = m.material.uniforms;
        u.tint.value.setRGB(...sa.p.Color);
        u.partColor.value.setRGB(...col);
        u.eTint.value.setRGB(...sa.p.EmissiveTint);
        u.eStr.value = sa.p.EmissiveStrength;
        if (u.ambient) u.ambient.value = this.view.sky === "night" ? 0.42 : 1.0;
        u.alphaMode.value = sa.p.AlphaMode === "Transparency" ? 1 : 0;
        // AlphaMode Transparency: Transparency 0 = hard (opaque pixels opaque);
        // >= 0.02 switches to soft blending (docs). Both modelled as opacity.
        u.opacity.value = 1 - tr;
        m.material.depthWrite = false;
        m.renderOrder = 8000;
        setMatrix(m, p.CFrame, p.Size);
        return;
      }
      // Roblox Neon is self-lit and blooms hard (Studio round 3: Neon rings edge-on read as a bright band)
      const k = neon ? 2.6 : 1;
      m.material.color.setRGB(col[0] * k, col[1] * k, col[2] * k);
      m.material.transparent = tr > 0 || ff;
      m.material.opacity = ff ? 1 - tr : 1 - tr;
      m.material.depthWrite = tr <= 0 && !ff;
      setMatrix(m, p.CFrame, p.Size);
    }
    // -------------------------------------------------- particles
    syncEmitter(em) {
      const p = em.p;
      const o = this.obj(em, () => makeDyn(this));
      const map = p.Texture ? this.getTex(p.Texture) : null;
      const mat = o.mesh.material;
      mat.uniforms.map.value = map;
      mat.uniforms.hasMap.value = map ? 1 : 0;
      mat.uniforms.le.value = Math.max(0, Math.min(1, p.LightEmission));
      const parts = em.hidden ? [] : em.parts;
      const n = parts.length;
      ensure(o, n);
      const cp = this.camPos, cf = this.camFwd;
      const order = parts.map((q, i) => [i, V.dot(V.sub(q.pos, cp), cf) - p.ZOffset]);
      order.sort((a, b) => b[1] - a[1]);
      const [cols, rows] = flipGrid(p);
      const lf = this.lightFactor(p);
      let w = 0, depthSum = 0;
      for (const [i] of order) {
        const q = parts[i];
        const t = Math.min(1, q.age / q.life);
        const tr = nsAt(p.Transparency, t, q.envT);
        if (tr >= 0.999) continue;
        const size = Math.max(0, nsAt(p.Size, t, q.envS));
        if (size <= 0) continue;
        const sq = nsAt(p.Squash, t);
        // Roblox draws a particle 2 x Size wide (measured in Studio 2026-10-27: Size 4 = 8 studs),
        // so the half-width IS Size. Squash > 0 narrows and stretches (docs); exponent mapping CALIBRATE.
        let hw = size * Math.pow(2, -sq), hh = size * Math.pow(2, sq);
        let pos = q.pos;
        if (p.ZOffset) {
          const toC = V.sub(cp, pos), d = V.len(toC);
          const z = Math.min(p.ZOffset, d - 0.2);
          pos = V.add(pos, V.mul(V.norm(toC), z));
          const s = (d - z) / d; hw *= s; hh *= s;
        }
        let ax, ay;
        const vdir = V.len(q.vel) > 1e-5 ? V.norm(q.vel) : q.dir;
        switch (p.Orientation) {
          case "FacingCameraWorldUp": ay = [0, 1, 0]; ax = V.norm(V.cross(ay, V.sub(cp, pos))); break;
          case "VelocityParallel": ay = vdir; ax = V.norm(V.cross(ay, V.sub(cp, pos))); break;
          case "VelocityPerpendicular": {
            const ref = Math.abs(vdir[1]) > 0.95 ? [0, 0, 1] : [0, 1, 0];
            ax = V.norm(V.cross(ref, vdir)); ay = V.cross(vdir, ax); break;
          }
          default: ax = this.camRight; ay = this.camUp;
        }
        const r = (-q.rot * Math.PI) / 180; // positive Rotation = clockwise
        const c = Math.cos(r), s = Math.sin(r);
        const rx = V.add(V.mul(ax, c), V.mul(ay, s)), ry = V.sub(V.mul(ay, c), V.mul(ax, s));
        const X = V.mul(rx, hw), Y = V.mul(ry, hh);
        const P = o.pos;
        const corners = [V.sub(V.sub(pos, X), Y), V.sub(V.add(pos, X), Y), V.add(V.add(pos, X), Y), V.add(V.sub(pos, X), Y)];
        for (let k = 0; k < 4; k++) { P[(w * 4 + k) * 3] = corners[k][0]; P[(w * 4 + k) * 3 + 1] = corners[k][1]; P[(w * 4 + k) * 3 + 2] = corners[k][2]; }
        const [fa, fb, bl] = flipFrame(p, q);
        writeUV(o.uvA, w, fa, cols, rows);
        writeUV(o.uvB, w, fb, cols, rows);
        const col = csAt(p.Color, t);
        for (let k = 0; k < 4; k++) {
          const j = (w * 4 + k) * 4;
          o.col[j] = col[0] * lf; o.col[j + 1] = col[1] * lf; o.col[j + 2] = col[2] * lf; o.col[j + 3] = 1 - tr;
          o.bl[w * 4 + k] = bl;
        }
        depthSum += V.dot(V.sub(pos, cp), cf);
        w++;
      }
      commit(o, w);
      o.mesh.renderOrder = w ? 10000 - Math.round((depthSum / w) * 10) : 0;
    }
    // -------------------------------------------------- beams
    syncBeam(b) {
      const p = b.p;
      const o = this.obj(b, () => makeDyn(this));
      const map = p.Texture ? this.getTex(p.Texture) : null;
      const mat = o.mesh.material;
      mat.uniforms.map.value = map; mat.uniforms.hasMap.value = map ? 1 : 0;
      mat.uniforms.le.value = Math.max(0, Math.min(1, p.LightEmission));
      if (!p.Enabled || b.hidden || !p.Attachment0 || !p.Attachment1) { commit(o, 0); return; }
      const w = this.world;
      const c0 = w.worldCF(p.Attachment0), c1 = w.worldCF(p.Attachment1);
      const P0 = c0.p, P3 = c1.p;
      const P1 = V.add(P0, V.mul(CF.right(c0), p.CurveSize0));
      const P2 = V.sub(P3, V.mul(CF.right(c1), p.CurveSize1));
      const segs = Math.max(1, Math.min(1000, p.Segments | 0));
      const pts = [];
      for (let i = 0; i <= segs; i++) {
        const t = i / segs, u = 1 - t;
        pts.push(V.add(V.add(V.mul(P0, u * u * u), V.mul(P1, 3 * u * u * t)), V.add(V.mul(P2, 3 * u * t * t), V.mul(P3, t * t * t))));
      }
      let L = 0; const acc = [0];
      for (let i = 1; i < pts.length; i++) { L += V.len(V.sub(pts[i], pts[i - 1])); acc.push(L); }
      ensure(o, segs);
      const lf = this.lightFactor(p);
      const cp = this.camPos;
      const scroll = (w.time || 0) * p.TextureSpeed;
      let n = 0;
      const vert = (i) => {
        const t = i / segs;
        const tan = V.norm(V.sub(pts[Math.min(segs, i + 1)], pts[Math.max(0, i - 1)]));
        let wd;
        if (p.FaceCamera) wd = V.norm(V.cross(tan, V.sub(cp, pts[i])));
        else {
          // width lies along the attachments' Y axes (measured in Studio,
          // 2026-10), made perpendicular to the curve
          const y = V.lerp(CF.up(c0), CF.up(c1), t);
          wd = V.norm(V.sub(y, V.mul(tan, V.dot(y, tan))));
        }
        const width = p.Width0 + (p.Width1 - p.Width0) * t;
        let c = pts[i];
        if (p.ZOffset) c = V.add(c, V.mul(V.norm(V.sub(cp, c)), p.ZOffset));
        let u;
        if (p.TextureMode === "Stretch") u = t * p.TextureLength;
        else u = acc[i] / Math.max(1e-3, p.TextureLength);
        u -= scroll;
        return { a: V.add(c, V.mul(wd, width / 2)), b: V.sub(c, V.mul(wd, width / 2)), u, col: csAt(p.Color, t), tr: nsAt(p.Transparency, t) };
      };
      let prev = vert(0);
      for (let i = 1; i <= segs; i++) {
        const cur = vert(i);
        quad(o, n++, prev, cur, lf);
        prev = cur;
      }
      commit(o, n);
      o.mesh.renderOrder = 10000 - Math.round(V.dot(V.sub(V.lerp(P0, P3, 0.5), cp), this.camFwd) * 10) + Math.round(p.ZOffset * 100);
    }
    // -------------------------------------------------- trails
    syncTrail(tr) {
      const p = tr.p;
      const o = this.obj(tr, () => makeDyn(this));
      const map = p.Texture ? this.getTex(p.Texture) : null;
      const mat = o.mesh.material;
      mat.uniforms.map.value = map; mat.uniforms.hasMap.value = map ? 1 : 0;
      mat.uniforms.le.value = Math.max(0, Math.min(1, p.LightEmission));
      const pts = tr.pts.slice();
      if (tr.head && p.Enabled) pts.push(tr.head);
      if (pts.length < 2 || tr.hidden) { commit(o, 0); return; }
      ensure(o, pts.length);
      const lf = this.lightFactor(p);
      const cp = this.camPos;
      const total = pts.length - 1;
      const headOdo = pts[pts.length - 1].odo;
      const vert = (q, idx) => {
        const t = Math.min(1, q.age / p.Lifetime);
        const ws = nsAt(p.WidthScale, t);
        let a = q.a, b = q.b;
        if (p.FaceCamera) {
          const half = V.len(V.sub(a, b)) / 2;
          const nxt = pts[Math.min(total, idx + 1)].mid, prv = pts[Math.max(0, idx - 1)].mid;
          const d = V.norm(V.sub(nxt, prv));
          const wd = V.norm(V.cross(d, V.sub(cp, q.mid)));
          a = V.add(q.mid, V.mul(wd, half)); b = V.sub(q.mid, V.mul(wd, half));
        }
        a = V.add(q.mid, V.mul(V.sub(a, q.mid), ws));
        b = V.add(q.mid, V.mul(V.sub(b, q.mid), ws));
        let u;
        if (p.TextureMode === "Stretch") u = (1 - idx / total) * p.TextureLength;
        else if (p.TextureMode === "Static") u = q.odo / Math.max(1e-3, p.TextureLength);
        else u = (headOdo - q.odo) / Math.max(1e-3, p.TextureLength);
        return { a, b, u, col: csAt(p.Color, t), tr: nsAt(p.Transparency, t) };
      };
      let n = 0, prev = vert(pts[0], 0);
      for (let i = 1; i < pts.length; i++) { const cur = vert(pts[i], i); quad(o, n++, prev, cur, lf); prev = cur; }
      commit(o, n);
      o.mesh.renderOrder = 9000;
    }
    // -------------------------------------------------- lights, highlight
    syncLight(it) {
      const p = it.p;
      const o = this.obj(it, () => ({ light: it.ClassName === "SpotLight" ? new T.SpotLight() : new T.PointLight() }));
      const L = o.light;
      const par = it.parent;
      const cf = this.world.worldCF(par);
      L.position.set(cf.p[0], cf.p[1], cf.p[2]);
      L.color.setRGB(p.Color[0], p.Color[1], p.Color[2]);
      L.intensity = p.Enabled && !it.hidden ? p.Brightness * 1.2 : 0;
      L.distance = p.Range;
      L.decay = 1;
      if (it.ClassName === "SpotLight") {
        L.angle = Math.min(Math.PI / 2, (p.Angle * Math.PI) / 360);
        const f = { Front: [0, 0, -1], Back: [0, 0, 1], Top: [0, 1, 0], Bottom: [0, -1, 0], Right: [1, 0, 0], Left: [-1, 0, 0] }[p.Face] || [0, 0, -1];
        const d = CF.vec(cf, f);
        L.target.position.set(cf.p[0] + d[0], cf.p[1] + d[1], cf.p[2] + d[2]);
        L.target.updateMatrixWorld();
      }
    }
    syncHighlight(it) {
      const p = it.p;
      const o = this.obj(it, () => ({ extra: [] }));
      const raw = it.spec.props && it.spec.props.Adornee;
      const wantDummy = raw === "Dummy" || (raw && raw.Ref === "Dummy");
      const foe = typeof raw === "string" && raw !== "Dummy" ? raw : (raw && raw.Ref && raw.Ref !== "Dummy" ? raw.Ref : null);
      o.foe = foe;
      if (!o.built) {
        let src = wantDummy ? this.dummy.children : [];
        if (foe) { src = []; for (const [it2, o2] of this.objs) if (it2 !== it && it2.Name && it2.Name.startsWith(foe) && o2.mesh && (it2.ClassName === "Part" || it2.ClassName === "MeshPart")) src.push(o2.mesh); }
        if (foe && !src.length) return;   // the target's parts are synced later this frame
        o.built = true;
        for (const m of src) {
          const fill = new T.Mesh(m.geometry, new T.MeshBasicMaterial({ transparent: true, depthWrite: false }));
          const line = new T.Mesh(m.geometry, new T.MeshBasicMaterial({ transparent: true, depthWrite: false, side: T.BackSide }));
          fill.userData.src = m; line.userData.src = m; line.userData.outline = true;
          o.extra.push(fill, line);
          this.scene.add(fill); this.scene.add(line);
        }
      }
      const on = p.Enabled && !it.hidden;
      for (const m of o.extra) {
        const s = m.userData.src;
        s.updateMatrixWorld();
        m.matrixAutoUpdate = false;
        m.matrix.copy(s.matrixWorld);
        if (m.userData.outline) m.matrix.multiply(new T.Matrix4().makeScale(1.06, 1.06, 1.06));
        m.parent !== this.scene && this.scene.add(m);
        const top = p.DepthMode === "AlwaysOnTop";
        m.material.depthTest = !top;
        m.renderOrder = 20000;
        m.visible = on && (o.foe ? s.visible : this.dummy.visible);
        if (m.userData.outline) { m.material.color.setRGB(...p.OutlineColor); m.material.opacity = 1 - p.OutlineTransparency; }
        else { m.material.color.setRGB(...p.FillColor); m.material.opacity = 1 - p.FillTransparency; }
      }
    }
    // -------------------------------------------------- measurement
    // Same statistics the video teardown measured (ffmpeg signalstats-like):
    // mean luma 0-255, saturation (chroma magnitude), fraction of pixels > 250.
    metrics() {
      const gl = this.gl.getContext();
      const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
      const px = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
      let ys = 0, ss = 0, hot = 0, n = 0;
      for (let i = 0; i < px.length; i += 16) {
        const r = px[i], g = px[i + 1], b = px[i + 2];
        const y = 0.299 * r + 0.587 * g + 0.114 * b;
        const u = -0.169 * r - 0.331 * g + 0.5 * b, v = 0.5 * r - 0.419 * g - 0.081 * b;
        ys += y; ss += Math.hypot(u, v); if (y > 250) hot++; n++;
      }
      return { luma: ys / n, sat: ss / n, hot: hot / n };
    }
  }

  // ------------------------------------------------------------ helpers
  function setMatrix(m, cf, size) {
    const R = cf.R;
    m.matrixAutoUpdate = false;
    m.matrix.set(
      R[0] * size[0], R[1] * size[1], R[2] * size[2], cf.p[0],
      R[3] * size[0], R[4] * size[1], R[5] * size[2], cf.p[1],
      R[6] * size[0], R[7] * size[1], R[8] * size[2], cf.p[2],
      0, 0, 0, 1);
    m.matrixWorldNeedsUpdate = true;
  }
  function makeDyn() {
    const geo = new T.BufferGeometry();
    const mat = new T.ShaderMaterial({
      uniforms: { map: { value: null }, le: { value: 0 }, hasMap: { value: 0 } },
      vertexShader: PVERT, fragmentShader: PFRAG, transparent: true, depthWrite: false, depthTest: true, side: T.DoubleSide,
      blending: T.CustomBlending, blendSrc: T.OneFactor, blendDst: T.OneMinusSrcAlphaFactor, blendEquation: T.AddEquation,
      blendSrcAlpha: T.OneFactor, blendDstAlpha: T.OneMinusSrcAlphaFactor,
    });
    const mesh = new T.Mesh(geo, mat);
    mesh.frustumCulled = false;
    return { mesh, cap: 0 };
  }
  function ensure(o, n) {
    if (n <= o.cap) return;
    const cap = Math.max(16, Math.ceil(n * 1.5));
    o.cap = cap;
    o.pos = new Float32Array(cap * 12);
    o.uvA = new Float32Array(cap * 8);
    o.uvB = new Float32Array(cap * 8);
    o.col = new Float32Array(cap * 16);
    o.bl = new Float32Array(cap * 4);
    const idx = new Uint32Array(cap * 6);
    for (let i = 0; i < cap; i++) idx.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3], i * 6);
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.BufferAttribute(o.pos, 3));
    g.setAttribute("uvA", new T.BufferAttribute(o.uvA, 2));
    g.setAttribute("uvB", new T.BufferAttribute(o.uvB, 2));
    g.setAttribute("rgba", new T.BufferAttribute(o.col, 4));
    g.setAttribute("blend", new T.BufferAttribute(o.bl, 1));
    g.setIndex(new T.BufferAttribute(idx, 1));
    o.mesh.geometry.dispose();
    o.mesh.geometry = g;
  }
  function commit(o, n) {
    const g = o.mesh.geometry;
    if (!g.index) { o.mesh.visible = false; return; }
    for (const k of ["position", "uvA", "uvB", "rgba", "blend"]) g.attributes[k].needsUpdate = true;
    g.setDrawRange(0, n * 6);
    o.mesh.visible = n > 0;
  }
  function writeUV(arr, w, f, cols, rows) {
    const cx = f % cols, cy = Math.floor(f / cols);
    const u0 = cx / cols, u1 = (cx + 1) / cols;
    const v1 = 1 - cy / rows, v0 = 1 - (cy + 1) / rows; // row 0 = top of the image
    arr.set([u0, v0, u1, v0, u1, v1, u0, v1], w * 8);
  }
  // A strip quad between two cross-sections (beams and trails); v=1 on the
  // "a" side, so a texture's TOP row runs along +width. CALIBRATE side.
  function quad(o, n, A, B, lf) {
    const P = o.pos, j = n * 12;
    const pts = [A.b, B.b, B.a, A.a];
    for (let k = 0; k < 4; k++) { P[j + k * 3] = pts[k][0]; P[j + k * 3 + 1] = pts[k][1]; P[j + k * 3 + 2] = pts[k][2]; }
    o.uvA.set([A.u, 0, B.u, 0, B.u, 1, A.u, 1], n * 8);
    o.uvB.set([A.u, 0, B.u, 0, B.u, 1, A.u, 1], n * 8);
    const cs = [A, B, B, A];
    for (let k = 0; k < 4; k++) {
      const c = cs[k].col, q = (n * 4 + k) * 4;
      o.col[q] = c[0] * lf; o.col[q + 1] = c[1] * lf; o.col[q + 2] = c[2] * lf; o.col[q + 3] = 1 - cs[k].tr;
      o.bl[n * 4 + k] = 0;
    }
  }
  // Minimal OBJ reader (v / vt / vn / f). Like a Roblox MeshPart, the mesh is
  // normalised so its bounds become 1x1x1 and Size scales each axis.
  function parseOBJ(txt) {
    const v = [], vt = [], vn = [], P = [], U = [], N = [];
    for (const line of txt.split("\n")) {
      const s = line.trim().split(/\s+/);
      if (s[0] === "v") v.push([+s[1], +s[2], +s[3]]);
      else if (s[0] === "vt") vt.push([+s[1], +s[2]]);
      else if (s[0] === "vn") vn.push([+s[1], +s[2], +s[3]]);
      else if (s[0] === "f") {
        const f = s.slice(1).map((x) => x.split("/").map((n) => parseInt(n, 10) - 1));
        for (let i = 1; i < f.length - 1; i++) for (const k of [f[0], f[i], f[i + 1]]) {
          P.push(...v[k[0]]);
          U.push(...(k[1] >= 0 && vt[k[1]] ? vt[k[1]] : [0, 0]));
          if (k[2] >= 0 && vn[k[2]]) N.push(...vn[k[2]]);
        }
      }
    }
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < P.length; i += 3) for (let a = 0; a < 3; a++) { min[a] = Math.min(min[a], P[i + a]); max[a] = Math.max(max[a], P[i + a]); }
    for (let i = 0; i < P.length; i += 3) for (let a = 0; a < 3; a++) { const ext = max[a] - min[a] || 1; P[i + a] = (P[i + a] - (min[a] + max[a]) / 2) / ext; }
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.Float32BufferAttribute(P, 3));
    g.setAttribute("uv", new T.Float32BufferAttribute(U, 2));
    if (N.length === P.length) g.setAttribute("normal", new T.Float32BufferAttribute(N, 3));
    else g.computeVertexNormals();
    return g;
  }

  SIM.Renderer = Renderer;
  SIM.parseOBJ = parseOBJ;
})(window);
