# ==========================================
# Practice Makefile — сборка и деплой practice/*
# ==========================================

CLUSTER ?= k3s-default

# Образы и их версии (синхронизируй с deployment.yaml)
IMG_WRITER   ?= writer:1.1
IMG_READER   ?= reader:1.4
IMG_PINGPONG ?= pingpong:1.5

# Пути к манифестам (относительно practice/)
MANIFESTS_COMMON   := manifests
MANIFESTS_LOG      := log_output/manifests
MANIFESTS_PINGPONG := pingpong/manifests

# Пути к исходникам (для docker build)
SRC_WRITER   := log_output/writer
SRC_READER   := log_output/reader
SRC_PINGPONG := pingpong

# Все деплойменты practice (для рестарта/проверки)
DEPLOYMENTS := log-output-deployment pingpong-deployment

# ==========================================
# Цели
# ==========================================
.PHONY: all build import deploy delete restart clean setup-node logs help

# Дефолтная цель
all: setup-node build import deploy

# 1. Сборка образов
build:
	@echo "🔨 Building Docker images..."
	docker build -t $(IMG_WRITER)   $(SRC_WRITER)
	docker build -t $(IMG_READER)   $(SRC_READER)
	docker build -t $(IMG_PINGPONG) $(SRC_PINGPONG)
	@echo "✅ Build complete."

# 2. Импорт в k3d
import:
	@echo "📦 Importing images to k3d cluster '$(CLUSTER)'..."
	k3d image import $(IMG_WRITER)   --cluster $(CLUSTER)
	k3d image import $(IMG_READER)   --cluster $(CLUSTER)
	k3d image import $(IMG_PINGPONG) --cluster $(CLUSTER)
	@echo "✅ Import complete."

# 3. Подготовка ноды для local PV (создаёт /tmp/kube на k3d-agent)
setup-node:
	@echo "📂 Ensuring /tmp/kube exists on k3d node..."
	@docker exec $(CLUSTER)-agent-0 mkdir -p /tmp/kube 2>/dev/null || \
		echo "⚠️  Node $(CLUSTER)-agent-0 not found; create /tmp/kube manually"
	@echo "✅ Node ready."

# 4. Применение манифестов (порядок важен: PV/PVC → сервисы → ingress)
deploy:
	@echo "🚀 Applying manifests..."
	kubectl apply -f $(MANIFESTS_COMMON)/
	kubectl apply -f $(MANIFESTS_LOG)/
	kubectl apply -f $(MANIFESTS_PINGPONG)/
	@echo "✅ Deploy complete."

# 5. Удаление манифестов (обратный порядок, безопасно к отсутствию)
delete:
	@echo "🗑️ Deleting manifests..."
	kubectl delete -f $(MANIFESTS_PINGPONG)/ --ignore-not-found=true || true
	kubectl delete -f $(MANIFESTS_LOG)/      --ignore-not-found=true || true
	kubectl delete -f $(MANIFESTS_COMMON)/   --ignore-not-found=true || true
	@echo "✅ Delete complete."

# 6. Безопасный рестарт всех деплойментов (не падает, если деплоймента ещё нет)
restart:
	@echo "🔄 Restarting deployments to pick up new images..."
	@for dep in $(DEPLOYMENTS); do \
		if kubectl get deployment $$dep >/dev/null 2>&1; then \
			echo "  ⟳ Restarting $$dep..."; \
			kubectl rollout restart deployment $$dep; \
		else \
			echo "  ⚠️  $$dep not found, skipping."; \
		fi; \
	done
	@echo "✅ Restart complete. Watch pods with: make logs"

# 7. Локальная очистка образов
clean:
	@echo "🧹 Cleaning up local Docker images..."
	docker rmi $(IMG_WRITER) $(IMG_READER) $(IMG_PINGPONG) --force 2>/dev/null || true
	@echo "✅ Clean complete."

# 8. Логи всех practice-подов в реальном времени
logs:
	kubectl get pods -l 'app in (log-output, pingpong)' -o name \
		| xargs -I {} kubectl logs -f {} --all-containers --tail=20

# 9. Справка
help:
	@echo "🛠️  Practice Makefile — available targets:"
	@echo "  make all         - setup-node + build + import + deploy (first run)"
	@echo "  make build       - Build writer, reader, pingpong images"
	@echo "  make import      - Import images into k3d cluster"
	@echo "  make setup-node  - Create /tmp/kube on k3d agent node (for PV)"
	@echo "  make deploy      - Apply all manifests (PV/PVC, services, ingress)"
	@echo "  make delete      - Delete all manifests (safe, order-aware)"
	@echo "  make restart     - Restart existing deployments (after code change)"
	@echo "  make clean       - Remove local Docker images"
	@echo "  make logs        - Tail logs from all practice pods"
	@echo "  make help        - Show this message"
	@echo ""
	@echo "💡 Typical workflow:"
	@echo "   First run:   make all"
	@echo "   Code change: make build import restart"
	@echo "   YAML change: make deploy"