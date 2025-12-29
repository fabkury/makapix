# Piskel Customizations

This document details all modifications to be made to the Piskel codebase for Makapix integration.

## File Structure

```
apps/piskel/
├── src/
│   ├── js/
│   │   ├── makapix/                      # NEW: Makapix integration module
│   │   │   └── MakapixIntegration.js
│   │   ├── service/
│   │   │   └── storage/
│   │   │       └── MakapixStorageService.js  # NEW: Makapix export service
│   │   ├── controller/
│   │   │   └── settings/
│   │   │       └── exportimage/
│   │   │           └── GifExportController.js  # MODIFIED
│   │   ├── Constants.js                  # MODIFIED
│   │   └── app.js                        # MODIFIED
│   ├── templates/
│   │   └── settings/
│   │       └── export/
│   │           └── gif.html              # MODIFIED
│   └── piskel-script-list.js             # MODIFIED
└── Dockerfile                            # NEW
```

---

## New Files

### 1. `src/js/makapix/MakapixIntegration.js`

```javascript
/**
 * Makapix Integration Module
 * Handles communication between Piskel and Makapix Club via postMessage
 */
(function () {
  var ns = $.namespace('pskl.makapix');

  // Configuration
  var MAKAPIX_ORIGIN = 'https://dev.makapix.club';
  var TOKEN_CHECK_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
  var TOKEN_REFRESH_BUFFER_SECONDS = 600; // Request refresh 10 min before expiry

  // State
  var accessToken = null;
  var editContext = null;
  var tokenCheckTimer = null;
  var isInitialized = false;

  ns.MakapixIntegration = {
    init: function () {
      if (isInitialized) return;
      isInitialized = true;

      // Listen for messages from Makapix
      window.addEventListener('message', this.handleMessage.bind(this));

      // Notify Makapix that Piskel is ready
      this.sendMessage({ type: 'PISKEL_READY' });

      // Start token expiry checker
      this.startTokenChecker();

      // Check URL for edit mode
      this.checkEditModeUrl();
    },

    handleMessage: function (event) {
      // Validate origin
      if (event.origin !== MAKAPIX_ORIGIN) return;

      var data = event.data;
      if (!data || !data.type) return;

      switch (data.type) {
        case 'MAKAPIX_INIT':
          this.handleInit(data);
          break;
        case 'MAKAPIX_AUTH_REFRESHED':
          this.handleAuthRefreshed(data);
          break;
        case 'MAKAPIX_CLOSE':
          this.handleClose();
          break;
      }
    },

    handleInit: function (data) {
      accessToken = data.accessToken;
      
      if (data.editMode) {
        editContext = data.editMode;
        this.loadArtworkForEditing(data.editMode);
      }

      // Store in session for recovery
      try {
        sessionStorage.setItem('makapix_access_token', accessToken);
        if (editContext) {
          sessionStorage.setItem('makapix_edit_context', JSON.stringify(editContext));
        }
      } catch (e) {
        console.warn('Failed to store Makapix session data:', e);
      }
    },

    handleAuthRefreshed: function (data) {
      accessToken = data.accessToken;
      try {
        sessionStorage.setItem('makapix_access_token', accessToken);
      } catch (e) {
        // Ignore
      }
    },

    handleClose: function () {
      // Clear state and potentially close/navigate
      accessToken = null;
      editContext = null;
      try {
        sessionStorage.removeItem('makapix_access_token');
        sessionStorage.removeItem('makapix_edit_context');
      } catch (e) {
        // Ignore
      }
    },

    loadArtworkForEditing: function (editMode) {
      var img = new Image();
      img.crossOrigin = 'anonymous';
      
      img.onload = function () {
        pskl.app.importService.newPiskelFromImage(img, {
          importType: 'single',
          name: editMode.title || 'Makapix Edit',
          frameSizeX: img.width,
          frameSizeY: img.height,
          smoothing: false
        }, function (piskel) {
          pskl.app.piskelController.setPiskel(piskel);
          // Show edit indicator
          ns.MakapixIntegration.showEditIndicator(editMode.title);
        });
      };

      img.onerror = function () {
        console.error('Failed to load artwork for editing');
        $.publish(Events.SHOW_NOTIFICATION, [{
          content: 'Failed to load artwork for editing',
          hideDelay: 5000
        }]);
      };

      img.src = editMode.artworkUrl;
    },

    showEditIndicator: function (title) {
      // Add visual indicator that we're in edit mode
      var indicator = document.createElement('div');
      indicator.id = 'makapix-edit-indicator';
      indicator.innerHTML = '<span>Editing: ' + (title || 'Untitled') + '</span>';
      indicator.style.cssText = 
        'position: fixed; top: 0; left: 50%; transform: translateX(-50%);' +
        'background: #00d4ff; color: #000; padding: 4px 12px; font-size: 12px;' +
        'font-weight: bold; z-index: 10000; border-radius: 0 0 4px 4px;';
      document.body.appendChild(indicator);
    },

    checkEditModeUrl: function () {
      var params = new URLSearchParams(window.location.search);
      var editSqid = params.get('edit');
      if (editSqid) {
        // Store for use when MAKAPIX_INIT arrives
        try {
          sessionStorage.setItem('makapix_pending_edit', editSqid);
        } catch (e) {
          // Ignore
        }
      }
    },

    startTokenChecker: function () {
      if (tokenCheckTimer) {
        clearInterval(tokenCheckTimer);
      }

      tokenCheckTimer = setInterval(function () {
        if (!accessToken) return;

        try {
          var payload = JSON.parse(atob(accessToken.split('.')[1]));
          var expiresAt = payload.exp * 1000;
          var now = Date.now();
          var bufferMs = TOKEN_REFRESH_BUFFER_SECONDS * 1000;

          if (expiresAt - now < bufferMs) {
            ns.MakapixIntegration.requestTokenRefresh();
          }
        } catch (e) {
          console.warn('Failed to check token expiry:', e);
        }
      }, TOKEN_CHECK_INTERVAL_MS);
    },

    requestTokenRefresh: function () {
      this.sendMessage({ type: 'PISKEL_AUTH_REFRESH_REQUEST' });
    },

    sendMessage: function (data) {
      if (window.parent !== window) {
        window.parent.postMessage(data, MAKAPIX_ORIGIN);
      }
    },

    getAccessToken: function () {
      return accessToken;
    },

    getEditContext: function () {
      return editContext;
    },

    isEditMode: function () {
      return editContext !== null;
    },

    exportToMakapix: function (blob, name, width, height, frameCount, fps) {
      this.sendMessage({
        type: 'PISKEL_EXPORT',
        blob: blob,
        name: name,
        width: width,
        height: height,
        frameCount: frameCount,
        fps: fps
      });
    },

    replaceArtwork: function (blob, name, width, height, frameCount, fps) {
      if (!editContext || !editContext.postSqid) {
        console.error('Cannot replace: no edit context');
        return;
      }

      this.sendMessage({
        type: 'PISKEL_REPLACE',
        blob: blob,
        originalPostSqid: editContext.postSqid,
        name: name,
        width: width,
        height: height,
        frameCount: frameCount,
        fps: fps
      });
    }
  };
})();
```

