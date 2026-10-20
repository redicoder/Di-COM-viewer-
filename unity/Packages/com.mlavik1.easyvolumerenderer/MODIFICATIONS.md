# Local modifications to UnityVolumeRendering 1.8.0

This is an embedded copy of [UnityVolumeRendering](https://github.com/mlavik1/UnityVolumeRendering)
version 1.8.0 (MIT, see `LICENSE.md`), kept in the repository because the dissection features need
shader changes. The project's `Packages/manifest.json` no longer references the git URL; Unity loads
this folder as an embedded package.

It lives under `unity/Packages/` instead of `Assets/ThirdParty/` (as the spec first suggested) so that its
assembly definitions and asset GUIDs stay exactly as upstream: moving it would change both for no gain.

Every change to files in this folder must be listed here.

| Date | Change | Reason |
|---|---|---|
| 2026-10-20 | Removed `Documentation~/` and `SampleProject~/` | Not loaded by Unity (`~` folders); 47 MB of unused files |
