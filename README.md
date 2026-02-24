# Coqui Simple UI

A simple PyQt6 UI for Coqui TTS.

## Setup Instructions

This project is designed to run on Windows using a dedicated Conda environment.

### 1. Prerequisites: TTS Installation in Conda

Before running the application, you must install the `TTS` package in an isolated Conda environment. 

1. Create a Python 3.10 environment:
   ```bash
   conda create -n coqui_env python=3.10
   conda activate coqui_env
   ```
2. Follow the official [Coqui TTS Installation Guide](https://github.com/coqui-ai/TTS?tab=readme-ov-file#installation) or [@GuyPaddock's Windows Installation Guide](https://github.com/coqui-ai/TTS/discussions/2360) to install `TTS`.

> **Note on Windows CUDA Installation:**
> Guy Paddock's guide is excellent, but its **section on configuring PyTorch for GPU/CUDA is outdated**. Finding the correct matching versions of PyTorch, PyAudio, and the CUDA toolkit for your specific graphics card can be complex. It is highly recommended to use an AI chat client to determine the exact installation commands based on your local hardware and CUDA version.

### 2. Install Project UI Dependencies

Install the required UI packages using the `requirements.txt` file (Note: `TTS` itself is purposefully omitted to prevent environment conflicts):

```bash
pip install -r requirements.txt
```

### 3. Recommended Post-Installation Patches

After completing the base `TTS` installation, it is strongly recommended to apply these manual patches to your `coqui_env` environment to fix known bugs in the original libraries:

#### Fix XTTS v2 Loading (Downgrade Transformers)
An `ImportError` related to `BeamSearchScorer` often occurs when using XTTS v2 due to an incompatibility in newer transformer versions.
- **Fix:** `pip install transformers==4.33.0`

#### Fix Bark Model Crashing (`invalid load key, '<'`)
The Bark model downloads a broken HTML page instead of the actual weights due to incorrect URLs generated in its configuration.
- **Fix:** 
  1. Open the local config file: `C:\Users\<User\AppData\Local\tts\tts_models--multilingual--multi-dataset--bark\config.json`.
  2. Change the broken raw model URL to use the direct download link:
     - **Old:** `https://huggingface.co/erogol/bark/tree/main/text_2.pt`
     - **New:** `https://huggingface.co/suno/bark/resolve/main/text_2.pt`
  3. Delete the locally cached `< 1MB` corrupted `text_2.pt` file from that directory to force a clean re-download.

### 3. Run the Application

The easiest way to run the application invisibly on Windows:

**Double-click in File Explorer:**
Run **`run_app.vbs`**. This will launch the application without any command windows appearing.

---

**Other options:**

**From PowerShell (Visible):**
```powershell
.\run_app.ps1
```




## Requirements

- Python 3.9+ (Python 3.10 recommended for Coqui TTS)
- PyQt6 6.10.2
- Coqui TTS