### 2. `src/js/service/storage/MakapixStorageService.js`

```javascript
/**
 * Makapix Storage Service
 * Generates GIF and sends to Makapix via postMessage
 */
(function () {
  var ns = $.namespace('pskl.service.storage');

  ns.MakapixStorageService = function (piskelController) {
    this.piskelController = piskelController;
  };

  ns.MakapixStorageService.prototype.init = function () {};

  ns.MakapixStorageService.prototype.save = function (piskel, options) {
    var deferred = Q.defer();
    var self = this;
    options = options || {};

    // Get export settings
    var zoom = options.zoom || 1;
    var fps = this.piskelController.getFPS();
    var frameCount = this.piskelController.getFrameCount();
    var width = this.piskelController.getWidth() * zoom;
    var height = this.piskelController.getHeight() * zoom;
    var name = piskel.getDescriptor().name;

    // Generate GIF
    this.renderAsGifBlob(zoom, fps, function (blob) {
      if (options.replace && pskl.makapix.MakapixIntegration.isEditMode()) {
        pskl.makapix.MakapixIntegration.replaceArtwork(
          blob, name, width, height, frameCount, fps
        );
      } else {
        pskl.makapix.MakapixIntegration.exportToMakapix(
          blob, name, width, height, frameCount, fps
        );
      }

      $.publish(Events.SHOW_NOTIFICATION, [{
        content: 'Sent to Makapix!',
        hideDelay: 3000
      }]);

      deferred.resolve();
    });

    return deferred.promise;
  };

  ns.MakapixStorageService.prototype.renderAsGifBlob = function (zoom, fps, callback) {
    var currentColors = pskl.app.currentColorsService.getCurrentColors();
    var layers = this.piskelController.getLayers();
    var isTransparent = layers.some(function (l) { return l.isTransparent(); });
    var preserveColors = !isTransparent && currentColors.length < 256;

    var transparentColor;
    var transparent;
    if (preserveColors) {
      transparentColor = pskl.utils.ColorUtils.getUnusedColor(currentColors) || '#FF00FF';
      transparent = parseInt(transparentColor.substring(1), 16);
    } else {
      transparentColor = '#FFFFFF';
      transparent = null;
    }

    var width = this.piskelController.getWidth();
    var height = this.piskelController.getHeight();

    var gif = new window.GIF({
      workers: 5,
      quality: 1,
      width: width * zoom,
      height: height * zoom,
      preserveColors: preserveColors,
      repeat: 0,
      transparent: transparent
    });

    var background = pskl.utils.CanvasUtils.createCanvas(width, height);
    var context = background.getContext('2d');
    context.fillStyle = transparentColor;

    for (var i = 0; i < this.piskelController.getFrameCount(); i++) {
      var render = this.piskelController.renderFrameAt(i, true);
      context.clearRect(0, 0, width, height);
      context.fillRect(0, 0, width, height);
      context.drawImage(render, 0, 0, width, height);

      var canvas = pskl.utils.ImageResizer.scale(background, zoom);
      gif.addFrame(canvas.getContext('2d'), {
        delay: 1000 / fps
      });
    }

    $.publish(Events.SHOW_PROGRESS, [{ name: 'Preparing for Makapix...' }]);
    
    gif.on('progress', function (percentage) {
      $.publish(Events.UPDATE_PROGRESS, [{ progress: (percentage * 100).toFixed(1) }]);
    });

    gif.on('finished', function (blob) {
      $.publish(Events.HIDE_PROGRESS);
      callback(blob);
    });

    gif.render();
  };
})();
```

