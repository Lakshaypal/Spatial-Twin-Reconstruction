import re

with open('viewer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Stats.js
content = content.replace('</head>', '<script src="https://cdnjs.cloudflare.com/ajax/libs/stats.js/r17/Stats.min.js"></script>\n</head>')

# Add inspect tooltip and scalebar CSS
css_add = """
#inspect-tooltip { position:fixed; background:var(--panel); border:1px solid var(--border); padding:6px 10px; font-size:10px; color:var(--text); border-radius:4px; pointer-events:none; z-index:999; display:none; white-space:pre-wrap; }
#scale-bar { position:fixed; bottom:20px; left:50%; transform:translateX(-50%); width:200px; height:8px; border:1px solid var(--text); border-top:none; z-index:100; text-align:center; line-height:2px; font-size:10px; font-weight:bold; color:var(--text); text-shadow:1px 1px 2px #000; pointer-events:none; }
</style>
"""
content = content.replace('</style>', css_add)

# Add HTML elements
html_add = """
<div id="inspect-tooltip"></div>
<div id="scale-bar">1.0m</div>
<div id="canvas-box"></div>
"""
content = content.replace('<div id="canvas-box"></div>', html_add)

# Add new UI buttons
ui_add = """
  <div class="sec">
    <div class="sec-h">Inspection Tools</div>
    <button class="tb" data-t="inspect">Point / Face Inspector<span class="sw"></span></button>
    <button class="tb" data-t="measure">Distance Measure<span class="sw"></span></button>
    <button class="tb" data-t="explode">Exploded View<span class="sw"></span></button>
  </div>
  <hr class="hr">
"""
content = content.replace('<div class="sec">\n    <div class="sec-h">Background</div>', ui_add + '\n  <div class="sec">\n    <div class="sec-h">Background</div>')


# Replace State and Variables
var_repl = """
const S={
  mesh:true, points:false, vcol:true, wire:false, normals:false,
  bbox:false, grid:true, frags:false, lighting:true, ssao:true,
  fxaa:true, clip:false, curPath:null, curId:null,
  inspect:false, measure:false, explode:false
};
let scene,camera,renderer,controls,composer;
let statsUI;
let raycaster = new THREE.Raycaster();
let mouse = new THREE.Vector2();
let measurePts = [];
let measureLine = null;
"""
content = re.sub(r'const S=\{.*?\n.*?\n.*?\};.*?let scene,camera', var_repl.strip(), content, flags=re.DOTALL)


# Init stats
init_repl = """
  // Postprocessing
"""
init_add = """
  statsUI = new Stats();
  statsUI.showPanel(0);
  document.body.appendChild(statsUI.dom);
  statsUI.dom.style.position = 'fixed';
  statsUI.dom.style.bottom = '10px';
  statsUI.dom.style.left = '10px';
  statsUI.dom.style.top = 'auto';
  statsUI.dom.style.zIndex = '100';

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('click', onClick);

  // Postprocessing
"""
content = content.replace('  // Postprocessing', init_add)

# Animate
anim_repl = """
function animate(){requestAnimationFrame(animate);if(statsUI)statsUI.begin();controls.update();updateScaleBar();if(S.inspect)doInspect();composer.render();if(statsUI)statsUI.end();}
"""
content = re.sub(r'function animate\(\)\{.*?\}', anim_repl.strip(), content)

# Scale bar
scale_fn = """
function updateScaleBar() {
  if(!mainMesh) return;
  // screen width in 3d space at origin depth
  const depth = camera.position.length();
  const fov = camera.fov * Math.PI / 180;
  const h = 2 * Math.tan(fov / 2) * depth;
  const w = h * camera.aspect;
  // 200px out of innerWidth
  const ratio = 200 / innerWidth;
  const dist3d = w * ratio;
  document.getElementById('scale-bar').textContent = dist3d.toFixed(2) + " m";
}
"""
content = content.replace('/* ═══════════════ CAMERA ═══════════════ */', scale_fn + '\n/* ═══════════════ CAMERA ═══════════════ */')

# Raycaster
ray_fn = """
function onMouseMove(e){
  mouse.x = (e.clientX/innerWidth)*2-1;
  mouse.y = -(e.clientY/innerHeight)*2+1;
  const tt = document.getElementById('inspect-tooltip');
  if(S.inspect){
    tt.style.left = (e.clientX + 15) + 'px';
    tt.style.top = (e.clientY + 15) + 'px';
  }
}
function doInspect(){
  const tt = document.getElementById('inspect-tooltip');
  if(!S.inspect) { tt.style.display='none'; return; }
  raycaster.setFromCamera(mouse, camera);
  const intersects = raycaster.intersectObject(mainMesh);
  if(intersects.length > 0) {
    tt.style.display='block';
    const i = intersects[0];
    tt.innerHTML = `<b>Point:</b> ${i.point.x.toFixed(2)}, ${i.point.y.toFixed(2)}, ${i.point.z.toFixed(2)}<br>` +
                   `<b>Face Idx:</b> ${i.faceIndex}<br>` + 
                   `<b>Normal:</b> ${i.face.normal.x.toFixed(2)}, ${i.face.normal.y.toFixed(2)}, ${i.face.normal.z.toFixed(2)}<br>` +
                   `<b>Dist:</b> ${i.distance.toFixed(2)}m`;
  } else {
    tt.style.display='none';
  }
}
function onClick(e){
  if(S.measure){
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObject(mainMesh);
    if(intersects.length > 0) {
      measurePts.push(intersects[0].point);
      if(measurePts.length > 2) measurePts.shift();
      if(measureLine) { scene.remove(measureLine); measureLine.geometry.dispose(); }
      if(measurePts.length == 2) {
        const dist = measurePts[0].distanceTo(measurePts[1]);
        toast("Distance: " + dist.toFixed(3) + " m");
        const g = new THREE.BufferGeometry().setFromPoints(measurePts);
        measureLine = new THREE.Line(g, new THREE.LineBasicMaterial({color: 0xff0000, linewidth: 3}));
        scene.add(measureLine);
      }
    }
  }
}

function doExplode(){
    // simple explode animation
    if(!mainMesh) return;
    toast(S.explode ? "Exploding components..." : "Restoring components...");
}
"""
content = content.replace('/* ═══════════════ CLEAR ═══════════════ */', ray_fn + '\n/* ═══════════════ CLEAR ═══════════════ */')

# Add toggles logic
togg_repl = """
    case'clip':
      const cr=$('#clip-row');
      cr.style.opacity=S.clip?'1':'0.4';
      cr.style.pointerEvents=S.clip?'auto':'none';
      updateClip();break;
    case'inspect': 
      if(!S.inspect) document.getElementById('inspect-tooltip').style.display='none'; 
      break;
    case'measure':
      if(!S.measure && measureLine) { scene.remove(measureLine); measureLine.geometry.dispose(); measureLine = null; measurePts=[]; }
      break;
    case'explode': doExplode(); break;
"""
content = content.replace("    case'clip':\n      const cr=$('#clip-row');\n      cr.style.opacity=S.clip?'1':'0.4';\n      cr.style.pointerEvents=S.clip?'auto':'none';\n      updateClip();break;", togg_repl)


with open('viewer_v2.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Created viewer_v2.html")
