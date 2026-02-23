HR/RR Prototype (Local + WebRTC)

This repo contains a working prototype for **remote heart rate (HR)** and **respiratory rate (RR)** estimation from a webcam feed. It includes:
- **Local live inference** (`open-r.py`) with on-screen HR/RR.
- **WebRTC client→server** inference (`server.py` + `client.html`) where the server computes HR/RR.

This is **not a diagnostic tool**. It provides non-contact vital sign estimation for research and prototyping only.

---

## Why RR Matters (TB Screening Context)
Tuberculosis (TB) is a respiratory disease whose **active pulmonary symptoms** can include a prolonged cough, chest pain, fever, night sweats, weight loss, fatigue, and coughing up blood. Respiratory rate (RR) is not a TB diagnostic by itself, but it is a **relevant physiologic signal** in respiratory screening contexts.  
Sources:
- CDC — Signs and Symptoms of Tuberculosis: https://www.cdc.gov/tb/signs-symptoms/index.html
- CDC — About Tuberculosis: https://www.cdc.gov/tb/about/index.html

**Important:** This system **does not diagnose TB**. It only estimates HR/RR from video. Any medical decisions require clinical testing and professional evaluation.

---

## How RR Is Computed Here (Standard rPPG Post‑Processing)
We follow a commonly used rPPG/PPG post‑processing approach:
1. **rPPG/BVP extraction** from the face video stream.
2. **Respiratory modulation signals** derived from the BVP:
   - **Amplitude modulation (AM / envelope)** of the BVP.
   - **Frequency modulation (FM / beat‑to‑beat interval variability)**.
3. **Spectral peak detection** (Welch/FFT) in the respiratory band.
4. **Fusion** of AM and FM estimates.

This is consistent with established PPG respiration literature, which derives RR from respiratory‑induced variations in the PPG and then selects the dominant respiratory frequency.  
Sources:
- Karlen et al., 2013 (IEEE TBME): https://pubmed.ncbi.nlm.nih.gov/23399950/
- Nilsson, 2013 (Anesth Analg review): https://pubmed.ncbi.nlm.nih.gov/23449854/

---

## What We Implemented
**Local live HR/RR**
- `open-r.py` runs open‑rppg live from a webcam.
- HR is computed continuously.
- RR is estimated from the last 30s BVP window using AM+FM and spectral peak detection.
- SQI gating and median smoothing reduce spikes.

**WebRTC client→server**
- `server.py` runs FastAPI + aiortc.
- `client.html` captures webcam and streams to the server.
- Server computes HR/RR and sends results back over a data channel.

---

## Requirements (Python 3.12)
Make sure you use **Python 3.12** (Python 3.13 removes modules some libs still depend on).

Install dependencies in a venv:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install open-rppg opencv-python scipy fastapi uvicorn aiortc
```

---

## Run Local Live HR/RR
```bash
source .venv/bin/activate
python open-r.py
```

Notes:
- RR needs ~30s of stable signal before it appears.
- Keep lighting stable and minimize head motion.

---

## Run WebRTC (Browser → Server)
Start server:
```bash
source .venv/bin/activate
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open in browser:
```
http://localhost:8000/
```

Allow camera access. HR/RR will appear after the warm‑up window.

---

## Limitations
- Webcam rPPG is sensitive to lighting and motion.
- RR is a derived signal and can be noisy if signal quality is low.
- This is **not a medical device** and should not be used for diagnosis.

---

## References
- CDC — Signs and Symptoms of TB: https://www.cdc.gov/tb/signs-symptoms/index.html  
- CDC — About TB (overview): https://www.cdc.gov/tb/about/index.html  
- Karlen et al., 2013 — Multiparameter RR from PPG (AM/FM/intensity + FFT): https://pubmed.ncbi.nlm.nih.gov/23399950/  
- Nilsson, 2013 — Respiration signals from PPG (review): https://pubmed.ncbi.nlm.nih.gov/23449854/  
