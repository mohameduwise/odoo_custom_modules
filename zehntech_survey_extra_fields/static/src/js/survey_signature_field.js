(function() {
    'use strict';
    
    function initSignaturePads() {
        document.querySelectorAll('.signature-pad').forEach(function(canvas) {
            if (canvas.dataset.initialized) return;
            canvas.dataset.initialized = 'true';
            
            var ctx = canvas.getContext('2d');
            var drawing = false;
            var hiddenInput = canvas.closest('.o_survey_answer_wrapper').querySelector('.signature-data');
            
            // Set drawing style
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            
            // Clear canvas
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Load existing signature if available
            var existingData = hiddenInput.value;
            if (existingData && existingData.startsWith('data:image/')) {
                var img = new Image();
                img.onload = function() {
                    ctx.drawImage(img, 0, 0);
                };
                img.src = existingData;
            }
            
            function getMousePos(e) {
                var rect = canvas.getBoundingClientRect();
                return {
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                };
            }
            
            canvas.addEventListener('mousedown', function(e) {
                drawing = true;
                var pos = getMousePos(e);
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y);
            });
            
            canvas.addEventListener('mousemove', function(e) {
                if (!drawing) return;
                var pos = getMousePos(e);
                ctx.lineTo(pos.x, pos.y);
                ctx.stroke();
            });
            
            function saveSignature() {
                if (drawing) {
                    drawing = false;
                    hiddenInput.value = canvas.toDataURL('image/png');
                }
            }
            
            canvas.addEventListener('mouseup', saveSignature);
            canvas.addEventListener('mouseout', saveSignature);
        });
        
        // Handle clear buttons
        document.querySelectorAll('.clear-signature').forEach(function(btn) {
            if (btn.dataset.initialized) return;
            btn.dataset.initialized = 'true';
            
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var container = btn.closest('.signature-container');
                var canvas = container.querySelector('.signature-pad');
                var hiddenInput = container.closest('.o_survey_answer_wrapper').querySelector('.signature-data');
                
                if (canvas) {
                    var ctx = canvas.getContext('2d');
                    ctx.fillStyle = 'white';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    hiddenInput.value = '';
                }
            });
        });
    }
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSignaturePads);
    } else {
        initSignaturePads();
    }
    
    // Re-initialize when new content is added (for dynamic content)
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length) {
                initSignaturePads();
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();