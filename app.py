# streamlit_app.py
import streamlit as st
from moviepy.editor import VideoFileClip, AudioFileClip
import tempfile, os, base64, io, mimetypes
import magic  # python-magic for file type detection

st.set_page_config(page_title="Audio Mixer (Streamlit)", layout="wide")

st.title("Audio Mixer — Streamlit + Multitouch + Video→MP3")
st.markdown(
    """
Upload audio files or video files (mp4, mov, mkv). Video files are automatically
converted to MP3. The embedded player supports looping, per-track 0–300% volume
(using Web Audio API), single/mix mode, and multitouch-friendly volume pads for iPad.
"""
)

# --- Upload files ---
uploaded = st.file_uploader(
    "Upload audio or video files (multiple)",
    accept_multiple_files=True,
    type=None,
)

st.markdown("### Uploaded / Converted files")
converted_files = []  # list of dicts: {name, mime, data (bytes)}

if uploaded:
    for up in uploaded:
        # detect mime
        up_bytes = up.read()
        up.seek(0)
        try:
            mime = magic.from_buffer(up_bytes, mime=True)
        except Exception:
            mime = mimetypes.guess_type(up.name)[0] or "application/octet-stream"

        name = up.name
        # Quick video detection by mime or extension:
        is_video = (mime and mime.startswith("video")) or os.path.splitext(name)[1].lower() in (
            ".mp4",
            ".mov",
            ".mkv",
            ".avi",
            ".webm",
        )

        if is_video:
            st.info(f"Converting video → MP3: {name}")
            # write uploaded bytes to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(name)[1]) as tmp_in:
                tmp_in.write(up_bytes)
                tmp_in.flush()
                tmp_in_path = tmp_in.name

            try:
                clip = VideoFileClip(tmp_in_path)
                # write audio to temp mp3
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_out:
                    tmp_out_path = tmp_out.name
                # Use bitrate/quality; can be tuned
                clip.audio.write_audiofile(tmp_out_path, logger=None, bitrate="192k")
                clip.close()
                # read mp3 bytes
                with open(tmp_out_path, "rb") as f:
                    mp3_bytes = f.read()
                converted_files.append({"name": os.path.splitext(name)[0] + ".mp3", "mime": "audio/mpeg", "data": mp3_bytes})
            except Exception as e:
                st.error(f"Conversion failed for {name}: {e}")
            finally:
                try:
                    os.remove(tmp_in_path)
                except Exception:
                    pass
                try:
                    os.remove(tmp_out_path)
                except Exception:
                    pass
        else:
            # assume audio file (or already mp3); possibly convert to mp3 for consistent mime if needed
            converted_files.append({"name": name, "mime": mime or "audio/*", "data": up_bytes})

# Show list and provide download links for converted MP3s
if converted_files:
    cols = st.columns([4,1])
    with cols[0]:
        for f in converted_files:
            st.write(f"- {f['name']} ({f['mime']})")
    with cols[1]:
        for f in converted_files:
            st.download_button(label="Download", data=f["data"], file_name=f["name"], mime=f["mime"])

# If no files yet, show hint and exit early
if not converted_files:
    st.info("Upload one or more audio/video files to enable the embedded player.")
    st.stop()

# --- Prepare data URLs for embedding into HTML component ---
# WARNING: embedding large files as base64 in HTML may be heavy for very large files.
# For a demo / small files it's fine. For large deployments, serve files from a static server.
tracks_for_js = []
for idx, f in enumerate(converted_files):
    b64 = base64.b64encode(f["data"]).decode("ascii")
    data_url = f"data:{f['mime']};base64,{b64}"
    tracks_for_js.append({"id": idx, "name": f["name"], "url": data_url})

