# CLAUDE SETUP INSTRUCTIONS FOR PROJECT ATLAS

Copy and paste this entire file to Claude.

---

You are helping Dr. King set up Project Atlas on his computer.

The full project folder has already been created and contains:

- README.md
- requirements.txt
- config.yaml
- main.py
- src/ folder with risk_office.py, journal.py, strategy_lab.py
- data/, logs/, templates/, docs/

### Your job

1. Make sure Python 3.10+ is installed and available in the terminal.
2. Open a terminal inside the Project_Atlas folder.
3. Run exactly these two commands:

```bash
pip install -r requirements.txt
streamlit run main.py
```

4. Confirm that a browser window opens showing “Project Atlas — Mission Control”.
5. Tell Dr. King the system is running and ready for paper trading.

Do not change any code unless something is broken.  
Do not add extra features.  
Just get the dashboard running.

If there is any error, fix only what is necessary to make `streamlit run main.py` work, then stop.

---

End of instructions.
