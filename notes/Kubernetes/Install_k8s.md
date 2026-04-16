# Installing Kubernetes k8s inside wsl2

In order to use my GPU for AI workload, I basically had 2 options: Docker or Kubernetes in WSL.


## Install a container runtime
Reference https://kubernetes.io/docs/setup/production-environment/container-runtimes/
### Enable IPv4 packet forwarding 
```bash
# sysctl params required by setup, params persist across reboots
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.ipv4.ip_forward = 1
EOF
```
``` bash
# Apply sysctl params without reboot
sudo sysctl --system

# Verify
sysctl net.ipv4.ip_forward
```

On Linux, control groups are used to constrain resources that are allocated to processes.
kubeadm defaults cgroup driver to `systemd` from v1.22: [source](https://kubernetes.io/docs/setup/production-environment/container-runtimes/#systemd-cgroup-driver).

> [!NOTE] 
> If you configure `systemd` (default) as the cgroup driver for the kubelet, you must also configure `systemd` as the cgroup driver for the container runtime. i.e containerd or CRI-O


> [!Warning] 
> Matching the container runtime and kubelet cgroup drivers is required or otherwise the kubelet process will fail.

### Verify containerd container runtime

To use containerd as CRI runtime, look for this config. If files do not exist, go to next step to install containerd.
```
# Default containerd configuration file
ls /etc/containerd/config.toml

# Default CRI socket for containerd 
ls /run/containerd/containerd.sock
```

### (Optional) Install containerd
Reference https://github.com/containerd/containerd/blob/main/docs/getting-started.md
	Update version number if needed
```bash
# uninstall all conflicting packages (incl containerd or runc)
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc | cut -f1)

wget https://github.com/containerd/containerd/releases/download/v2.2.2/containerd-2.2.2-linux-amd64.tar.gz

tar Cxzvf /usr/local containerd-2.2.2-linux-amd64.tar.gz

# download containerd service
cd /usr/lib/systemd/system
wget https://raw.githubusercontent.com/containerd/containerd/main/containerd.service

systemctl daemon-reload
systemctl enable --now containerd
```

### (Optional) Install runc
	Update version number if needed
```bash
cd /usr/local/sbin/runc
wget https://github.com/opencontainers/runc/releases/download/v1.5.0-rc.1/runc.amd64

install -m 755 runc.amd64 /usr/local/sbin/runc
```


### (Optional) Install CNI plugins
	Update version number if needed
```bash
cd $home
wget https://github.com/containernetworking/plugins/releases/download/v1.9.0/cni-plugins-linux-amd64-v1.9.0.tgz

mkdir -p /opt/cni/bin
tar Cxzvf /opt/cni/bin cni-plugins-linux-amd64-v1.9.0.tgz
```

### (Optional) Verify containerd
```bash
ls /etc/containerd/config.toml
ls /var/run/containerd/containerd.sock
sudo systemctl status containerd
```

## Install kubeadm, kubelet & kubectl
Reference https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-using-native-package-management

Reference https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/#installing-runtime

```bash
sudo apt-get update
# apt-transport-https may be a dummy package; if so, you can skip that package
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg

# If the folder `/etc/apt/keyrings` does not exist, it should be created before the curl command, read the note below.
# sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
sudo chmod 644 /etc/apt/keyrings/kubernetes-apt-keyring.gpg # allow unprivileged APT programs to read this keyring

# This overwrites any existing configuration in /etc/apt/sources.list.d/kubernetes.list
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo chmod 644 /etc/apt/sources.list.d/kubernetes.list   # helps tools such as command-not-found to work correctly

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# (Optional) Enable the kubelet service before running kubeadm
sudo systemctl enable --now kubelet

# Verify
kubectl version
kubectl cluster-info
```

---

### If .kube config is missing 
Error Message: `E0326 00:34:41.352576    4711 memcache.go:265] "Unhandled Error" err="couldn't get current server API group list: Get \"http://localhost:8080/api?timeout=32s\": dial tcp 127.0.0.1:8080: connect: connection refused"
The connection to the server localhost:8080 was refused - did you specify the right host or port?`

``` bash
export KUBECONFIG=/etc/kubernetes/admin.conf

# Proper way
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config 
sudo chown $(id -u):$(id -g) $HOME/.kube/config
export KUBECONFIG=$HOME/.kube/config
```

### Regenerate kube config
Error Message: `Error from server (Forbidden): nodes is forbidden: User "kubernetes-admin" cannot list resource "nodes" in API group "" at the cluster scope`

```bash
sudo rm /etc/kubernetes/admin.conf
sudo kubeadm init phase kubeconfig admin

# If still failed, RBAC binding for kubeadm admin group is missing
# Recreate binding expected by new kubeadm admin certs
export KUBECONFIG=/etc/kubernetes/super-admin.conf
kubectl create clusterrolebinding kubeadm:cluster-admins \
  --clusterrole=cluster-admin \
  --group=kubeadm:cluster-admins
```

### If swap is enabled
By default, the kubelet will not start on a node that has swap enabled.

```
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

sudo systemctl restart kubelet
```

### Reset node for init again
Reference https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/#tear-down

``` bash
kubectl drain <node name> --delete-emptydir-data--ignore-daemonsets --force

sudo kubeadm reset 
# if failed
# sudo kubeadm reset -f

iptables -F && iptables -t nat -F && iptables -t mangle -F && iptables -X

kubectl delete node <node name>
```

> [!Important]
> Steps for manual cleanup: https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-reset

#### Cleanup of CNI configuration

CNI plugins use the directory `/etc/cni/net.d` to store their configuration. The `kubeadm reset` command does not cleanup that directory. Leaving the configuration of a CNI plugin on a host can be problematic if the same host is later used as a new Kubernetes node and a different CNI plugin happens to be deployed in that cluster. It can result in a configuration conflict between CNI plugins.

To cleanup the directory, backup its contents if needed and then execute the following command:

```bash
sudo rm -rf /etc/cni/net.d
```

# Result
<img width="1381" height="304" alt="image" src="https://github.com/user-attachments/assets/6af8bee7-e257-43c3-902e-93d4503e4133" />
<img width="483" height="59" alt="image" src="https://github.com/user-attachments/assets/a85b5885-e804-4bb1-8828-c645f3d41d7b" />


---
