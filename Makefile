# 🔍 Set up pre-commit hooks
pre-commit-install:
	pre-commit uninstall && \
	pre-commit install && \
	pre-commit autoupdate && \
	pre-commit install --hook-type commit-msg -f
