.PHONY: build clean clean-all install-deps test help

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
	@echo "  build          - Build executable with timestamp (preserves old builds)"
	@echo "  clean          - Remove build artifacts only (preserves distributions)"
	@echo "  clean-all      - Remove ALL build artifacts and distributions"
	@echo "  install-deps   - Install PyInstaller in virtual environment"
	@echo "  test           - Run unit tests"
	@echo "  help           - Show this help message"

install-deps:
	@echo "Installing PyInstaller and Pillow..."
	$(PIP) install pyinstaller pillow

build: install-deps
	@echo "Building executable: $(EXECUTABLE_NAME)"
	@echo "Release directory: $(RELEASE_DIR)"
	@if [ -d "$(RELEASE_DIR)" ]; then \
		echo "Warning: Release directory already exists, but continuing..."; \
	fi
	@echo "Checking for save files (should not be bundled)..."
	@if [ -f "save.json" ] || [ -d ".ascii-bullet" ]; then \
		echo "WARNING: Save files found in project directory!"; \
		echo "These should not be here and will NOT be bundled."; \
		echo "Save files are user-specific and stored in ~/.ascii-bullet/"; \
	fi
	@mkdir -p $(BUILD_DIR) $(DIST_DIR) $(RELEASE_DIR)
	@echo "Preparing icon..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		if [ -f "src/assets/bllthll.png" ] && [ ! -f "src/assets/bllthll.icns" ]; then \
			echo "Converting PNG to ICNS for macOS..."; \
			ICONSET_DIR="/tmp/bllthll.iconset"; \
			mkdir -p $$ICONSET_DIR; \
			$(PYTHON) -c "from PIL import Image; \
			import os; \
			img = Image.open('src/assets/bllthll.png'); \
			sizes = [16, 32, 128, 256, 512, 1024]; \
			for s in sizes: \
				img.resize((s, s), Image.Resampling.LANCZOS).save(f'$$ICONSET_DIR/icon_{s}x{s}.png'); \
				img.resize((s*2, s*2), Image.Resampling.LANCZOS).save(f'$$ICONSET_DIR/icon_{s}x{s}@2x.png');"; \
			iconutil -c icns $$ICONSET_DIR -o src/assets/bllthll.icns; \
			rm -rf $$ICONSET_DIR; \
			echo "ICNS file created: src/assets/bllthll.icns"; \
		fi; \
		if [ -f "src/assets/bllthll.icns" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.icns"; \
			echo "Using ICNS icon file for macOS"; \
		elif [ -f "src/assets/bllthll.png" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.png"; \
			echo "Using PNG icon file (will be converted)"; \
		else \
			ICON_FLAG=""; \
			echo "No icon file found"; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		if [ -f "src/assets/bllthll.ico" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.ico"; \
			echo "Using ICO icon file for Linux"; \
		elif [ -f "src/assets/bllthll.png" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.png"; \
			echo "Using PNG icon file for Linux"; \
		else \
			ICON_FLAG=""; \
			echo "No icon file found"; \
		fi; \
	else \
		if [ -f "src/assets/bllthll.png" ] && [ ! -f "src/assets/bllthll.ico" ]; then \
			echo "Converting PNG to ICO for Windows..."; \
			$(PYTHON) -c "from PIL import Image; \
			img = Image.open('src/assets/bllthll.png'); \
			sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]; \
			img.save('src/assets/bllthll.ico', format='ICO', sizes=sizes);"; \
			echo "ICO file created: src/assets/bllthll.ico"; \
		fi; \
		if [ -f "src/assets/bllthll.ico" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.ico"; \
			echo "Using ICO icon file for Windows"; \
		elif [ -f "src/assets/bllthll.png" ]; then \
			ICON_FLAG="--icon src/assets/bllthll.png"; \
			echo "Using PNG icon file (will be converted)"; \
		else \
			ICON_FLAG=""; \
			echo "No icon file found"; \
		fi; \
	fi
	@TMP_DIST_DIR="$(DIST_DIR)/tmp-$(TIMESTAMP)"; \
	mkdir -p $$TMP_DIST_DIR; \
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
		--workpath $(BUILD_DIR)/pyinstaller-$(TIMESTAMP) \
		--distpath $$TMP_DIST_DIR \
		--noconfirm \
		--clean \
		main.py
	@echo "Organizing build artifacts..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		if [ -d "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME).app" ]; then \
			mv "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME).app" "$(RELEASE_DIR)/"; \
			echo "Fixing app bundle icon..."; \
			APP_PATH="$(RELEASE_DIR)/$(EXECUTABLE_NAME).app"; \
			if [ -f "src/assets/bllthll.icns" ]; then \
				cp "src/assets/bllthll.icns" "$$APP_PATH/Contents/Resources/bllthll.icns"; \
				$(PYTHON) -c "import plistlib; \
import sys; \
with open('$$APP_PATH/Contents/Info.plist', 'rb') as f: \
	plist = plistlib.load(f); \
plist['CFBundleIconFile'] = 'bllthll'; \
with open('$$APP_PATH/Contents/Info.plist', 'wb') as f: \
	plistlib.dump(plist, f)"; \
				touch "$$APP_PATH"; \
				echo "Icon set in Info.plist and app bundle refreshed"; \
			fi; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		if [ -f "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME)" ]; then \
			mv "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME)" "$(RELEASE_DIR)/"; \
		fi; \
	else \
		if [ -f "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME).exe" ]; then \
			mv "$(DIST_DIR)/tmp-$(TIMESTAMP)/$(EXECUTABLE_NAME).exe" "$(RELEASE_DIR)/"; \
		fi; \
	fi
	@rm -rf "$(DIST_DIR)/tmp-$(TIMESTAMP)"
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
	@echo "Previous builds are preserved in:"
	@ls -1d $(DIST_DIR)/ascii-bullet-* 2>/dev/null | head -5 || echo "  (no previous builds found)"
	@echo ""

test:
	@echo "Running unit tests..."
	$(PYTHON) -m unittest discover -s src/tests -p "test_*.py" -v
	@echo ""
	@echo "Tests complete!"

clean:
	@echo "Cleaning build artifacts (BUILD_DIR only, preserving distributions)..."
	rm -rf $(BUILD_DIR)
	rm -rf *.spec
	@echo "Clean complete! Distributions in $(DIST_DIR) are preserved."

clean-all:
	@echo "Cleaning ALL build artifacts and distributions..."
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	rm -rf *.spec
	@echo "Clean complete!"
