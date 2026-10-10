<p align="center">
  <img src="assets/streetworld-logo.svg" alt="StreetWorld logo" width="900">
</p>

# StreetWorld

![Project page](https://img.shields.io/badge/Project%20page-coming%20soon-grey?logo=googlechrome&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-coming%20soon-grey?logo=huggingface)
![arXiv](https://img.shields.io/badge/arXiv-coming%20soon-grey?logo=arxiv)

🚗 **What is StreetWorld?** StreetWorld is a high-fidelity, extensible closed-loop autonomous driving benchmark. It provides over 1,000 dynamic Gaussian splatting scene assets reconstructed from [nuScenes](https://www.nuscenes.org/) and [Waymo](https://waymo.com/open/), and integrates [NuRec](https://huggingface.co/datasets/nvidia/PhysicalAI-Autonomous-Vehicles-NuRec) assets for closed-loop evaluation of AD policies. **Its highly extensible design gives the community the freedom to customize evaluation configurations and even integrate an unlimited number of scene assets.**

🎯 **Why is it important?** Open-loop trajectory metrics cannot measure how an AD policy's actions change subsequent observations or how errors accumulate over successive decisions. Closed-loop evaluation in synthetic environments also introduces a domain gap between simulation and real driving. AD policy evaluation therefore requires a **fully closed-loop**, **high-fidelity**, **large-scale**, and **physically correct** driving simulator.

🛠️ **How to use it?** StreetWorld follows Gym's environment design: AD policies interact through `reset()` and `step(action)` for training and evaluation. Users can also drive with keyboard controls in a browser. Rendering backends, observations, policies, and simulation objects have separate interfaces, so users can replace or extend them for new scenes, cameras, and AD policies.

<video src="assets/promo/streetworld-opening-preview.mp4" controls width="100%"></video>

[Documentation](documentation/DOCUMENTATION_EN.md) · [文档](documentation/DOCUMENTATION_ZH.md) · [Installation](documentation/en/getting-started/installation.md#section-1-1) · [Quick start](documentation/en/getting-started/web-controller.md#section-1-2)

## 🗓️ Release roadmap

- [ ] Release StreetWorld source code
- [ ] Release 2 Hz and 10 Hz evaluation results on nuScenes
- [ ] Release nuScenes scene assets
- [ ] Release 2 Hz and 10 Hz evaluation results on Waymo
- [ ] Release Waymo scene assets
- [ ] Release the paper

## 🗂️ Current assets

| Dataset | Scenes | Storage size | HD maps | Scene duration |
| --- | ---: | --- | --- | --- |
| [nuScenes](https://www.nuscenes.org/) | 660 | TBD | ✓ | 20 s |
| [Waymo](https://waymo.com/open/) | TBD | TBD | ✓ | 20 s |
| [NuRec](https://huggingface.co/datasets/nvidia/PhysicalAI-Autonomous-Vehicles-NuRec) | 923 | TBD | ✓ | 20 s |

## 🏆 Benchmark leaderboard

### nuScenes · 2 Hz

| Rank | AD policy | NC ↑ (%) | DAC ↑ (%) | TTC ↑ (%) | COM ↑ (%) | RC ↑ (%) | RE ↑ (m/s) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | [ST-P3](https://github.com/OpenDriveLab/ST-P3) | 51.67 | 95.13 | 46.77 | 95.74 | 59.36 | 3.76 |
| 2 | [OpenDriveVLA](https://github.com/DriveVLA/OpenDriveVLA) | 60.30 | 90.87 | 36.70 | 99.52 | 56.89 | 5.48 |
| 3 | [SparseDrive](https://github.com/swc-17/SparseDrive) | 50.15 | 95.05 | 39.90 | 97.38 | 55.67 | 3.87 |
| 4 | [DiffusionDrive](https://github.com/hustvl/DiffusionDrive) | 46.82 | 95.48 | 46.12 | 98.09 | 53.54 | 3.55 |
| 5 | [Epona](https://github.com/Kevin-thu/Epona) | 74.39 | 85.16 | 36.07 | 96.98 | 53.23 | 5.56 |
| 6 | [UniAD](https://github.com/OpenDriveLab/UniAD) | 60.30 | 91.19 | 36.62 | 99.18 | 53.19 | 8.31 |
| 7 | [MomAD](https://github.com/adept-thu/MomAD) | 54.70 | 92.09 | 37.98 | 96.15 | 51.91 | 4.25 |
| 8 | [VAD](https://github.com/hustvl/VAD) | 62.58 | 90.24 | 38.92 | 98.82 | 48.37 | 7.08 |
| 9 | [GenAD](https://github.com/wzzheng/GenAD) | 58.94 | 90.69 | 29.14 | 99.53 | 48.11 | 8.01 |
| 10 | [Latent TransFuser](https://github.com/autonomousvision/transfuser) | 49.85 | 87.53 | 38.69 | 99.43 | 37.97 | 3.96 |
| — | [AutoVLA](https://github.com/ucla-mobility/AutoVLA) | — | — | — | — | — | — |
| — | [OpenEMMA GPT](https://github.com/taco-group/OpenEMMA) | — | — | — | — | — | — |
| — | [OpenEMMA Qwen](https://github.com/taco-group/OpenEMMA) | — | — | — | — | — | — |
| — | [OpenEMMA LLaVA](https://github.com/taco-group/OpenEMMA) | — | — | — | — | — | — |
| — | [OpenEMMA Llama](https://github.com/taco-group/OpenEMMA) | — | — | — | — | — | — |

## 📄 License

StreetWorld code is released under the [Apache 2.0 License](LICENSE.txt).

## 🙏 Acknowledgments
The basis of our implementation builds on [MetaDrive](https://github.com/metadriverse/metadrive)'s simulation framework. Our nuScenes and Waymo assets are reconstructed by [Hierarchy UGP](https://github.com/LiAutoAD/HierarchyUGP).

We thank the creators of [nuScenes](https://www.nuscenes.org/) and the [Waymo Open Dataset](https://waymo.com/open/) for providing the driving recordings, annotations, and HD maps used to construct our scene assets. We thank NVIDIA for the [NuRec](https://huggingface.co/datasets/nvidia/PhysicalAI-Autonomous-Vehicles-NuRec) reconstructed driving scenes and rendering service.

We also thank the authors of the AD policies for releasing their code and model weights. Their code allows us to integrate these AD policies into StreetWorld and compared under a common closed-loop evaluation protocol.

## 📚 Citation
