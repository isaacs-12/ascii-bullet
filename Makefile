.PHONY: build clean install-deps test help

# Variables
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
BUILD_DIR = build
DIST_DIR = dist
TIMESTAMP = $(shell date +%Y%m%d_%H%M%S)
EXECUTABLE_NAME = ascii-bullet-$(TIMESTAMP)
RELEASE_DIR = $(DIST_DIR)/$(EXECUTABLE_NAME)

help:
	@echo "Available targets:"
	@echo "  build          - Build executable with timestamp"
	@echo "  clean          - Remove build artifacts"
	@echo "  install-deps   - Install PyInstaller in virtual environment"
	@echo "  test           - Run unit tests"
	@echo "  help           - Show this help message"

install-deps:
	@echo "Installing PyInstaller and Pillow..."
	$(PIP) install pyinstaller pillow

build: install-deps
	@echo "Building executable: $(EXECUTABLE_NAME)"
	@mkdir -p $(BUILD_DIR) $(DIST_DIR) $(RELEASE_DIR)
	@if [ -f "src/assets/bllthll.icns" ]; then \
		ICON_FLAG="--icon src/assets/bllthll.icns"; \
	elif [ -f "src/assets/bllthll.png" ]; then \
		ICON_FLAG="--icon src/assets/bllthll.png"; \
	else \
		ICON_FLAG=""; \
	fi; \
	$(PYTHON) -m PyInstaller \
		--name $(EXECUTABLE_NAME) \
		--onefile \
		--windowed \
		$$ICON_FLAG \
		--add-data "src/assets:src/assets" \
		--hidden-import pygame \
		--hidden-import RestrictedPython \
		--hidden-import src.core \
		--hidden-import src.unix \
		--hidden-import src.states \
		--collect-all pygame \
		--collect-all RestrictedPython \
		--clean \
		main.py
	@echo "Organizing build artifacts..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		if [ -d "$(DIST_DIR)/$(EXECUTABLE_NAME).app" ]; then \
			mv "$(DIST_DIR)/$(EXECUTABLE_NAME).app" "$(RELEASE_DIR)/"; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		if [ -f "$(DIST_DIR)/$(EXECUTABLE_NAME)" ]; then \
			mv "$(DIST_DIR)/$(EXECUTABLE_NAME)" "$(RELEASE_DIR)/"; \
		fi; \
	else \
		if [ -f "$(DIST_DIR)/$(EXECUTABLE_NAME).exe" ]; then \
			mv "$(DIST_DIR)/$(EXECUTABLE_NAME).exe" "$(RELEASE_DIR)/"; \
		fi; \
	fi
	@if [ -f "$(EXECUTABLE_NAME).spec" ]; then \
		mv "$(EXECUTABLE_NAME).spec" "$(RELEASE_DIR)/"; \
	fi
	@echo ""
	@echo "Build complete! All files are in:"
	@echo "  $(RELEASE_DIR)/"
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "  Run with: open $(RELEASE_DIR)/$(EXECUTABLE_NAME).app"; \
	elif [ "$$(uname)" = "Linux" ]; then \
		echo "  Run with: $(RELEASE_DIR)/$(EXECUTABLE_NAME)"; \
	else \
		echo "  Run with: $(RELEASE_DIR)/$(EXECUTABLE_NAME).exe"; \
	fi
	@echo ""

test:
	@echo "Running unit tests..."
	$(PYTHON) -m unittest discover -s src/tests -p "test_*.py" -v
	@echo ""
	@echo "Tests complete!"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	rm -rf *.spec
	@echo "Clean complete!"
