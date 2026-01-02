odoo.define('zehntech_survey_extra_fields.survey_range_field', [], function (require) {
    'use strict';
 
    $(document).ready(function() {
        $(document).on('input', '.o_survey_question_range', function() {
            var $range = $(this);
            var $valueDisplay = $range.closest('.o_survey_answer_wrapper').find('.range-value');
            $valueDisplay.text($range.val());
        });
       
        // Initialize value on page load
        $('.o_survey_question_range').each(function() {
            var $range = $(this);
            var $valueDisplay = $range.closest('.o_survey_answer_wrapper').find('.range-value');
            $valueDisplay.text($range.val());
        });
    });
});