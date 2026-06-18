.PHONY: pre-commit-install install lint format check

# 🔍 Set up pre-commit hooks
pre-commit-install:
	pre-commit install --install-hooks && \
	pre-commit install --hook-type commit-msg -f

# 📦 Install dev dependencies and hooks
install:
	python -m pip install -r requirements-dev.txt
	$(MAKE) pre-commit-install

# 🧹 Lint and auto-fix
lint:
	ruff check --fix .

# 🎨 Format code
format:
	ruff format .

# ✅ Run all pre-commit hooks across the repo
check:
	pre-commit run --all-files
