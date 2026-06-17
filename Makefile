.PHONY: pre-commit-install install lint format check

# 🔍 Set up pre-commit hooks
pre-commit-install:
	pre-commit uninstall && \
	pre-commit install && \
	pre-commit autoupdate && \
	pre-commit install --hook-type commit-msg -f

# 📦 Install dev dependencies and hooks
# Note: pre-commit is expected to be installed system-wide via `brew install pre-commit`
install:
	command -v pre-commit >/dev/null 2>&1 || brew install pre-commit
	pip install -r requirements-dev.txt
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
