# StreetWorld

StreetWorld is a high-fidelity, extensible closed-loop autonomous driving benchmark. It combines scene rendering with vehicle dynamics simulation using real-world scene assets from nuScenes, Waymo, and NuRec, allowing AD policies to drive continuously in simulation.

Open-loop trajectory errors do not capture how an AD policy accumulates or corrects errors over successive decisions. Closed-loop evaluation in synthetic environments introduces a domain gap between simulated sensor observations and real driving data. StreetWorld reconstructs scenes from recorded driving data and combines high-fidelity rendering with vehicle dynamics to generate subsequent sensor observations from the vehicle's executed state. A common evaluation protocol measures AD policy safety, comfort, and driving progress.

StreetWorld follows Gym's environment design: AD policies interact through `reset()` and `step(action)` for training and evaluation. Users can also drive with keyboard controls in a browser. Separate interfaces for rendering backends, observations, policies, and simulation objects allow these components to be replaced or extended for new scenes, cameras, and AD policies.

[Documentation](documentation/DOCUMENTATION_EN.md) · [简体中文](documentation/DOCUMENTATION_ZH.md) · [Installation](documentation/en/getting-started/index.md#section-1-1) · [Quick start](documentation/en/getting-started/index.md#section-1-2) · [Policy Launcher](documentation/en/launchers/index.md)

## Release events

- [ ] Release StreetWorld source code
- [ ] Release nuScenes scene assets
- [ ] Release Waymo scene assets
- [ ] Release the paper

## Assets

| Dataset | Scenes | Download size | HD maps | Scene duration |
| --- | ---: | --- | --- | --- |
| nuScenes | 850 | TBA | ✓ | 20 s |
| Waymo | 798 | TBA | ✓ | 20 s |
| NuRec | 923 | TBA | ✓ | TBA |

## Benchmark

### nuScenes · 0.5 s

660 scenes with a 0.5 s simulation step, ranked by RC.

| Rank | AD policy | NC ↑ (%) | DAC ↑ (%) | TTC ↑ (%) | COM ↑ (%) | RC ↑ (%) | RE ↑ (m/s) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | [ST-P3](documentation/en/launchers/stp3.md) | 51.67 | 95.13 | 46.77 | 95.74 | 59.36 | 3.76 |
| 2 | [OpenDriveVLA](documentation/en/launchers/opendrivevla.md) | 60.30 | 90.87 | 36.70 | 99.52 | 56.89 | 5.48 |
| 3 | [SparseDrive](documentation/en/launchers/sparsedrive.md) | 50.15 | 95.05 | 39.90 | 97.38 | 55.67 | 3.87 |
| 4 | [DiffusionDrive](documentation/en/launchers/diffusiondrive.md) | 46.82 | 95.48 | 46.12 | 98.09 | 53.54 | 3.55 |
| 5 | [UniAD](documentation/en/launchers/uniad.md) | 60.30 | 91.19 | 36.62 | 99.18 | 53.19 | 8.31 |
| 6 | [VAD](documentation/en/launchers/vad.md) | 62.58 | 90.24 | 38.92 | 98.82 | 48.37 | 7.08 |
| 7 | [GenAD](documentation/en/launchers/genad.md) | 58.94 | 90.69 | 29.14 | 99.53 | 48.11 | 8.01 |
| 8 | [Latent TransFuser](documentation/en/launchers/latent_transfuser.md) | 49.85 | 87.53 | 38.69 | 99.43 | 37.97 | 3.96 |
| — | [MomAD](documentation/en/launchers/momad.md) | — | — | — | — | — | — |
| — | [AutoVLA](documentation/en/launchers/autovla.md) | — | — | — | — | — | — |
| — | [Epona](documentation/en/launchers/epona.md) | — | — | — | — | — | — |
| — | [OpenEMMA GPT](documentation/en/launchers/openemma_gpt.md) | — | — | — | — | — | — |
| — | [OpenEMMA Qwen](documentation/en/launchers/openemma_qwen.md) | — | — | — | — | — | — |
| — | [OpenEMMA LLaVA](documentation/en/launchers/openemma_llava.md) | — | — | — | — | — | — |
| — | [OpenEMMA Llama](documentation/en/launchers/openemma_llama.md) | — | — | — | — | — | — |

## License

## Citation