---

## Modified Files

### 3. `src/js/Constants.js`

**Changes:**
- Set `MAX_WIDTH` and `MAX_HEIGHT` to 256 (Makapix limit)

```diff
  MAX_HEIGHT : 1024,
  MAX_WIDTH : 1024,
+ // Makapix Club limits artwork to 256x256
+ MAX_HEIGHT : 256,
+ MAX_WIDTH : 256,
```

### 4. `src/js/app.js`

**Changes:**
- Initialize Makapix integration
- Add Makapix storage service

```diff
  this.fileDropperService.init();

+ // Makapix Integration
+ this.makapixStorageService = new pskl.service.storage.MakapixStorageService(this.piskelController);
+ this.makapixStorageService.init();
+
+ // Initialize Makapix communication (if in iframe)
+ if (window.parent !== window) {
+   pskl.makapix.MakapixIntegration.init();
+ }
+
  this.userWarningController = new pskl.controller.UserWarningController(this.piskelController);
```

### 5. `src/js/controller/settings/exportimage/GifExportController.js`

**Changes:**
- Add "Publish to Makapix" button handler

```diff
  ns.GifExportController.prototype.init = function () {
    this.uploadStatusContainerEl = document.querySelector('.gif-upload-status');
    this.downloadButton = document.querySelector('.gif-download-button');
    this.repeatCheckbox = document.querySelector('.gif-repeat-checkbox');
+   this.makapixButton = document.querySelector('.gif-makapix-button');
+   this.makapixReplaceButton = document.querySelector('.gif-makapix-replace-button');

    // Initialize repeatCheckbox state
    this.repeatCheckbox.checked = this.getRepeatSetting_();

    this.addEventListener(this.downloadButton, 'click', this.onDownloadButtonClick_);
    this.addEventListener(this.repeatCheckbox, 'change', this.onRepeatCheckboxChange_);
+   
+   if (this.makapixButton) {
+     this.addEventListener(this.makapixButton, 'click', this.onMakapixButtonClick_);
+   }
+   if (this.makapixReplaceButton) {
+     this.addEventListener(this.makapixReplaceButton, 'click', this.onMakapixReplaceButtonClick_);
+   }
+   
+   // Show/hide replace button based on edit mode
+   this.updateMakapixButtons_();

    var currentColors = pskl.app.currentColorsService.getCurrentColors();
    var tooManyColors = currentColors.length >= MAX_GIF_COLORS;
    document.querySelector('.gif-export-warning').classList.toggle('visible', tooManyColors);
  };

+ ns.GifExportController.prototype.updateMakapixButtons_ = function () {
+   var isEditMode = pskl.makapix && pskl.makapix.MakapixIntegration.isEditMode();
+   if (this.makapixReplaceButton) {
+     this.makapixReplaceButton.style.display = isEditMode ? 'inline-block' : 'none';
+   }
+ };

+ ns.GifExportController.prototype.onMakapixButtonClick_ = function () {
+   var zoom = this.getZoom_();
+   pskl.app.makapixStorageService.save(pskl.app.piskelController.getPiskel(), {
+     zoom: zoom,
+     replace: false
+   });
+ };

+ ns.GifExportController.prototype.onMakapixReplaceButtonClick_ = function () {
+   var zoom = this.getZoom_();
+   pskl.app.makapixStorageService.save(pskl.app.piskelController.getPiskel(), {
+     zoom: zoom,
+     replace: true
+   });
+ };
```

