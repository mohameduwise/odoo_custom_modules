function loadSelect2() {
    if (!document.querySelector('link[href*="select2"]')) {
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = 'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css';
        document.head.appendChild(css);
    }
    
    if (typeof jQuery !== 'undefined' && !jQuery.fn.select2) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js';
        script.onload = () => setTimeout(initSelect2, 100);
        document.head.appendChild(script);
    } else if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
        initSelect2();
    } else {
        setTimeout(loadSelect2, 100);
    }
}

function initSelect2() {
    if (typeof jQuery === 'undefined' || !jQuery.fn.select2) {
        setTimeout(initSelect2, 100);
        return;
    }

    jQuery('.many2many-select2:not(.select2-hidden-accessible)').select2({
        placeholder: "Select one or more options",
        allowClear: true,
        closeOnSelect: false,
        width: '100%'
    }).on('change', function() {
        const values = jQuery(this).val() || [];
        jQuery(this).closest('.o_survey_answer_wrapper').find('.many2many-data').val(values.join(','));
    }).trigger('change');
    
    jQuery('.many2one-select2:not(.select2-hidden-accessible)').select2({
        placeholder: "-- Select an option --",
        allowClear: true,
        width: '100%'
    });
}

if (typeof jQuery !== 'undefined') {
    jQuery(document).ready(loadSelect2);
    
    new MutationObserver(mutations => {
        if (mutations.some(m => m.addedNodes.length && 
            Array.from(m.addedNodes).some(n => n.nodeType === 1 && 
                (n.querySelector('.many2many-select2') || n.querySelector('.many2one-select2'))))) {
            setTimeout(initSelect2, 50);
        }
    }).observe(document.body, { childList: true, subtree: true });
} else {
    setTimeout(loadSelect2, 100);
}