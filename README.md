# Coqui Simple UI

A simple PyQt6 UI for Coqui TTS.

## Setup Instructions

This project is designed to run on Windows using a Miniconda environment.

### 1. Create and Activate Environment

```bash
conda create -n coqui_env python=3.10
conda activate coqui_env
```

### 2. Install Dependencies

Install the required packages using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

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
