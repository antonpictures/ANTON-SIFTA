with open("Documents/MAKE_A_WISH_HASSABIS_TOURNAMENT.md", "r") as f:
    text = f.read()

text = text.replace("* **WISH_005: Hippocampus → Cortex**", "* **WISH_005: Hippocampus → Cortex (✅ GRANTED)**")
text = text.replace("**Status:** ROUND 3 COMPLETE. WISH_004 GRANTED.", "**Status:** TOURNAMENT COMPLETE. WISH_005 GRANTED.")
text = text.replace("**Next Up:** WISH_003 or 005.", "**Next Up:** All wishes granted. Swarm stands ready.")

with open("Documents/MAKE_A_WISH_HASSABIS_TOURNAMENT.md", "w") as f:
    f.write(text)
