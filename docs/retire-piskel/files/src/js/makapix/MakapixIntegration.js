/**
 * Makapix Integration Module
 * Handles communication between Piskel and Makapix Club via postMessage
 */
(function () {
  var ns = $.namespace('pskl.makapix');

  // Configuration
  var MAKAPIX_ORIGIN = 'https://makapix.club';
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
        case 'MAKAPIX_EDIT_FRAMES_RGBA':
          this.handleRgbaFrames(data);
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
        // If frames are sent separately (transferables), wait for them.
        if (!editContext.hasRgbaFrames) {
          this.loadArtworkForEditing(data.editMode);
        } else {
          $.publish(Events.SHOW_NOTIFICATION, [{
            content: 'Loading animation frames...',
            hideDelay: -1
          }]);
        }
      }

      // Store in session for recovery
      try {
        sessionStorage.setItem('makapix_access_token', accessToken);
        if (editContext) {
          // Do not store large/binary payloads in session storage.
          var safeContext = editContext;
          if (safeContext && safeContext.hasRgbaFrames) {
            safeContext = {
              postSqid: safeContext.postSqid,
              artworkUrl: safeContext.artworkUrl,
              title: safeContext.title,
              hasRgbaFrames: true,
              frameCount: safeContext.frameCount,
              width: safeContext.width,
              height: safeContext.height,
              fps: safeContext.fps
            };
          }
          sessionStorage.setItem('makapix_edit_context', JSON.stringify(safeContext));
        }
      } catch (e) {
        console.warn('Failed to store Makapix session data:', e);
      }
    },

    handleRgbaFrames: function (data) {
      try {
        if (!editContext) {
          console.warn('Received RGBA frames but no editContext exists yet');
          return;
        }

        var buffers = data.frameRgbaBuffers || [];
        if (!buffers.length) {
          console.error('Received RGBA frames message without buffers');
          return;
        }

        // Prefer dimensions from init editContext, fall back to message.
        var w = editContext.width || data.width;
        var h = editContext.height || data.height;
        if (!w || !h) {
          console.error('Missing frame dimensions for RGBA import');
          return;
        }

        var canvases = buffers.map(function (buf) {
          var bytes = new Uint8ClampedArray(buf);
          // Basic sanity check
          if (bytes.length !== w * h * 4) {
            throw new Error('Invalid RGBA buffer size: expected ' + (w * h * 4) + ' got ' + bytes.length);
          }
          var imageData = new ImageData(bytes, w, h);
          return pskl.utils.CanvasUtils.createFromImageData(imageData);
        });

        var piskel = pskl.app.importService.createPiskelFromImages_(
          canvases,
          editContext.title || 'Makapix Edit',
          w,
          h,
          false // smoothing
        );

        // Set FPS if provided
        var fps = editContext.fps || data.fps;
        if (fps && fps > 0) {
          piskel.fps = fps;
        }

        pskl.app.piskelController.setPiskel(piskel);
        ns.MakapixIntegration.showEditIndicator(editContext.title);
        $.publish(Events.HIDE_NOTIFICATION);
      } catch (e) {
        console.error('Failed to create Piskel from RGBA frames:', e);
        $.publish(Events.SHOW_NOTIFICATION, [{
          content: 'Failed to load animation frames',
          hideDelay: 5000
        }]);
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
      // Check if we have pre-decoded multi-frame data
      if (editMode.frameDataUrls && editMode.frameDataUrls.length > 0) {
        this.loadMultiFrameArtwork(editMode);
        return;
      }

      // Fallback to single-image loading for simple cases
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

    loadMultiFrameArtwork: function (editMode) {
      var frameDataUrls = editMode.frameDataUrls;
      var images = [];
      var loaded = 0;
      var total = frameDataUrls.length;
      var hasError = false;

      console.log('Loading ' + total + ' frames for editing');

      // Load all frame images
      frameDataUrls.forEach(function(dataUrl, index) {
        var img = new Image();
        
        img.onload = function() {
          images[index] = img;
          loaded++;
          
          if (loaded === total && !hasError) {
            // All frames loaded successfully - create Piskel
            try {
              var piskel = pskl.app.importService.createPiskelFromImages_(
                images,
                editMode.title || 'Makapix Edit',
                images[0].width,
                images[0].height,
                false  // smoothing
              );
              
              // Set FPS if provided
              if (editMode.fps && editMode.fps > 0) {
                piskel.fps = editMode.fps;
              }
              
              pskl.app.piskelController.setPiskel(piskel);
              ns.MakapixIntegration.showEditIndicator(editMode.title);
              
              console.log('Successfully loaded ' + total + ' frames at ' + (editMode.fps || 'default') + ' FPS');
            } catch (e) {
              console.error('Failed to create Piskel from frames:', e);
              $.publish(Events.SHOW_NOTIFICATION, [{
                content: 'Failed to create animation from frames',
                hideDelay: 5000
              }]);
            }
          }
        };
        
        img.onerror = function() {
          if (!hasError) {
            hasError = true;
            console.error('Failed to load frame ' + index);
            $.publish(Events.SHOW_NOTIFICATION, [{
              content: 'Failed to load animation frames',
              hideDelay: 5000
            }]);
          }
        };
        
        img.src = dataUrl;
      });
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

