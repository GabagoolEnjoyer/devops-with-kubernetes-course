# ==========================================
# The Project Makefile — todo-app
# ==========================================

CLUSTER ?= k3s-default

IMG_TODO ?= todo-app:1.5

MANIFESTS_COMMON := manifests
MANIFESTS_TODO   := todo-app/manifests
SRC_TODO         := todo-app

DEPLOYMENTS := todo-app-deployment

.PHONY: all build import deploy delete restart clean setup-node logs help

all: setup-node build import deploy

build:
	@echo "🔨 Building $(IMG_TODO)..."
	docker build -t $(IMG_TODO) $(SRC_TODO)
	@echo "✅ Build complete."

import:
	@echo "📦 Importing to k3d '$(CLUSTER)'..."
	k3d image import $(IMG_TODO) --cluster $(CLUSTER)
	@echo "✅ Import complete."

setup-node:
	@docker exec $(CLUSTER)-agent-0 mkdir -p /tmp/kube 2>/dev/null || true

deploy:
	@echo "🚀 Applying manifests..."
	kubectl apply -f $(MANIFESTS_COMMON)/ || true
	kubectl apply -f $(MANIFESTS_TODO)/
	@echo "✅ Deploy complete."

delete:
	@echo "🗑️ Deleting manifests..."
	kubectl delete -f $(MANIFESTS_TODO)/   --ignore-not-found=true || true
	kubectl delete -f $(MANIFESTS_COMMON)/ --ignore-not-found=true || true
	@echo "✅ Delete complete."

restart:
	@echo "🔄 Restarting todo-app deployment..."
	@if kubectl get deployment $(DEPLOYMENTS) >/dev/null 2>&1; then \
		kubectl rollout restart deployment $(DEPLOYMENTS); \
	else \
		echo "  ⚠️  $(DEPLOYMENTS) not found, skipping."; \
	fi
	@echo "✅ Restart complete."

clean:
	docker rmi $(IMG_TODO) --force 2>/dev/null || true

logs:
	kubectl get pods -l app=todo-app -o name \
		| xargs -I {} kubectl logs -f {} --all-containers --tail=20

help:
	@echo "🛠️  The Project Makefile — available targets:"
	@echo "  make all       - setup-node + build + import + deploy"
	@echo "  make build     - Build todo-app image"
	@echo "  make import    - Import image into k3d"
	@echo "  make deploy    - Apply manifests"
	@echo "  make delete    - Delete manifests (safe)"
	@echo "  make restart   - Restart todo-app deployment"
	@echo "  make clean     - Remove local image"
	@echo "  make logs      - Tail todo-app pod logs"
	@echo "  make help      - Show this message"