# --- Build the HTML + JS player (multitouch pads, Web Audio API, etc.) ---
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
  .progress{height:6px;background:rgba(255,255,255,0.06);border-radius:6px;overflow:hidden}
  .progress>i{display:block;height:100%;background:linear-gradient(90deg,#60a5fa,#a855f7);width:0%}
  .playbtn{padding:8px 12px;border-radius:8px;border:none;background:linear-gradient(90deg,#60a5fa,#a855f7);color:white;cursor:pointer}
  .stopbtn{padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);background:transparent;color:#60a5fa;cursor:pointer}
  .pad{{height:90px;background:linear-gradient(180deg,rgba(255,255,255,0.01),rgba(255,255,255,0.02));border-radius:8px;display:flex;align-items:center;justify-content:center;touch-action:none;user-select:none}}
  .pad .label{{font-size:13px;color:#cfe8ff}}
  .vol-info{{font-size:13px;color:#9ca3af;margin-left:8px;width:58px;text-align:center}}
  @media(max-width:720px){.track{{grid-template-columns:1fr}}}
</style>
</head>
<body>
  <div class="player">
    <h2>Embedded Audio Mixer</h2>
    <p style="color:#9ca3af;margin-top:6px;margin-bottom:12px">Play, loop, multitouch pads for volume (works on iPad) — per-track gain up to 300%.</p>

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
const tracksData = {tracks_for_js}; // inserted from python
// Build UI elements
const container = document.getElementById('tracks');
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function formatTime(s){ if(isNaN(s)) return '0:00'; const m=Math.floor(s/60); const sec=Math.floor(s%60).toString().padStart(2,'0'); return m+':'+sec; }
function getMode(){ return document.querySelector('input[name="mode"]:checked').value; }

const tracks = []; // will hold {id, name, audio, gainNode, elements}

// create rows
tracksData.forEach(td=>{
  const id = 't'+td.id;
  const wrapper = document.createElement('div'); wrapper.className='track'; wrapper.id='wrap-'+id;
  wrapper.innerHTML = `
    <div>
      <div class="title">${td['name'].replaceAll('<','&lt;')}</div>
      <div class="sub"><span id="time-${id}">0:00</span> / <span id="dur-${id}">0:00</span></div>
      <div class="progress" id="prog-${id}"><i></i></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px">
      <button id="btn-${id}" class="playbtn">Play</button>
      <div style="display:flex;align-items:center;gap:8px">
        <div id="pad-${id}" class="pad"><div class="label">Touch to adjust</div></div>
        <div style="display:flex;flex-direction:column;align-items:flex-start">
          <div style="display:flex;align-items:center;gap:6px">
            <div class="sub">Volume</div>
            <div id="volpct-${id}" class="vol-info">100%</div>
          </div>
          <div style="font-size:12px;color:#9ca3af">0% — 300%</div>
        </div>
      </div>
    </div>
  `;
  container.appendChild(wrapper);

  // create audio
  const audio = new Audio(td['url']);
  audio.loop = true;
  audio.preload = 'metadata';
  const source = audioCtx.createMediaElementSource(audio);
  const gainNode = audioCtx.createGain();
  gainNode.gain.value = 1.0;
  source.connect(gainNode).connect(audioCtx.destination);

  // update metadata
  audio.addEventListener('loadedmetadata', ()=>{
    document.getElementById('dur-'+id).textContent = formatTime(audio.duration);
  });
  audio.addEventListener('timeupdate', ()=>{
    const t = document.getElementById('time-'+id);
    const p = document.querySelector('#prog-'+id+' > i');
    t.textContent = formatTime(audio.currentTime);
    const pct = audio.duration ? (audio.currentTime/audio.duration*100) : 0;
    p.style.width = pct + '%';
  });

  // play button toggles play/stop
  const btn = document.getElementById('btn-'+id);
  btn.addEventListener('click', ()=>{
    if(audio.paused){
      audioCtx.resume();
      if(getMode()==='single'){
        tracks.forEach(tr=>{ if(!tr.audio.paused){ tr.audio.pause(); tr.audio.currentTime=0; tr.btn.textContent='Play'; tr.btn.className='playbtn'; } });
      }
      audio.play();
      btn.textContent = 'Stop';
      btn.className = 'stopbtn';
    } else {
      audio.pause();
      audio.currentTime = 0;
      btn.textContent = 'Play';
      btn.className = 'playbtn';
    }
  });

  // Multitouch pad: vertical touch controls volume 0..3 (0%..300%)
  const pad = document.getElementById('pad-'+id);
  const volDisplay = document.getElementById('volpct-'+id);

  // function to set gain from 0..3
  function setGainFromRelative(rel){ // rel in 0..1 where 1 top = 300%
    const g = Math.max(0, Math.min(3, rel*3));
    gainNode.gain.value = g;
    const pct = Math.round(g*100);
    volDisplay.textContent = pct + '%';
  }

  // helper to get relative Y inside pad (0 at bottom -> 1 at top)
  function relFromTouchY(y, rect){
    const local = y - rect.top;
    const rel = 1 - (local / rect.height);
    return Math.max(0, Math.min(1, rel));
  }

  // pointer events (work for mouse and single touch)
  pad.addEventListener('pointerdown', e=>{
    e.preventDefault();
    pad.setPointerCapture(e.pointerId);
    const rect = pad.getBoundingClientRect();
    const rel = relFromTouchY(e.clientY, rect);
    setGainFromRelative(rel);
  });
  pad.addEventListener('pointermove', e=>{
    if(e.pressure===0) return; // not pressed
    const rect = pad.getBoundingClientRect();
    const rel = relFromTouchY(e.clientY, rect);
    setGainFromRelative(rel);
  });
  pad.addEventListener('pointerup', e=>{
    try{ pad.releasePointerCapture(e.pointerId); }catch(err){}
  });

  // touch events (for multitouch)
  pad.addEventListener('touchstart', e=>{
    e.preventDefault();
    // handle all touches on this pad
    const rect = pad.getBoundingClientRect();
    for(const t of e.touches){
      const rel = relFromTouchY(t.clientY, rect);
      setGainFromRelative(rel);
    }
  }, {passive:false});
  pad.addEventListener('touchmove', e=>{
    e.preventDefault();
    const rect = pad.getBoundingClientRect();
    // We only use the first touch that is inside this pad for this pad instance
    // For better multitouch across different pads, each pad listens to its own touches.
    for(const t of e.touches){
      // if touch is within this pad bounds, update using that touch
      if(t.clientX >= rect.left && t.clientX <= rect.right && t.clientY >= rect.top && t.clientY <= rect.bottom){
        const rel = relFromTouchY(t.clientY, rect);
        setGainFromRelative(rel);
        break;
      }
    }
  }, {passive:false});

  tracks.push({id, name:td['name'], audio, gainNode, btn});
});

// end of building tracks
</script>
</body>
</html>
"""

# Render HTML in Streamlit component
st.components.v1.html(html, height=700, scrolling=True)

st.markdown(
    """
**Notes & limitations**

- The demo embeds audio as `data:` base64 URLs — this is fine for small/medium files but for large files it's heavy.
- For production, host MP3 files on a static server (S3, Netlify, etc.) and pass URLs to the player for streaming.
- The multitouch pads are handled via `touch`/`pointer` events — they allow multiple fingers on different pads (e.g., iPad).
"""
)
