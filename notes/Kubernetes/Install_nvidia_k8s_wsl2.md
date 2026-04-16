# Failed on k3s

Where installed the NVIDIA toolkit and configured CDI. It listens on `/run/containerd/containerd.sock`, k3s failed because it is using K3s binary containerd. 

I have also tested the following procedures for k3s using the system's containerd instead of the k3s's out-of-the-box containerd. However, I have not figured out how it failed to detect the GPU or how to apply the CDI configurations for k3s. In one of the k3s Github issue, it is mentioned k3s can indeed use an external containerd runtime but other binary should be installed manually. 

If anyone have suceeded connecting your GPU on k3s, let us keep in touch if you don't mind sharing. Any information woudl be appreciated.


# Installing Nvidia CUDA Toolkit on WSL2 for Kubernetes k8s

Reference
- https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl
- https://docs.nvidia.com/cuda/wsl-user-guide/index.html#getting-started-with-cuda-on-wsl

> [!Important] 
> The CUDA driver installed on Windows host will be stubbed inside the WSL 2 as `libcuda.so`, therefore **users must not install any NVIDIA GPU Linux driver within WSL 2**.

1. Remove the old GPG key
``` bash
sudo apt-key del 7fa2af80
```
![[capture-20260314-0005.png]]

2. Install CUDA Toolkit using the latest [WSL-Ubuntu Package](https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu&target_version=2.0&target_type=deb_local)
```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin
sudo mv cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/13.2.0/local_installers/cuda-repo-wsl-ubuntu-13-2-local_13.2.0-1_amd64.deb
sudo dpkg -i cuda-repo-wsl-ubuntu-13-2-local_13.2.0-1_amd64.deb
sudo cp /var/cuda-repo-wsl-ubuntu-13-2-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda-toolkit-13-2
```

	Add cuda toolkit to PATH, change version if needed.
``` bash
export PATH=/usr/local/cuda-13.2/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-13.2/lib:$LD_LIBRARY_PATH
```

3. Reboot 
`sudo reboot`

4. Verify GPU by `nvidia-smi`
![[capture-20260314-0202.png]]

---
# Install NVIDIA Container Toolkit on WSL2 ubuntu for Kubernetes k8s

Reference https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html

```bash
sudo apt-get update && sudo apt-get install -y --no-install-recommends \
   ca-certificates \
   curl \
   gnupg2
   
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
sudo apt-get update

export NVIDIA_CONTAINER_TOOLKIT_VERSION=1.19.0-1
  sudo apt-get install -y \
      nvidia-container-toolkit=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
      nvidia-container-toolkit-base=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
      libnvidia-container-tools=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
      libnvidia-container1=${NVIDIA_CONTAINER_TOOLKIT_VERSION}
```

## Configure NVIDIA Container Toolkit for Kubernetes k8s

Reference https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#configuration

```bash
# To generate a containerd config file at /etc/containerd/conf.d/99.nvidia.toml
sudo nvidia-ctk runtime configure --runtime=containerd --set-as-default

sudo systemctl restart containerd
```

## Verify NVIDIA Container Toolkit

``` bash
sudo nvidia-container-cli info
```


## If missing CDI files or configs
Reconfigure NVIDIA Container Toolkit when got this error message: 
```
I0320 20:55:01.936647       1 main.go:369] Retrieving plugins.
E0320 20:55:01.936717       1 factory.go:113] Incompatible strategy detected auto
E0320 20:55:01.936738       1 factory.go:114] If this is a GPU node, did you configure the NVIDIA Container Toolkit?
E0320 20:55:01.936742       1 factory.go:115] You can check the prerequisites at: https://github.com/NVIDIA/k8s-device-plugin#prerequisites
E0320 20:55:01.936744       1 factory.go:116] You can learn how to set the runtime at: https://github.com/NVIDIA/k8s-device-plugin#quick-start
E0320 20:55:01.936746       1 factory.go:117] If this is not a GPU node, you should set up a toleration or nodeSelector to only deploy this plugin on GPU nodes     
E0320 20:55:01.950610       1 main.go:185] error starting plugins: error getting plugins: unable to create plugins: failed to construct resource managers: invalid device discovery strategy
```

