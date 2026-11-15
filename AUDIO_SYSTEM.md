# Scene-aware sound system

The sound director is a separate module in audio_director.py. It produces timestamped cues with evidence from scene state or animation keyframes. It is conservative: no sound is emitted just because narration mentions a noun.

## Current evidence rules

- Door creak: door_open state increases from the preceding scene.
- Footsteps: a visible actor has a walk/run keyframe AND moves position.
- Rain: environment is explicitly rainroom.
- Wind: outdoor street/forest scene explicitly sets weather to wind.
- Wing flaps: an actor in the scene actors list explicitly has species bird.
- Bird calls are not inferred yet; they require an explicit future event annotation.

Every cue records evidence and source. A future Groq planner must return the same cue contract and pass validate_audio_cues; it cannot bypass evidence validation. A door event cannot create footsteps, and a forest background alone cannot create bird sounds.

## Commercial sound library policy

The current renderer uses original procedural fallback foley, not downloaded recordings. These are research entry points, not blanket permission for every file:

- Mixkit: https://mixkit.co/free-sound-effects/
- Pixabay: https://pixabay.com/sound-effects/
- Freesound: https://freesound.org/

Before a recording enters the production library, store exact asset URL, creator, title, license identifier and URL, explicit commercial-use permission, attribution text, retrieval date and SHA-256. Reject CC BY-NC, non-commercial, editorial-only, unclear, or missing license metadata. Check each asset license, not merely the website. Respect provider terms and download/API rules.

Keep large audio files out of Git. Store approved files in a release or external object storage later; keep manifests and small test fixtures in this repository.

## Groq integration boundary

Groq will later analyze structured scene descriptions, action tracks and character states, then propose cue events and timestamps. The deterministic validator remains the gatekeeper. The renderer/mixer does not depend on Groq and runs in GitHub Actions.
