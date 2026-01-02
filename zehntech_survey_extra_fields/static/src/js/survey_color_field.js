/** @odoo-module */

import { registry } from "@web/core/registry";

const interactions = registry.category("public.interactions");

function applyPatchTo(SurveyForm) {
    // Helper to initialize address and name fields using jQuery scoped to this.el
    function _initializeAddressFields() {
        const $root = $(this.el);
        $root.find('[data-question-type="address"]').each(function () {
            const $hiddenInput = $(this);
            const existingData = $hiddenInput.val();
            if (existingData) {
                try {
                    const addressData = JSON.parse(existingData);
                    const $container = $hiddenInput.closest('.o_survey_answer_wrapper').find('.address-fields');
                    $container.find('.address-street').val(addressData.street || '');
                    $container.find('.address-street2').val(addressData.street2 || '');
                    $container.find('.address-zip').val(addressData.zip || '');
                    $container.find('.address-city').val(addressData.city || '');
                    $container.find('.address-state').val(addressData.state || '');
                    $container.find('.address-country').val(addressData.country || '');
                } catch (e) {
                    console.error('Error parsing address data:', e);
                }
            }
        });

        $root.find('[data-question-type="name"]').each(function () {
            const $hiddenInput = $(this);
            const existingData = $hiddenInput.val();
            if (existingData) {
                try {
                    const nameData = JSON.parse(existingData);
                    const $container = $hiddenInput.closest('.o_survey_answer_wrapper').find('.name-fields');
                    $container.find('.name-first').val(nameData.first_name || '');
                    $container.find('.name-middle').val(nameData.middle_name || '');
                    $container.find('.name-last').val(nameData.last_name || '');
                } catch (e) {
                    console.error('Error parsing name data:', e);
                }
            }
        });

        $root.find('.o_survey_question_many2many').off('change.custom_many2many').on('change.custom_many2many', function() {
            const selectedIds = Array.from(this.selectedOptions).map(option => option.value).filter(id => id);
            $(this).siblings('.many2many-data').val(selectedIds.join(','));
        });
    }

    function displayErrors(ctx, errors) {
        // Prefer built-in methods if present (showErrors or _showErrors)
        if (typeof ctx.showErrors === 'function') {
            ctx.showErrors(errors);
        } else if (typeof ctx._showErrors === 'function') {
            ctx._showErrors(errors);
        } else {
            // fallback: simple inline display or alert
            // Try to mark elements with error class if possible
            try {
                Object.keys(errors).forEach(function (qid) {
                    const msg = errors[qid];
                    const $el = $('#' + qid);
                    if ($el.length) {
                        $el.addClass('o_survey_error');
                        // append small error block if not present
                        if ($el.find('.o_survey_inline_error').length === 0) {
                            $el.append($('<div class="o_survey_inline_error"/>').text(msg));
                        } else {
                            $el.find('.o_survey_inline_error').text(msg);
                        }
                    }
                });
            } catch (e) {
                // last resort
                alert(Object.values(errors).join("\n"));
            }
        }
    }

    // Wrap start
    const _origStart = SurveyForm.prototype.start;
    SurveyForm.prototype.start = function () {
        const res = _origStart && _origStart.apply(this, arguments);
        try {
            _initializeAddressFields.call(this);
        } catch (e) {
            console.error('Error in custom survey start initialiser:', e);
        }
        return res;
    };

    // Wrap prepareSubmitValues
    const _origPrepare = SurveyForm.prototype.prepareSubmitValues;
    SurveyForm.prototype.prepareSubmitValues = function (formData, params) {
        _origPrepare && _origPrepare.call(this, formData, params);
        const $root = $(this.el);

        $root.find('[data-question-type="color"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="email"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="url"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="time"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="range"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="week"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="password"]').each(function () { params[this.name] = this.value; });
        $root.find('[data-question-type="signature"]').each(function () {
            const $hiddenInput = $(this);
            const signatureData = $hiddenInput.val();
            if (signatureData && signatureData.startsWith('data:image/')) {
                params[this.name] = signatureData;
            }
        });
        $root.find('[data-question-type="month"]').each(function () { params[this.name] = this.value; });

        $root.find('[data-question-type="address"]').each(function () {
            const $hiddenInput = $(this);
            const $addressContainer = $hiddenInput.closest('.o_survey_answer_wrapper').find('.address-fields');
            const addressData = {
                street: $addressContainer.find('.address-street').val() || '',
                street2: $addressContainer.find('.address-street2').val() || '',
                zip: $addressContainer.find('.address-zip').val() || '',
                city: $addressContainer.find('.address-city').val() || '',
                state: $addressContainer.find('.address-state').val() || '',
                country: $addressContainer.find('.address-country').val() || ''
            };
            params[this.name] = JSON.stringify(addressData);
        });

        $root.find('[data-question-type="name"]').each(function () {
            const $hiddenInput = $(this);
            const $nameContainer = $hiddenInput.closest('.o_survey_answer_wrapper').find('.name-fields');
            const nameData = {
                first_name: $nameContainer.find('.name-first').val() || '',
                middle_name: $nameContainer.find('.name-middle').val() || '',
                last_name: $nameContainer.find('.name-last').val() || ''
            };
            params[this.name] = JSON.stringify(nameData);
        });

        $root.find('[data-question-type="many2one"]').each(function () { params[this.name] = this.value; });

        $root.find('[data-question-type="many2many"]').each(function () {
            const selectedIds = Array.from(this.selectedOptions).map(option => option.value).filter(id => id);
            params[this.name] = selectedIds.join(',');
        });

        $root.find('[data-question-type="file"]').each(function () {
            const $input = $(this);
            const files = $input[0].files;
            if (files && files.length > 0) {
                const fd = new FormData();
                fd.append('file', files[0]);
                // Keep synchronous ajax for parity with original behaviour
                $.ajax({
                    url: '/survey/upload_file',
                    type: 'POST',
                    data: fd,
                    processData: false,
                    contentType: false,
                    async: false
                }).done(function(response) {
                    let result;
                    try {
                        result = JSON.parse(response);
                    } catch (e) {
                        result = response;
                    }
                    if (result && result.attachment_id) {
                        // original code used data-question-id to set
                        params[$input.data('question-id')] = result.attachment_id;
                    }
                }).fail(function (jqXHR, status, err) {
                    console.error('File upload failed:', status, err);
                });
            }
        });

        return params;
    };

    // Wrap validateForm
    const _origValidate = SurveyForm.prototype.validateForm;
    SurveyForm.prototype.validateForm = function (formEl, formData) {
        const origResult = _origValidate && _origValidate.call(this, formEl, formData);
        // If original validation failed, propagate false (keep original behavior)
        if (origResult === false) {
            return false;
        }

        const $form = $(formEl);
        const errors = {};

        // Color fields
        $form.find('[data-question-type="color"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            if (questionRequired && !$input.val()) {
                errors[questionId] = 'Please select a color.';
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a color.";
                errors[questionId] = customErrorMsg;
            }
        });

        // Email fields
        $form.find('[data-question-type="email"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const value = ($input.val() || '').trim();
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (questionRequired && !value) {
                errors[questionId] = 'Please enter an email address.';
                var customErrorMsg = $questionWrapper.data('required-error') || "Please enter an email address.";
                errors[questionId] = customErrorMsg;
            } else if (value && !emailRegex.test(value)) {
                errors[questionId] = 'Please enter a valid email address (e.g., user@example.com).';
            }
        });

        // URL fields
        $form.find('[data-question-type="url"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const value = ($input.val() || '').trim();
            const urlRegex = /^https?:\/\/[^\s]+$/;
            if (questionRequired && !value) {
                errors[questionId] = 'Please enter a URL.';
                var customErrorMsg = $questionWrapper.data('required-error') || "Please enter a URL.";
                errors[questionId] = customErrorMsg;
            } else if (value && !urlRegex.test(value)) {
                errors[questionId] = 'Please enter a valid URL starting with http:// or https:// (e.g., https://example.com).';
            }
        });

        // Time fields with min/max/step
        $form.find('[data-question-type="time"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const value = $input.val();
            const step = parseInt($questionWrapper.data('timeStep') || 15, 10);
            const min = $questionWrapper.data('timeMin');
            const max = $questionWrapper.data('timeMax');

            if (questionRequired && !value) {
                errors[questionId] = "Please select a time.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a time.";
                errors[questionId] = customErrorMsg;
                return;
            }
            if (value) {
                const timeParts = value.split(':');
                if (timeParts.length !== 2) {
                    errors[questionId] = "Please enter a valid time format (HH:MM).";
                    return;
                }
                const hours = parseInt(timeParts[0], 10);
                const minutes = parseInt(timeParts[1], 10);

                let minParts, maxParts;
                if (min) {
                    minParts = min.split(':');
                    if (hours < parseInt(minParts[0], 10) || (hours === parseInt(minParts[0], 10) && minutes < parseInt(minParts[1], 10))) {
                        errors[questionId] = "Time must be after " + min + ".";
                    }
                }
                if (max) {
                    maxParts = max.split(':');
                    if (hours > parseInt(maxParts[0], 10) || (hours === parseInt(maxParts[0], 10) && minutes > parseInt(maxParts[1], 10))) {
                        errors[questionId] = "Time must be before " + max + ".";
                    }
                }

                if (step && min) {
                    const minTime = parseInt(minParts[0], 10) * 60 + parseInt(minParts[1], 10);
                    const valueTime = hours * 60 + minutes;
                    if ((valueTime - minTime) % step !== 0) {
                        errors[questionId] = "Please select time in " + step + " minute intervals from " + min + ".";
                    }
                }
            }
        });

        // Range fields
        $form.find('[data-question-type="range"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const validateRange = $questionWrapper.data('validateRange');

            const val = parseFloat($input.val());
            const min = parseFloat($input.attr('min'));
            const max = parseFloat($input.attr('max'));
            const step = parseFloat($input.attr('step') || 1);

            if (questionRequired && !$input.val()) {
                errors[questionId] = "Please select a value.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a value.";
                errors[questionId] = customErrorMsg;
            } else if (validateRange && $input.val()) {
                if (!isNaN(min) && val < min || !isNaN(max) && val > max) {
                    errors[questionId] = "Value must be between " + min + " and " + max + ".";
                } else {
                    // step check (allow float rounding)
                    if (step && !isNaN(min)) {
                        const diff = (val - min) / step;
                        const near = Math.round(diff);
                        const eps = 1e-9;
                        if (Math.abs(diff - near) > eps) {
                            errors[questionId] = "Value must be in steps of " + step + " from " + min + ".";
                        }
                    }
                }
            }
        });

        // Week field validation
        $form.find('[data-question-type="week"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const minWeek = $input.data('weekMin');
            const maxWeek = $input.data('weekMax');
            const step = parseInt($input.data('weekStep') || 1, 10);
            const value = ($input.val() || '').trim();

            if (questionRequired && !value) {
                errors[questionId] = "Please select a week.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a week.";
                errors[questionId] = customErrorMsg;
                return;
            }

            if (value && minWeek && maxWeek) {
                const valParts = value.split('-W');
                const minParts = minWeek.split('-W');
                const maxParts = maxWeek.split('-W');

                const valYear = parseInt(valParts[0], 10);
                const valWeek = parseInt(valParts[1], 10);
                const minYear = parseInt(minParts[0], 10);
                const minWeekNum = parseInt(minParts[1], 10);
                const maxYear = parseInt(maxParts[0], 10);
                const maxWeekNum = parseInt(maxParts[1], 10);

                if (valYear < minYear || (valYear === minYear && valWeek < minWeekNum) ||
                    valYear > maxYear || (valYear === maxYear && valWeek > maxWeekNum)) {
                    errors[questionId] = "Please select a week between " + minWeek + " and " + maxWeek + ".";
                    return;
                }

                if (step > 1) {
                    const diffWeeks = (valYear - minYear) * 52 + (valWeek - minWeekNum);
                    if (diffWeeks % step !== 0) {
                        errors[questionId] = "Please select a week in steps of " + step + " from " + minWeek + ".";
                        return;
                    }
                }
            }
        });

        // Password fields
        $form.find('[data-question-type="password"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const required = $questionWrapper.data('required');
            const validate = $input.data('validate-password');
            const minLength = parseInt($input.data('password-min') || 0, 10);
            const maxLength = parseInt($input.data('password-max') || 4096, 10);

            const val = $input.val() || '';

            if (required && !val) {
                errors[questionId] = "Please enter a password.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please enter a password.";
                errors[questionId] = customErrorMsg;
            } else if (validate && val) {
                if (val.length < minLength) {
                    errors[questionId] = "Password must be at least " + minLength + " characters long.";
                } else if (val.length > maxLength) {
                    errors[questionId] = "Password cannot exceed " + maxLength + " characters.";
                }
            }
        });

        // File fields validation (size & allowed types)
        $form.find('[data-question-type="file"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const maxSize = parseFloat($input.data('max-size')) || 10; // MB
            const allowedTypes = $input.data('allowed-types'); // comma separated exts
            const files = $input[0].files;

            if (questionRequired && (!files || files.length === 0)) {
                errors[questionId] = "Please select a file.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a file.";
                errors[questionId] = customErrorMsg;
                return;
            }

            if (files && files.length > 0) {
                const file = files[0];
                const fileSizeMB = file.size / (1024 * 1024);

                if (fileSizeMB > maxSize) {
                    errors[questionId] = "File size must not exceed " + maxSize + " MB.";
                    return;
                }

                if (allowedTypes) {
                    const fileExt = (file.name.split('.').pop() || '').toLowerCase();
                    const allowed = allowedTypes.toLowerCase().split(',').map(s => s.trim());
                    if (!allowed.includes(fileExt)) {
                        errors[questionId] = "Only " + allowedTypes + " files are allowed.";
                        return;
                    }
                }
            }
        });

        // Month fields
        $form.find('[data-question-type="month"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const validateEntry = $input.data('validate-month-entry');
            const minMonth = $input.data('month-min');
            const maxMonth = $input.data('month-max');
            const step = parseInt($input.data('month-step') || 1, 10);
            const value = ($input.val() || '').trim();

            if (questionRequired && !value) {
                errors[questionId] = "Please select a month.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select a month.";
                errors[questionId] = customErrorMsg;
                return;
            }

            if (value && validateEntry) {
                const monthRegex = /^\d{4}-\d{2}$/;
                if (!monthRegex.test(value)) {
                    errors[questionId] = "Please enter a valid month in YYYY-MM format.";
                    return;
                }

                if (minMonth && value < minMonth) {
                    errors[questionId] = "Please select a month after " + minMonth + ".";
                    return;
                }

                if (maxMonth && value > maxMonth) {
                    errors[questionId] = "Please select a month before " + maxMonth + ".";
                    return;
                }

                if (step > 1 && minMonth) {
                    const minParts = minMonth.split('-');
                    const valParts = value.split('-');
                    const minYear = parseInt(minParts[0], 10);
                    const minMonthNum = parseInt(minParts[1], 10);
                    const valYear = parseInt(valParts[0], 10);
                    const valMonthNum = parseInt(valParts[1], 10);

                    const monthsFromMin = (valYear - minYear) * 12 + (valMonthNum - minMonthNum);
                    if (monthsFromMin % step !== 0) {
                        errors[questionId] = "Please select a month in steps of " + step + " from " + minMonth + ".";
                        return;
                    }
                }
            }
        });

        // Address fields required check (at least one non-empty)
        $form.find('[data-question-type="address"]').each(function () {
            const $hiddenInput = $(this);
            const $questionWrapper = $hiddenInput.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const $addressContainer = $hiddenInput.closest('.o_survey_answer_wrapper').find('.address-fields');

            if (questionRequired) {
                let hasValue = false;
                $addressContainer.find('input[type="text"]').each(function() {
                    if ($(this).val().trim()) {
                        hasValue = true;
                        return false;
                    }
                });

                if (!hasValue) {
                    errors[questionId] = "At least one address field must be filled.";
                    var customErrorMsg = $questionWrapper.data('required-error') || "At least one address field must be filled.";
                    errors[questionId] = customErrorMsg;
                }
            }
        });

        // Name fields required check (first & last, middle optional)
        $form.find('[data-question-type="name"]').each(function () {
            const $hiddenInput = $(this);
            const $questionWrapper = $hiddenInput.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');
            const middleOptional = $hiddenInput.data('middle-optional');
            const $nameContainer = $hiddenInput.closest('.o_survey_answer_wrapper').find('.name-fields');

            if (questionRequired) {
                const firstName = ($nameContainer.find('.name-first').val() || '').trim();
                const lastName = ($nameContainer.find('.name-last').val() || '').trim();
                const middleName = ($nameContainer.find('.name-middle').val() || '').trim();

                if (!firstName) {
                    errors[questionId] = "First name is required.";
                     var customErrorMsg = $questionWrapper.data('required-error') || "First name is required.";
                    errors[questionId] = customErrorMsg;
                } else if (!lastName) {
                    errors[questionId] = "Last name is required.";
                    var customErrorMsg = $questionWrapper.data('required-error') || "Last name is required.";
                    errors[questionId] = customErrorMsg;
                } else if (!middleOptional && !middleName) {
                    errors[questionId] = "Middle name is required.";
                    var customErrorMsg = $questionWrapper.data('required-error') || "Middle name is required.";
                    errors[questionId] = customErrorMsg;
                }
            }
        });

        // many2one required
        $form.find('[data-question-type="many2one"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');

            if (questionRequired && !$input.val()) {
                errors[questionId] = "Please select an option.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select an option.";
                errors[questionId] = customErrorMsg;
            }
        });

        // many2many required
        $form.find('[data-question-type="many2many"]').each(function () {
            const $input = $(this);
            const $questionWrapper = $input.closest(".js_question-wrapper");
            const questionId = $questionWrapper.attr('id');
            const questionRequired = $questionWrapper.data('required');

            const val = $input.val() || [];
            if (questionRequired && val.length === 0) {
                errors[questionId] = "Please select at least one option.";
                var customErrorMsg = $questionWrapper.data('required-error') || "Please select at least one option.";
                errors[questionId] = customErrorMsg;
            }
        });

        if (Object.keys(errors).length > 0) {
            displayErrors(this, errors);
            return false;
        }

        return origResult;
    };
}

// If the interaction is already registered, patch it now. Otherwise wait
// for the public.interactions registry to be updated.
if (interactions.contains("survey.SurveyForm")) {
    applyPatchTo(interactions.get("survey.SurveyForm"));
} else {
    const handler = (ev) => {
        if (interactions.contains("survey.SurveyForm")) {
            interactions.removeEventListener("UPDATE", handler);
            applyPatchTo(interactions.get("survey.SurveyForm"));
        }
    };
    interactions.addEventListener("UPDATE", handler);
}
