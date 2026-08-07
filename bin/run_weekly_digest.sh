#!/usr/bin/env bash
# Weekly ATLAS digest runner — uses the perm venv.
cd /Users/it/Project_Atlas || exit 1
source .venv/bin/activate 2>/dev/null || export PATH="/Users/it/Project_Atlas/.venv/bin:$PATH"
python bin/weekly_digest.py --since 7
