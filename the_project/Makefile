# ==========================================
# The Project Makefile — todo-app + todo-backend
# ==========================================

CLUSTER ?= k3s-default

# Образы и версии (ДЕРЖИ СИНХРОННО с deployment.yaml!)
IMG_TODO    ?= todo-app:1.5
IMG_BACKEND ?= todo-backend:1.0

# Пути к манифестам
MANIFESTS_COMMON  := manifests
MANIFESTS_TODO    := todo-app/manifests
MANIFESTS_BACKEND := todo-backend/manifests

# Пути к исходникам для docker build
SRC_TODO    := todo-app
SRC_BACKEND := todo-backend

# Все деплойменты проекта
DEPLOYMENTS := todo-app-deployment todo-backend-deployment

# ==========================================
# Цели
# ==========================================
.PHONY: all build import deploy delete restart update clean setup-node logs help

# Первый запуск: всё сразу
all: setup-node build import deploy

# 1. Сборка обоих образов
build:
	@echo "🔨 Building Docker images..."
	docker build -t $(IMG_TODO) $(SRC_TODO)
	docker build -t $(IMG_BACKEND) $(SRC_BACKEND)
	@echo "✅ Build complete."

# 2. Импорт обоих образов в k3d
import:
	@echo "📦 Importing images to k3d '$(CLUSTER)'..."
	k3d image import $(IMG_TODO) --cluster $(CLUSTER)
	k3d image import $(IMG_BACKEND) --cluster $(CLUSTER)
	@echo "✅ Import complete."

# 3. Подготовка ноды для local PV
setup-node:
	@docker exec $(CLUSTER)-agent-0 mkdir -p /tmp/kube 2>/dev/null || true

# 4. Применение манифестов: сначала бэкенд, потом фронтенд, потом общее (ingress)
deploy:
	@echo "🚀 Applying manifests..."
	kubectl apply -f $(MANIFESTS_BACKEND)/
	kubectl apply -f $(MANIFESTS_TODO)/
	kubectl apply -f $(MANIFESTS_COMMON)/ || true
	@echo "✅ Deploy complete."

# 5. Удаление в обратном порядке
delete:
	@echo "🗑️ Deleting manifests..."
	kubectl delete -f $(MANIFESTS_COMMON)/  --ignore-not-found=true || true
	kubectl delete -f $(MANIFESTS_TODO)/    --ignore-not-found=true || true
	kubectl delete -f $(MANIFESTS_BACKEND)/ --ignore-not-found=true || true
	@echo "✅ Delete complete."

# 6. Безопасный рестарт всех деплойментов (после смены кода с тем же тегом)
restart:
	@echo "🔄 Restarting deployments..."
	@for dep in $(DEPLOYMENTS); do \
		if kubectl get deployment $$dep >/dev/null 2>&1; then \
			echo "  ⟳ $$dep"; \
			kubectl rollout restart deployment $$dep; \
		else \
			echo "  ⚠️  $$dep not found, skipping."; \
		fi; \
	done
	@echo "✅ Restart complete. Watch: make logs"

# 7. Быстрое обновление тегов без правки YAML (императивный путь)
update:
	@echo "🔁 Patching image tags via kubectl set image..."
	kubectl set image deployment/todo-app-deployment todo-app=$(IMG_TODO)
	kubectl set image deployment/todo-backend-deployment todo-backend=$(IMG_BACKEND)
	kubectl rollout status deployment/todo-app-deployment
	kubectl rollout status deployment/todo-backend-deployment
	@echo "✅ Update complete."

# 8. Очистка локальных образов
clean:
	@echo "🧹 Cleaning local images..."
	docker rmi $(IMG_TODO) $(IMG_BACKEND) --force 2>/dev/null || true
	@echo "✅ Clean complete."

# 9. Логи всех подов проекта
logs:
	kubectl get pods -l 'app in (todo-app, todo-backend)' -o name \
		| xargs -I {} kubectl logs -f {} --all-containers --tail=20

# 10. Справка
help:
	@echo "🛠️  The Project Makefile — available targets:"
	@echo "  make all       - setup-node + build + import + deploy (first run)"
	@echo "  make build     - Build todo-app and todo-backend images"
	@echo "  make import    - Import images into k3d"
	@echo "  make deploy    - Apply manifests (backend → app → ingress)"
	@echo "  make delete    - Delete manifests (safe, reverse order)"
	@echo "  make restart   - Restart existing deployments (same tag)"
	@echo "  make update    - Retag deployments via kubectl set image"
	@echo "  make clean     - Remove local Docker images"
	@echo "  make logs      - Tail logs of todo-app and todo-backend pods"
	@echo "  make help      - Show this message"
	@echo ""
	@echo "💡 Workflow:"
	@echo "   First run:    make all"
	@echo "   Code change:  make build import restart"
	@echo "   YAML change:  make deploy"