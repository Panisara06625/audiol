import streamlit as st
from moviepy.editor import VideoFileClip
import tempfile, os, base64, mimetypes
import magic

st.set_page_config(page_title="Audio Mixer (Streamlit)", layout="wide")

st.title("Audio Mixer — Streamlit + Multitouch + Video→MP3")
st.markdown(
    """
Upload audio or video files (mp4, mov, mkv, etc.). Video files are automatically
converted to MP3. The embedded player supports looping, per-track 0–300% volume,
single/mix mode, and multitouch-friendly pads for iPad.
"""
)

# --- Upload files ---
uploaded = st.file_uploader(
    "Upload audio or video files (multiple)",
    accept_multiple_files=True,
    type=None,
)

converted_files = []

if uploaded:
    for up in uploaded:
        up_bytes = up.read()
        up.seek(0)
        try:
            mime = magic.from_buffer(up_bytes, mime=True)
        except Exception:
            mime = mimetypes.guess_type(up.name)[0] or "application/octet-stream"

        name = up.name
        is_video = (mime and mime.startswith("video")) or os.path.splitext(name)[1].lower() in (
            ".mp4", ".mov", ".mkv", ".avi", ".webm"
        )

        if is_video:
            st.info(f"Converting video → MP3: {name}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(name)[1]) as tmp_in:
                tmp_in.write(up_bytes)
                tmp_in_path = tmp_in.name

            try:
                clip = VideoFileClip(tmp_in_path)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_out:
                    tmp_out_path = tmp_out.name
                clip.audio.write_audiofile(tmp_out_path, logger=None, bitrate="192k")
                clip.close()
                with open(tmp_out_path, "rb") as f:
                    mp3_bytes = f.read()
                converted_files.append({
                    "name": os.path.splitext(name)[0] + ".mp3",
                    "mime": "audio/mpeg",
                    "data": mp3_bytes
                })
            except Exception as e:
                st.error(f"Conversion failed for {name}: {e}")
            finally:
                try: os.remove(tmp_in_path)
                except: pass
                try: os.remove(tmp_out_path)
                except: pass
        else:
            converted_files.append({"name": name, "mime": mime or "audio/*", "data": up_bytes})

if converted_files:
    cols = st.columns([4,1])
    with cols[0]:
        for f in converted_files:
            st.write(f"- {f['name']} ({f['mime']})")
    with cols[1]:
        for f in converted_files:
            st.download_button("Download", data=f["data"], file_name=f["name"], mime=f["mime"])

if not converted_files:
    st.info("Upload files to enable the player.")
    st.stop()

# --- Prepare base64 data URLs ---
tracks_for_js = []
for idx, f in enumerate(converted_files):
    b64 = base64.b64encode(f["data"]).decode("ascii")
    data_url = f"data:{f['mime']};base64,{b64}"
    tracks_for_js.append({"id": idx, "name": f["name"], "url": data_url})

# --- HTML/JS Player ---
html = f"""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
body{{font-family:Inter,system-ui,Arial;color:#e6eef8;background:linear-gradient(180deg,#071126,#081a2d);margin:0;padding:12px}}
.player{{max-width:960px;margin:0 auto;background:rgba(255,255,255,0.03);padding:18px;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,0.6)}}
h2{{margin:0 0 8px;font-size:18px}}
.controls{{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap}}
.mode{{background:rgba(255,255,255,0.03);padding:8px;border-radius:10px;}}
.track{{display:grid;grid-template-columns:1fr 220px;gap:12px;padding:12px;border-radius:10px;background:rgba(255,255,255,0.02);margin-bottom:10px;align-items:center}}
.title{{font-weight:600}}
.sub{{color:#9ca3af;font-size:13px}}
.progress{{height:6px;background:rgba(255,255,255,0.06);border-radius:6px;overflow:hidden}}
.progress>i{{display:block;height:100%;background:linear-gradient(90deg,#60a5fa,#a855f7);width:0%}}
.playbtn{{padding:8px 12px;border-radius:8px;border:none;background:linear-gradient(90deg,#60a5fa,#a855f7);color:white;cursor:pointer}}
.stopbtn{{padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);background:transparent;color:#60a5fa;cursor:pointer}}
.pad{{height:90px;background:linear-gradient(180deg,rgba(255,255,255,0.01),rgba(255,255,255,0.02));border-radius:8px;display:flex;align-items:center;justify-content:center;touch-action:none;user-select:none}}
.pad .label{{font-size:13px;color:#cfe8ff}}
.vol-info{{font-size:13px;color:#9ca3af;margin-left:8px;width:58px;text-align:center}}
@media(max-width:720px){{.track{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="player">
<h2>Embedded Audio Mixer</h2>
<p style="color:#9ca3af;margin-top:6px;margin-bottom:12px">Play, loop, multitouch pads for volume (0–300%)</p>
<div class="controls">
<div class="mode">
<label style="font-weight:600;color:#cfe8ff;margin-right:8px">Mode:</label>
<label><input type="radio" name="mode" value="single" checked /> Single</label>
<label style="margin-left:8px"><input type="radio" name="mode" value="mix" /> Mix</label>
</div>
</div>
<div id="tracks"></div>
<div style="color:#9ca3af;margin-top:8px;font-size:13px">Tip: On iPad, use multiple fingers on different pads to adjust volumes simultaneously.</div>
</div>

<script>
const tracksData = {tracks_for_js};
const container = document.getElementById('tracks');
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function formatTime(s){{ if(isNaN(s)) return '0:00'; const m=Math.floor(s/60); const sec=Math.floor(s%60).toString().padStart(2,'0'); return m+':'+sec; }}
function getMode(){{ return document.querySelector('input[name="mode"]:checked').value; }}

const tracks = [];

tracksData.forEach(td=>{{
  const id = 't'+td.id;
  const wrapper = document.createElement('div'); wrapper.className='track'; wrapper.id='wrap-'+id;
  wrapper.innerHTML = `
    <div>
      <div class="title">${{td['name'].replaceAll('<','&lt;')}}</div>
      <div class="sub"><span id="time-${{id}}">0:00</span> / <span id="dur-${{id}}">0:00</span></div>
      <div class="progress" id="prog-${{id}}"><i></i></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px">
      <button id="btn-${{id}}" class="playbtn">Play</button>
      <div style="display:flex;align-items:center;gap:8px">
        <div id="pad-${{id}}" class="pad"><div class="label">Touch to adjust</div></div>
        <div style="display:flex;flex-direction:column;align-items:flex-start">
          <div style="display:flex;align-items:center;gap:6px">
            <div class="sub">Volume</div>
            <div id="volpct-${{id}}" class="vol-info">100%</div>
          </div>
          <div style="font-size:12px;color:#9ca3af">0% — 300%</div>
        </div>
      </div>
    </div>
  `;
  container.appendChild(wrapper);

  const audio = new Audio(td['url']);
  audio.loop = true;
  audio.preload = 'metadata';
  const source = audioCtx.createMediaElementSource(audio);
  const gainNode = audioCtx.createGain();
  gainNode.gain.value = 1.0;
  source.connect(gainNode).connect(audioCtx.destination);

  audio.addEventListener('loadedmetadata', ()=>{{ document.getElementById('dur-'+id).textContent = formatTime(audio.duration); }});
  audio.addEventListener('timeupdate', ()=>{{
    const t = document.getElementById('time-'+id);
    const p = document.querySelector('#prog-'+id+' > i');
    t.textContent = formatTime(audio.currentTime);
    const pct = audio.duration ? (audio.currentTime/audio.duration*100) : 0;
    p.style.width = pct + '%';
  }});

  const btn = document.getElementById('btn-'+id);
  btn.addEventListener('click', ()=>{{
    if(audio.paused){{
      audioCtx.resume();
      if(getMode()==='single'){{ tracks.forEach(tr=>{{ if(!tr.audio.paused){{ tr.audio.pause(); tr.audio.currentTime=0; tr.btn.textContent='Play'; tr.btn.className='playbtn'; }} }}); }}
      audio.play();
      btn.textContent='Stop';
      btn.className='stopbtn';
    }} else {{
      audio.pause();
      audio.currentTime=0;
      btn.textContent='Play';
      btn.className='playbtn';
    }}
  }});

  const pad = document.getElementById('pad-'+id);
  const volDisplay = document.getElementById('volpct-'+id);

  function setGainFromRelative(rel){{
    const g = Math.max(0, Math.min(3, rel*3));
    gainNode.gain.value = g;
    const pct = Math.round(g*100);
    volDisplay.textContent = pct + '%';
  }}

  function relFromTouchY(y, rect){{
    const local = y - rect.top;
    const rel = 1 - (local / rect.height);
    return Math.max(0, Math.min(1, rel));
  }}

  pad.addEventListener('pointerdown', e=>{{ e.preventDefault(); pad.setPointerCapture(e.pointerId); const rect=pad.getBoundingClientRect(); setGainFromRelative(relFromTouchY(e.clientY, rect)); }});
  pad.addEventListener('pointermove', e=>{{ if(e.pressure===0) return; const rect=pad.getBoundingClientRect(); setGainFromRelative(relFromTouchY(e.clientY, rect)); }});
  pad.addEventListener('pointerup', e=>{{ try{{ pad.releasePointerCapture(e.pointerId); }}catch(err){{}} }});

  pad.addEventListener('touchstart', e=>{{ e.preventDefault(); const rect=pad.getBoundingClientRect(); for(const t of e.touches){{ const rel=relFromTouchY(t.clientY, rect); setGainFromRelative(rel); }} }}, {{passive:false}});
  pad.addEventListener('touchmove', e=>{{ e.preventDefault(); const rect=pad.getBoundingClientRect(); for(const t of e.touches){{ if(t.clientX>=rect.left && t.clientX<=rect.right && t.clientY>=rect.top && t.clientY<=rect.bottom){{ const rel=relFromTouchY(t.clientY, rect); setGainFromRelative(rel); break; }} }} }}, {{passive:false}});

  tracks.push({{id, name:td['name'], audio, gainNode, btn}});
}});
</script>
</body>
</html>
"""

st.components.v1.html(html, height=700, scrolling=True)

st.markdown(
    """
**Notes:**
- Base64 embedding is fine for small/medium files. For large files, host MP3s externally and pass URLs.
- Multitouch pads allow simultaneous volume control on iPad.
"""
)
