# Spec notes: agreed deviations and open checks

Review of `DISSECTION_TABLE_SPEC.md` before implementation. Each item is either a decision (applied) or a
check that must be done before the related step is closed.

## Decisions

| Spec | Decision | Why |
|---|---|---|
| §2.1 fork UVR into `Assets/ThirdParty/` | Kept as an **embedded package** in `unity/Packages/com.mlavik1.easyvolumerenderer/`, git-URL dependency removed from the manifest, changes logged in its `MODIFICATIONS.md` | Same effect (code in the repo, editable), but assembly definitions and asset GUIDs stay identical to upstream |
| §2.2 shader snippet (`sampler3D`, `tex3Dlod`) | Written in the URP shader's own style: `Texture3D` + `SamplerState` + `SampleLevel` | The URP DVR shader declares textures that way; mixing styles does not compile cleanly |
| §2.5 GPU picking first | First a **CPU copy of the mask**, updated by the same `MaskOp` list, used by the existing CPU ray-march picker behind `IVolumePicker`; GPU pick pass later if profiling asks for it | Picking must see cuts from day one; the CPU path is simpler and testable, and runs only on tap |
| §2.6 dig coalescing | A dig stroke is stored as **one op** (path of centres + radius), not one op per frame | Keeps the replay list short for undo/redo and lessons |
| §4 legacy `Input` removed | The **Input Manager stays enabled** (Active Input Handling = Both) even after the tools move to the Input System | Sony's SR Display plugin reads the legacy Input Manager |

## Checks before the related step is closed

1. **Visible Human licence** (§3.1): confirm on the NLM site that the data is public domain since 2019,
   the exact acknowledgement wording, and whether NCI Imaging Data Commons hosts the CT as DICOM.
   Record in `LICENSES.md`.
2. **TotalSegmentator `total` weights licence** (§7): confirm the licence of the released weights (the
   spec says CC BY 4.0). Record the citation required in the About screen.
3. **Sony ELF-SR2 with a second display** (§2.8): confirm in Sony's documentation that the SR plugin can
   run while Unity also drives a normal monitor (Display 0). The plugin may expect the app full-screen
   on the SR display; if so the touch monitor needs another design (e.g. a second app or window).
4. **Performance targets** (§5) are goals to measure on the RTX 2070 Max-Q laptop, not guarantees;
   presets get tuned from measurements.
5. **Dev fixtures**: `5 RibWB Standard.nrrd` (unknown origin) and `anonymized_20261019` (origin to be
   confirmed) are development data only and are never committed or shipped. Scans are git-ignored.
