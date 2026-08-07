# ATLAS CAPITAL — Portal Changelog

Tracked by Hermes. Bump `VERSION` in `main.py` on any user-visible change, add an
entry here, and commit. The version shows in the footer + the SIMULATED banner so
cache-staleness is visible at a glance.

## v0.5 — 2026-08-07
- Added `VERSION` constant (footer + SIMULATED banner) so stale mobile caches are obvious.
- (manifest of v0.4.1 fixes rolled in)
- Tab order fixed: Auto Trader first; Mission Control / New Idea / Risk Office / etc. map correctly (no off-by-one).
- Approved Member Comments now render under the (correctly labeled) Member Comments tab.
- Self-service password reset for approved members (verify username + email on file; notify Dr. King; no approval needed).
- Login autocomplete hints (username / current-password) so browsers save credentials.
- Larger mobile input/label font sizes.
- "Both Books" read-only panel: Dr. King's auto-traded book + Penn's MASTA, visible to all members.
- Weekly digest: removed private "Penn likes Hermes" line; manual trades labeled "Manual (Dr. King)" (never flagged); $notional shown instead of "?"; improvement-suggestions table; Penn's MASTA book section.
- Inbound email monitor: Hermes answers Penn (professional letters, "subject to approval"), acknowledges + logs suggestions, relay-only-on-important Telegram alerts.
- Suggestion lifecycle: `atlas_mod.py suggestion <ID> <approve|decline|change> [note]` follows up with the user.

## v0.4 — (pre-versioning baseline)
- Branded ATLAS CAPITAL portal, Streamlit, 9 tabs.
- Approval-gated access + moderated comments.
- Simulated broker + Risk Office + Strategy Lab.
- Permanent Cloudflare tunnel `portal.ilyatorchinsky.com`.
