#!/bin/bash
# k8s/istio/install-istio.sh
# Istio Service Mesh Installation Script

set -e

echo "=== Istio Service Mesh Installation for CQOx ==="
echo

# 1. Install Istio CLI (istioctl)
if ! command -v istioctl &> /dev/null; then
    echo "[1/5] Installing istioctl..."
    curl -L https://istio.io/downloadIstio | sh -
    cd istio-*
    export PATH=$PWD/bin:$PATH
    cd ..
else
    echo "[1/5] istioctl already installed"
fi

# 2. Install Istio with demo profile
echo "[2/5] Installing Istio with demo profile..."
istioctl install --set profile=demo -y

# 3. Enable automatic sidecar injection
echo "[3/5] Enabling automatic sidecar injection for default namespace..."
kubectl label namespace default istio-injection=enabled --overwrite

# 4. Verify installation
echo "[4/5] Verifying Istio installation..."
kubectl get pods -n istio-system

# 5. Apply CQOx Istio configuration
echo "[5/5] Applying CQOx Istio configuration..."
kubectl apply -f k8s/istio/istio-config.yaml

echo
echo "=== Istio Service Mesh Installation Complete ==="
echo
echo "Next steps:"
echo "1. Deploy CQOx services: kubectl apply -f k8s/deployments/"
echo "2. Check Istio dashboard: istioctl dashboard kiali"
echo "3. Check Jaeger tracing: istioctl dashboard jaeger"
echo "4. Check Grafana metrics: istioctl dashboard grafana"
