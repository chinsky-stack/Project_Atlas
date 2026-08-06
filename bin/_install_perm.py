import subprocess
venv_py = "/Users/it/Project_Atlas/.venv/bin/python"
for pkg in ["alpaca-py", "bcrypt", "pyyaml", "streamlit", "python-dateutil", "requests"]:
    r = subprocess.run([venv_py, "-m", "pip", "install", "--quiet", pkg], capture_output=True, text=True)
    print(pkg, "->", "ok" if r.returncode == 0 else r.stderr[-120:])
