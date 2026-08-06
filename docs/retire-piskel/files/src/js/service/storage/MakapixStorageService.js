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

