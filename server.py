import asyncio
import json
import time
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from aiortc import RTCPeerConnection, RTCSessionDescription

import rppg
import numpy as np
from scipy.signal import butter, filtfilt, welch, hilbert, find_peaks

app = FastAPI()
app.mount("/static", StaticFiles(directory="."), name="static")

pcs = set()

def bandpass(sig, fs, low, high, order=3):
    b, a = butter(order, [low, high], fs=fs, btype="band")
    return filtfilt(b, a, sig)

def estimate_rr_from_bvp(bvp, fs, rr_low=0.1, rr_high=0.7, window_s=30):
    if bvp is None or len(bvp) < fs * max(10, window_s):
        return None
    bvp = np.asarray(bvp, dtype=np.float32)
    if bvp.ndim != 1:
        bvp = bvp.reshape(-1)
    env = np.abs(hilbert(bvp))
    env = bandpass(env, fs, rr_low, rr_high)
    if not np.all(np.isfinite(env)):
        return None
    f, pxx = welch(env, fs=fs, nperseg=min(len(env), int(fs * window_s)))
    band = (f >= rr_low) & (f <= rr_high)
    rr_am = None
    if np.any(band):
        rr_hz = f[band][np.argmax(pxx[band])]
        rr_am = rr_hz * 60.0

    peaks, _ = find_peaks(bvp, distance=max(1, int(0.25 * fs)))
    rr_fm = None
    if len(peaks) >= 5:
        ibi = np.diff(peaks) / fs
        t_ibi = peaks[1:] / fs
        if len(ibi) >= 5 and (t_ibi[-1] - t_ibi[0]) >= 10:
            t_uniform = np.linspace(t_ibi[0], t_ibi[-1], int((t_ibi[-1] - t_ibi[0]) * fs))
            ibi_interp = np.interp(t_uniform, t_ibi, ibi)
            ibi_bp = bandpass(ibi_interp, fs, rr_low, rr_high)
            if not np.all(np.isfinite(ibi_bp)):
                ibi_bp = ibi_bp[np.isfinite(ibi_bp)]
            if len(ibi_bp) > 1:
                f2, pxx2 = welch(ibi_bp, fs=fs, nperseg=min(len(ibi_bp), int(fs * window_s)))
                band2 = (f2 >= rr_low) & (f2 <= rr_high)
                if np.any(band2):
                    rr_hz2 = f2[band2][np.argmax(pxx2[band2])]
                    rr_fm = rr_hz2 * 60.0

    candidates = [v for v in (rr_am, rr_fm) if v is not None]
    if not candidates:
        return None
    return float(np.mean(candidates))


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("client.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    data_channel = {"dc": None}

    @pc.on("datachannel")
    def on_datachannel(channel):
        data_channel["dc"] = channel

    @pc.on("track")
    def on_track(track):
        if track.kind != "video":
            return

        model = rppg.Model()
        model.face_detect_per_n = 1

        async def run_rppg():
            with model:
                last_report = 0.0
                start_time = time.time()
                rr_history = deque(maxlen=5)
                while True:
                    try:
                        frame = await track.recv()
                    except Exception:
                        break

                    img = frame.to_ndarray(format="rgb24")
                    model.update_frame(img, ts=time.time())

                    now = time.time()
                    if now - last_report >= 1.0:
                        if now - start_time < 10:
                            last_report = now
                            continue
                        if model.n_signal < model.fps * 10:
                            last_report = now
                            continue
                        if model.hasface <= 0:
                            last_report = now
                            continue

                        result = model.hr(start=-10)
                        hr = None
                        rr = None
                        if isinstance(result, dict):
                            hr = result.get("hr")
                            sqi = result.get("SQI")
                        else:
                            hr = result
                            sqi = None

                        if sqi is not None and sqi >= 0.5:
                            bvp, _ = model.bvp(start=-30)
                            rr = estimate_rr_from_bvp(bvp, model.fps, window_s=30)
                            if rr is not None and np.isfinite(rr):
                                rr_history.append(rr)
                        if rr_history:
                            rr = float(np.median(rr_history))

                        if data_channel["dc"] is not None:
                            try:
                                payload = {}
                                if hr is not None:
                                    hr_val = float(hr)
                                    if hr_val == hr_val:
                                        payload["hr"] = hr_val
                                if rr is not None:
                                    rr_val = float(rr)
                                    if rr_val == rr_val:
                                        payload["rr"] = rr_val
                                if payload:
                                    data_channel["dc"].send(json.dumps(payload))
                                    if "hr" in payload or "rr" in payload:
                                        print(
                                            "HR:", f"{payload.get('hr', 'n/a')}",
                                            "RR:", f"{payload.get('rr', 'n/a')}",
                                        )
                            except Exception:
                                pass
                        last_report = now
            model.stop()

        asyncio.ensure_future(run_rppg())

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@app.on_event("shutdown")
async def on_shutdown():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
