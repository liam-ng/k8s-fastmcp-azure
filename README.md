# k8s-fastmcp-azure

<img style="width:20%; height:auto;" alt="ezgif com-animated-gif-maker" src="https://github.com/user-attachments/assets/3ba17ad6-7c18-454b-86d3-a0f4a0b3a68c" />

## Overview

Technical notes and manifests for running **Ollama**, **Open WebUI**, and **FastMCP** (with Azure integration) on **Kubernetes**, with a focus on **Windows / WSL2** environments.

## What’s in this repository

- **`k8s/`** — Kustomize bases for FastMCP, storage, and NVIDIA-related configuration.
- **`helm/`** — Helm values and references for ingress, Ollama, Open WebUI, and SearXNG.
- **`notes/`** — Step-by-step install and setup notes (Kubernetes, NVIDIA on WSL2, Ollama).

## Components at a glance

- **FastMCP + Azure** — MCP server deployment and secrets (see `k8s/fastmcp/`).
- **Inference & UI** — Ollama and Open WebUI (Helm charts / values).
- **Ingress** — NGINX Ingress controller configuration.
- **Search** — SearXNG (optional companion service).

## Prerequisites

- A working Kubernetes cluster (local or remote).
- For GPU workloads: NVIDIA drivers and device plugin setup as described in `notes/`.
- Azure app registration details where FastMCP uses Azure APIs (see `k8s/fastmcp/secrets.yaml` patterns).

## Getting started

Apply manifests with Kustomize from the repo root, or install Helm releases using the files under `helm/` once your cluster and namespaces are ready. See `notes/` for environment-specific setup (especially WSL2).

### Table of contents (notes)

| Topic | Notes |
| --- | --- |
| Kubernetes install | [notes/Kubernetes/Install_k8s.md](notes/Kubernetes/Install_k8s.md) |
| NVIDIA + Kubernetes on WSL2 | [notes/Kubernetes/Install_nvidia_k8s_wsl2.md](notes/Kubernetes/Install_nvidia_k8s_wsl2.md) |
| Ollama | [notes/AI/Install_Ollama.md](notes/AI/Install_Ollama.md) |

