import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Audio Mixer", layout="wide")

# Remove Streamlit’s default title bar padding
st.markdown("""
    <style>
    .block-container { padding: 0 !important; margin: 0 !important; }
    </style>
""", unsafe_allow_html=True)

html_code = """
<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {
  --bg:#0f1724; --card:#111827; --muted:#9ca3af; --accent:#60a5fa; --accent2:#a855f7;
}
body {
  font-family: Inter, system-ui, sans-serif;
  color: #e6eef8;
  background: linear-gradient(180deg,#071126 0%,#081a2d 100%);
  margin:0;
  min-height:100vh;
}
.app {
  width:100%;
  max-width:1600px;
  margin:auto;
  padding:32px;
  background:rgba(255,255,255,0.04);
  border-radius:16px;
  backdrop-filter:blur(8px);
}
p.lead{color:var(--muted); margin-bottom:20px;font-size:0.9rem;}
.controls{display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin-bottom:16px;}
input[type=file]{color:#ccc;}
.mode{display:flex; gap:8px; align-items:center; background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:10px;}
.mode label{font-size:13px;color:var(--muted);}
.list{display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px;}
.item{
  background:rgba(255,255,255,0.05);
  border-radius:12px;
  padding:14px;
  display:flex;
  flex-direction:column;
  gap:12px;
}
.meta{display:flex; flex-direction:column; gap:6px;}
.title{font-weight:600;}
.sub{font-size:13px; color:var(--muted);}
.progress{height:6px; background:rgba(255,255,255,0.08); border-radius:6px; overflow:hidden;}
.progress>i{display:block;height:100%; background:linear-gradient(90deg,var(--accent),var(--accent2)); width:0%; transition:0.2s;}
button{cursor:pointer; border:none; border-radius:8px; padding:8px 12px; font-weight:500; transition:0.2s;}
button.play{background:linear-gradient(90deg,var(--accent),var(--accent2)); color:white;}
button.play:hover{filter:brightness(1.1); transform:scale(1.03);}
button.stop{background:transparent; border:1px solid rgba(255,255,255,0.1); color:var(--accent);}
.vol{display:flex; gap:8px; align-items:center;}
input[type=range]{width:100%; accent-color: var(--accent); height:12px; border-radius:6px; background: rgba(255,255,255,0.2);}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance:none; width:28px; height:28px; background: var(--accent); border-radius:50%; border:2px solid white; cursor:pointer; margin-top:-8px;
}
input[type=range]::-moz-range-thumb {
  width:28px; height:28px; background: var(--accent); border-radius:50%; border:2px solid white; cursor:pointer;
}
.footer{margin-top:20px; color:var(--muted); font-size:13px;}
</style>
</head>
<body>
<div class="app">
<p class="lead">
เพิ่มไฟล์เสียงหลายไฟล์ แล้วเลือกเล่นทีละไฟล์หรือเล่นพร้อมกันได้ (Single หรือ Mix Mode)<br>
ปรับเสียงแต่ละไฟล์ได้สูงสุด 300% และเสียงจะวนอัตโนมัติ
</p>

<div class="controls">
<input id="file" type="file" accept="audio/*" multiple />
<button id="clearAll" class="stop">ลบทั้งหมด</button>
<div class="mode">
<label style="font-weight:600;color:#cde7ff;">Mode:</label>
<label><input type="radio" name="mode" value="single" checked /> Single</label>
<label><input type="radio" name="mode" value="mix" /> Mix</label>
</div>
</div>

<div id="list" class="list"></div>

<div class="footer">Tip: ปรับ Volume slider เพื่อเพิ่มเสียงสูงสุด 300%. ระบบจะวนเสียงโดยอัตโนมัติ.</div>
</div>

<script>
const fileInput=document.getElementById('file');
const listEl=document.getElementById('list');
const clearAllBtn=document.getElementById('clearAll');
const tracks=[];
const audioCtx=new (window.AudioContext||window.webkitAudioContext)();

function formatTime(s){if(isNaN(s))return '0:00';const m=Math.floor(s/60);const sec=Math.floor(s%60).toString().padStart(2,'0');return `${m}:${sec}`;}
function getMode(){return document.querySelector('input[name="mode"]:checked').value;}
function stopOtherTracks(exceptId){
  for(const t of tracks){
    if(t.id!==exceptId&&!t.audio.paused){t.audio.pause(); t.audio.currentTime=0; t.btn.textContent='Play'; t.btn.className='play';}
  }
}

function createTrackRow(file){
  const id=Math.random().toString(36).slice(2,9);
  const url=URL.createObjectURL(file);
  const audio=new Audio(url); audio.loop=true;
  const source=audioCtx.createMediaElementSource(audio);
  const gainNode=audioCtx.createGain(); gainNode.gain.value=1.0;
  source.connect(gainNode).connect(audioCtx.destination);

  const item=document.createElement('div');
  item.className='item'; item.id='item-'+id;
  item.innerHTML=`
  <div class="meta">
    <div class="title">${file.name.replaceAll('<','&lt;')}</div>
    <div class="sub"><span id="time-${id}">0:00</span> / <span id="dur-${id}">0:00</span></div>
    <div class="progress" id="prog-${id}"><i></i></div>
  </div>
  <button id="btn-${id}" class="play">Play</button>
  <div class="vol">
    <label class="sub">Volume</label>
    <input id="vol-${id}" type="range" min="0" max="3" step="0.01" value="1"/>
  </div>`;
  listEl.appendChild(item);

  const btn=document.getElementById('btn-'+id);
  btn.addEventListener('click',()=>{
    audioCtx.resume();
    if(audio.paused){
      if(getMode()==='single') stopOtherTracks(id);
      audio.play(); btn.textContent='Stop'; btn.className='stop';
    } else { audio.pause(); audio.currentTime=0; btn.textContent='Play'; btn.className='play'; }
  });

  audio.addEventListener('loadedmetadata',()=>{document.getElementById('dur-'+id).textContent=formatTime(audio.duration);});
  audio.addEventListener('timeupdate',()=>{
    const t=document.getElementById('time-'+id);
    const p=document.querySelector('#prog-'+id+ ' > i');
    t.textContent=formatTime(audio.currentTime);
    const pct=audio.duration ? (audio.currentTime/audio.duration*100):0;
    p.style.width=pct+'%';
  });

  document.getElementById('vol-'+id).addEventListener('input',e=>{gainNode.gain.value=parseFloat(e.target.value);});
  tracks.push({id,audio,btn,gainNode});
}

fileInput.addEventListener('change',e=>{
  const files=Array.from(e.target.files||[]);
  for(const f of files){if(f.type.startsWith('audio')) createTrackRow(f);}
  fileInput.value='';
});

clearAllBtn.addEventListener('click',()=>{
  for(const t of tracks){t.audio.pause(); t.audio.src='';}
  listEl.innerHTML=''; tracks.length=0;
});
</script>
</body>
</html>
"""

components.html(html_code, height=850, scrolling=True)