---

# Install NVIDIA Device Plugin in k8s

Reference [https://github.com/NVIDIA/k8s-device-plugin](https://github.com/NVIDIA/k8s-device-plugin)

## (Option 1/2) Deploy via helm

### Install Helm
https://helm.sh/docs/intro/install/
```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4

chmod 700 get_helm.sh

./get_helm.sh
```

## Install nvidia-device-plugin via helm
https://github.com/NVIDIA/k8s-device-plugin#deployment-via-helm
```bash
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm repo update

# Check NVIDIA Device Plugin version
helm search repo nvdp --devel

helm upgrade -i nvdp nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin \
  --create-namespace \
  --version 0.18.2
```
## (Option 2/2) Deploy via yaml
```yaml
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.18.2/deployments/static/nvidia-device-plugin.yml
```

### Label node as GPU node
```bash
# Node label needed for daemonset nvdp-nvidia-device-plugin 
kubectl label nodes desktop-7451qal nvidia.com/gpu.present=true
```

## Troubleshoot nvidia-device-plugin

```bash
sudo journalctl -u k3s | grep -E "level=(error|fatal)"
sudo crictl ps | grep nvidia-device-plugin
```

### If daemonset is not populating pod
Check node taint. By default, your cluster will not schedule Pods on the control plane nodes for security reasons.
```bash
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
```

Check if the GPU node has label `nvidia.com/gpu.present=true`
```
kubectl label node NODE_NAME nvidia.com/gpu.present=true --overwrite
```


# Install GPU Operator for Kubernetes k8s

Since GPU Operator is not designed for WSL2, the container toolkit daemonset will most likely conflict with your windows driver and will not work.
The CUDA driver installed on Windows host will be stubbed inside the WSL 2 as libcuda.so, therefore users must not install any NVIDIA GPU Linux driver within WSL 2. which is also warned by Nvidia.   

The following workaround is referenced from: https://github.com/NVIDIA/gpu-operator/issues/318#issuecomment-3523976737

1. Add the NVIDIA Helm repository

``` bash
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia \
    && helm repo update
```

2. On each WSL2 node, update the host root filesystem so that its mount propagation is shared.

``` bash
sudo mount --make-rshared /
```

3. Install the latest gpu-operator helm chart with below options. Note, additional options may be required depending on what k8s flavor you have installed.
   
	Set KUBECONFIG for helm's visibility. Error msg: `cluster reachability check failed: kubernetes cluster unreachable`

``` bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

helm upgrade -install gpu-operator nvidia/gpu-operator \
  -n gpu-operator --create-namespace \
  --set driver.enabled=false \
  --set dcgmExporter.enabled=false \
  --set cdi.enabled=true \
  --set "config.map.defaultConfig.flags.failOnInitError=false"
```

![[capture-20260313-2348.png]]

4. Create a custom NodeFeatureRule that ensures all WSL2 nodes get labeled with `feature.node.kubernetes.io/pci-10de.present=true`. The NodeFeatureRule ensures that any new GPU WSL2 node added to the cluster will automatically get labeled

``` bash
$ kubectl apply -f - <<EOF
apiVersion: nfd.k8s-sigs.io/v1alpha1
kind: NodeFeatureRule
metadata:
  name: wsl2-nvidia-gpu-rule
spec:
  rules:
  - name: dxgkrnl-module
    labels:
      dxgkrnl: "true"
      pci-10de.present: "true"
    matchFeatures:
    - feature: kernel.enabledmodule
      matchExpressions:
        "dxgkrnl":
          op: Exists
EOF
```

After installation, the GPU Operator and its operands should be up and running.
![[capture-20260314-1823.png]]

	## Verification

``` bash
kubectl get node desktop-7451qal -o jsonpath='{.status.allocatable}'
```
> `nvidia.com/gpu` is expected in the output, otherwise your YAML will never schedule.

Your GPU CDI should be found here, no changes needed.
```
/var/run/cdi/k8s.device-plugin.nvidia.com-gpu.json
```
