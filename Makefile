# ==========================================
# Переменные конфигурации
# ==========================================
CLUSTER ?= k3s-default

# Образы и их версии
IMG_WRITER ?= writer:1.0
IMG_READER ?= reader:1.0
IMG_PINGPONG ?= pingpong:1.0
IMG_TODO ?= todo-app:1.1

# Пути к манифестам (обновлены под новую структуру)
MANIFESTS_PRACTICE := practice/manifests
MANIFESTS_LOG := practice/log_output/manifests
MANIFESTS_PINGPONG := practice/pingpong/manifests
MANIFESTS_TODO := the_project/todo-app/manifests
MANIFESTS_THE_PROJECT := the_project/manifests

# Список всех деплойментов для безопасного рестарта
DEPLOYMENTS := log-output-deployment pingpong-deployment todo-app-deployment

# ==========================================
# Основные цели
# ==========================================
.PHONY: all build import deploy delete restart clean help logs

# Цель по умолчанию: делает всё сразу
all: build import deploy

# 1. Сборка всех Docker-образов
build:
	@echo "🔨 Building Docker images..."
	docker build -t $(IMG_WRITER) ./practice/log_output/writer
	docker build -t $(IMG_READER) ./practice/log_output/reader
	docker build -t $(IMG_PINGPONG) ./practice/pingpong
	docker build -t $(IMG_TODO) ./the_project/todo-app
	@echo "✅ Build complete."

# 2. Импорт образов в кластер k3d
import:
	@echo "📦 Importing images to k3d cluster '$(CLUSTER)'..."
	k3d image import $(IMG_WRITER) --cluster $(CLUSTER)
	k3d image import $(IMG_READER) --cluster $(CLUSTER)
	k3d image import $(IMG_PINGPONG) --cluster $(CLUSTER)
	k3d image import $(IMG_TODO) --cluster $(CLUSTER)
	@echo "✅ Import complete."

# 3. Применение манифестов (Deploy)
deploy:
	@echo "🚀 Applying Kubernetes manifests..."
	kubectl apply -f $(MANIFESTS_THE_PROJECT)/ || true
	kubectl apply -f $(MANIFESTS_PRACTICE)/
	kubectl apply -f $(MANIFESTS_LOG)/
	kubectl apply -f $(MANIFESTS_PINGPONG)/
	kubectl apply -f $(MANIFESTS_TODO)/
	@echo "✅ Deploy complete."

# 4. Удаление манифестов (Undeploy)
delete:
	@echo "🗑️ Deleting Kubernetes manifests..."
	kubectl delete -f $(MANIFESTS_TODO)/ --ignore-not-found=true
	kubectl delete -f $(MANIFESTS_PINGPONG)/ --ignore-not-found=true
	kubectl delete -f $(MANIFESTS_LOG)/ --ignore-not-found=true
	kubectl delete -f $(MANIFESTS_PRACTICE)/ --ignore-not-found=true
	kubectl delete -f $(MANIFESTS_THE_PROJECT)/ --ignore-not-found=true
	@echo "✅ Delete complete."

# 5. Перезапуск всех Deployment'ов (БЕЗОПАСНЫЙ: не падает, если деплоймента нет)
restart:
	@echo "🔄 Restarting deployments to pick up new images..."
	@for dep in $(DEPLOYMENTS); do \
		if kubectl get deployment $$dep >/dev/null 2>&1; then \
			echo "  ⟳ Restarting $$dep..."; \
			kubectl rollout restart deployment $$dep; \
		else \
			echo "  ⚠️  Deployment $$dep not found, skipping."; \
		fi; \
	done
	@echo "✅ Restart complete. Watch pods with: make logs"

# 6. Очистка локальных образов
clean:
	@echo "🧹 Cleaning up local Docker images..."
	docker rmi $(IMG_WRITER) $(IMG_READER) $(IMG_PINGPONG) $(IMG_TODO) --force || true
	@echo "✅ Clean complete."

# 7. Просмотр логов всех подов в реальном времени
logs:
	kubectl get pods --all-namespaces --field-selector=status.phase=Running -o name | xargs -I {} kubectl logs -f {} --all-containers --tail=20

# 8. Справка
help:
	@echo "🛠️ Available targets:"
	@echo "  make all      - Build, import, and deploy everything"
	@echo "  make build    - Build all Docker images locally"
	@echo "  make import   - Import images into the k3d cluster"
	@echo "  make deploy   - Apply all Kubernetes manifests"
	@echo "  make delete   - Delete all Kubernetes manifests"
	@echo "  make restart  - Safely restart all existing deployments"
	@echo "  make clean    - Remove local Docker images"
	@echo "  make logs     - Tail logs from all running pods"
	@echo "  make help     - Show this help message"