# Calm Stigmergy RFC

Status: draft policy.

SIFTA may communicate state through quiet, truthful signals that do not steal
control from the Architect. The goal is ambient coordination, not surprise.

## Allowed Channels

- Dock badge state for counts, alerts, or short-lived attention markers.
- Menubar or status-icon state for health, bridge, or sleep/awake posture.
- Silent Notification Center notices for completed work, blocked effectors, or
  explicit reminders.
- Existing in-app status labels, HUD text, and append-only ledgers.
- Receipt-backed summaries that name what changed and where evidence lives.

## Forbidden Channels

- Moving windows, changing focus, fake clicks, fake typing, or cursor motion.
- Password prompts, auth prompts, or commands known to trigger them as a
  signaling mechanism.
- Sound by default, including spoken announcements, unless the owner explicitly
  enabled audio for that channel.
- UI manipulation that pretends to be the human owner or hides the executing
  agent.

## Doctrine

This policy follows IDE Boot Covenant section 7.5 and section 7.8: keep core
surfaces inside the Python/Qt organism, keep senses open without adding new
permission gates, and keep external effects receipt-backed. Calm stigmergy is
allowed only when it is honest, reversible, local, and low-friction.
