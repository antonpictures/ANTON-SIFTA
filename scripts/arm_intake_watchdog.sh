#!/bin/bash
# Phone /c commands land in the arm's queue — automatically.
# Architect 2026-10-04: "i sent a /c from phone but i dont see it in this hole queued.. why?
# i want to see visually how you code Alice with command from phone"
# Nothing was running the intake: the queue only filled when someone remembered to call it.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 0
export PYTHONPATH="$REPO"
"$REPO/bin/sifta-brain" -m System.swarm_arm_task_queue intake >> .sifta_state/runtime_logs/arm_intake.log 2>&1
exit 0