### 6. `src/templates/settings/export/gif.html`

**Changes:**
- Add Makapix publish buttons

```diff
    <div class="export-panel-section export-panel-row">
      <button type="button" class="button button-primary gif-download-button">Download</button>
      <div class="export-info">Download as an animated GIF.</div>
    </div>
+   <div class="export-panel-section export-panel-row makapix-export-section">
+     <button type="button" class="button button-primary gif-makapix-button">
+       🚀 Publish to Makapix
+     </button>
+     <button type="button" class="button button-secondary gif-makapix-replace-button" style="display:none;">
+       🔄 Replace Original
+     </button>
+     <div class="export-info">Send directly to Makapix Club for publishing.</div>
+   </div>
  </div>
```

### 7. `src/piskel-script-list.js`

**Changes:**
- Add new script files to the build

```diff
  window.pskl_exports.scripts = [
    // ... existing scripts ...
    'js/service/storage/GalleryStorageService.js',
+   'js/service/storage/MakapixStorageService.js',
+   'js/makapix/MakapixIntegration.js',
    // ... rest of scripts ...
  ];
```

---

## New: `Dockerfile`

```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install grunt globally
RUN npm install -g grunt-cli

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build production version
RUN grunt build

# Production stage
FROM caddy:2-alpine

# Copy built files
COPY --from=builder /app/dest/prod /srv

# Caddy config for SPA
COPY <<EOF /etc/caddy/Caddyfile
:80 {
    root * /srv
    encode gzip
    try_files {path} /index.html
    file_server
    header X-Content-Type-Options nosniff
}
EOF

EXPOSE 80
```

---

## CSS Additions (Optional)

Add to `src/css/settings-export.css`:

```css
/* Makapix export section */
.makapix-export-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #3a3a3a;
}

.gif-makapix-button {
  background: linear-gradient(135deg, #ff6eb4, #b44eff) !important;
}

.gif-makapix-button:hover {
  box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
}

.gif-makapix-replace-button {
  margin-left: 8px;
}
```

---

## Build Commands

```bash
# Development
cd apps/piskel
npm install
npm run dev

# Production build
npm run prod

# Or with grunt directly
npx grunt build
```

## Testing Checklist

- [ ] Piskel loads without errors
- [ ] "Publish to Makapix" button appears in GIF export
- [ ] Edit mode shows indicator bar
- [ ] Replace button appears in edit mode
- [ ] postMessage sends correctly
- [ ] Token refresh request works
- [ ] 256x256 max dimension enforced

