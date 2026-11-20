<div align="center">

# VYDRIA

### A local-first foundation for AI video creation

**Create, experiment, and build with video-generation models on hardware you control.**

[Source project](https://github.com/FlashML-org/FreeVideo) · [OpenVDN](https://github.com/OpenVDN) · [Issues](https://github.com/schelaalynn-cell/Vydria/issues)

</div>

---

## What is Vydria?

Vydria is an independently maintained project built from the open-source [FreeVideo](https://github.com/FlashML-org/FreeVideo) codebase. Its starting point is a local inference workflow for MiniMax H3, powered by [Video DeltaNet (VDN)](https://openvdn.github.io/) and designed to make video generation more practical on capable consumer hardware.

The goal is to evolve this foundation into a dependable, extensible video-generation engine: one that can be developed and operated independently, while also serving as the video capability within the broader **Zyvano** AI creative platform.

**Project status:** Vydria is at the foundation and adaptation stage. The inherited FreeVideo functionality is the starting point; Vydria-specific improvements, integrations, releases, and support commitments will be documented here as they are implemented and verified. This repository does not yet claim a separate Vydria release or a completed Zyvano integration.

## Current technical foundation

The upstream codebase provides the following capabilities. Their availability in a Vydria build depends on the inherited implementation and its dependencies:

- **Local video inference** using the VDN-H3 / MiniMax H3 model family.
- **Hardware-adaptive execution** that selects supported compute formats and attention implementations for the available GPU.
- **Memory-conscious inference** using weight streaming, prefetching, and chunked computation.
- **Multimodal conditioning** with text prompts, frame inputs, and image, video, or audio references where supported by the model workflow.
- **ComfyUI integration** for composing and running generation workflows.
- **LoRA workflows** and configurable generation settings supported by the underlying implementation.

Hardware requirements, model availability, operating-system support, and performance vary. Consult the upstream documentation and model terms before attempting to run a workflow.

## Direction

Vydria will be developed around a few engineering priorities:

1. **Reliable inference:** make model execution, memory planning, and hardware compatibility observable and predictable.
2. **Usable workflows:** improve the experience from prompt and reference inputs through preview, generation, editing, and export.
3. **Extensible architecture:** keep model adapters, execution backends, workflow integration, and user-facing interfaces clearly separated.
4. **Reproducibility:** make generation settings, model versions, and workflow metadata easier to inspect and reproduce.
5. **Zyvano integration:** expose video-generation capabilities through a defined interface so Zyvano can orchestrate media creation without tightly coupling its main application to the inference runtime.

These are development goals, not a statement that every capability is already implemented.

## Upstream heritage and attribution

Vydria is derived from **[FlashML-org/FreeVideo](https://github.com/FlashML-org/FreeVideo)**. The upstream project, its contributors, and its history remain acknowledged. This repository is an independent development effort and is not presented as an official FreeVideo release or as endorsed by the upstream maintainers.

The underlying model and research foundations include:

- [OpenVDN / VDN-H3](https://github.com/OpenVDN)
- [Video DeltaNet](https://openvdn.github.io/)
- [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3)
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
- [Hugging Face Diffusers](https://github.com/huggingface/diffusers)
- [SageAttention](https://github.com/thu-ml/SageAttention)

Please consult the upstream repository for the original project history, contributor acknowledgements, research citation, and detailed technical documentation.

## Getting started

Vydria-specific installation instructions and verified release artifacts will be published here when they are ready.

For now, developers examining this codebase should:

1. Review the [upstream FreeVideo README](https://github.com/FlashML-org/FreeVideo#readme) for the inherited setup process and platform-specific guidance.
2. Review the upstream [execution-planning documentation](https://github.com/FlashML-org/FreeVideo/blob/main/docs/execution-planning.md).
3. Confirm that the required model files can be obtained and used under their applicable terms.
4. Treat upstream download links and binaries as **FreeVideo artifacts**, not Vydria releases.

Do not assume that an upstream binary, model package, or installation command is an officially supported Vydria distribution.

## Development and contributions

Development should preserve a clear distinction between inherited upstream behavior and Vydria-specific changes. When proposing a change:

- Describe the problem and intended behavior.
- Include relevant tests or reproducible steps.
- Document hardware, model, and platform assumptions.
- Preserve upstream copyright notices and applicable license terms.
- Avoid claiming performance or compatibility improvements without reproducible evidence.

Use [GitHub Issues](https://github.com/schelaalynn-cell/Vydria/issues) for bugs and development discussions.

## Licensing

The upstream FreeVideo code is released under the [Apache License 2.0](https://github.com/FlashML-org/FreeVideo/blob/main/LICENSE). This project retains applicable upstream license terms and notices. Review the repository's `LICENSE` and any third-party notices before redistributing modified builds.

**Model weights are separately licensed.** The VDN-H3 / MiniMax H3 model weights are subject to the [MiniMax H3 Community License](https://huggingface.co/OpenVDN/vdn-minimax-h3-edge/blob/main/LICENSE), which includes additional use restrictions. The code license does not grant unrestricted rights to model weights or other third-party assets. Check each dependency's and model's current terms independently.

## Research citation

For work based on Video DeltaNet, consult and cite the [Video DeltaNet paper](https://arxiv.org/abs/2609.20744):

```bibtex
@article{xi2026videodeltanet,
  title={Video DeltaNet: A Video-Native Hybrid Attention for Livestream Video Generation},
  author={Xi, Haocheng and Xie, Yiming and Zhao, Hexu and Zhang, Yiwen and Liu, Michael and Creavin, Thomas and Keutzer, Kurt and Li, Xiuyu and Lv, Zhaoyang and Xu, Chenfeng and Feng, Haiwen},
  journal={arXiv preprint arXiv:2609.20744},
  year={2026}
}
```

---

<div align="center">

**Vydria — an independent video-engineering project in development.**

</div>
