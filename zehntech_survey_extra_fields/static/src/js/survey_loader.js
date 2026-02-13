import { patch } from '@web/core/utils/patch';
import {SurveyForm} from '@survey/interactions/survey_form'
import { fadeIn, fadeOut } from "@survey/utils";
import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(SurveyForm.prototype, {
    // SUBMIT
    // -------------------------------------------------------------------------
    /**
     * This function will send a json rpc call to the server to
     * - start the survey (if we are on start screen)
     * - submit the answers of the current page
     * Before submitting the answers, they are first validated to avoid latency from the server
     * and allow a fade out/fade in transition of the next question.
     *
     * @param {Array} [options]
     * @param {Integer} [options.previousPageId] navigates to page id
     * @param {Boolean} [options.nextSkipped] navigates to next skipped page or question
     * @param {Boolean} [options.skipValidation] skips JS validation
     * @param {Boolean} [options.initTime] will force the re-init of the timer after next
     * screen transition
     * @param {Boolean} [options.isFinish] fades out breadcrumb and timer
     */
    async submitForm(options = {}) {
        if (this.submitting) {
            return;
        }
        this.submitting = true;

        const params = {};
        if (options.previousPageId) {
            params.previous_page_id = options.previousPageId;
        }
        if (options.nextSkipped) {
            params.next_skipped_page_or_question = true;
        }

        let route = "/survey/submit";
        if (this.options.isStartScreen) {
            params.lang_code = this.el.querySelector(
                ".o_survey_lang_selector[name='lang_code']"
            ).value;
            route = "/survey/begin";
            // Hide survey title in 'page_per_question' layout: it takes too much space
            if (this.options.questionsLayout === "page_per_question") {
                fadeOut(this.el.querySelector(".o_survey_main_title"), 400);
            }
            fadeOut(this.el.querySelector(".o_survey_lang_selector"), 400);
        } else {
            const formData = new FormData(this.formEl);
            if (!options.skipValidation) {
                if (!this.validateForm(this.formEl, formData)) {
                    this.submitting = false;
                    return;
                }
            }
            this._showLoadingOverlay(options.isFinish);
            this.prepareSubmitValues(formData, params);
        }

        if (this.options.sessionInProgress) {
            // reset the fadeInOutDelay when attendee is submitting form
            this.fadeInOutDelay = 400;
            // prevent user from clicking on matrix options when form is submitted
            this.readonly = true;
        }

        const submitPromise = rpc(
            `${route}/${this.options.surveyToken}/${this.options.answerToken}`,
            params
        );

        if (
            !this.options.isStartScreen &&
            this.options.scoringType === "scoring_with_answers_after_page"
        ) {
            const [correctAnswers] = await this.waitFor(submitPromise);
            if (
                Object.keys(correctAnswers).length &&
                this.el.querySelector(".js_question-wrapper")
            ) {
                this.showCorrectAnswers(correctAnswers, submitPromise, options);
                this.submitting = false;
                return;
            }
        }

        await this.nextScreen(submitPromise, options);
        this.submitting = false;
    },

    _showLoadingOverlay(isFinish = false) {
        if ($('.o_survey_loading_screen').length) return;

        const loadingHtml = `
            <div class="o_survey_loading_screen">
                <div class="o_survey_loading_content">
                    <div class="o_survey_spinner"></div>
                    <h3 class="o_survey_loading_title">Uploading the data...</h3>
                    <p>Please wait...</p>
                </div>
            </div>
        `;
        $('body').append(loadingHtml);

        // Rotating messages for overlay
        const overlayMessages = isFinish
            ? ['Processing and finalizing...', 'Saving your answers...', 'Almost there...']
            : ['Uploading the data...', 'Saving your answers...', 'Almost there...'];

        let messageIndex = 0;
        const messageInterval = setInterval(() => {
            messageIndex = (messageIndex + 1) % overlayMessages.length;
            $('.o_survey_loading_title').text(overlayMessages[messageIndex]);
        }, 2000);

        const observer = new MutationObserver(() => {
            if ($('.o_survey_finished, .o_survey_form_done').length) {
                clearInterval(messageInterval);
                $('.o_survey_loading_screen').remove();
                observer.disconnect();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    },

    onSubmit(ev) {
        ev.preventDefault();
        const targetEl = ev.currentTarget;
        const button = targetEl;

        if (targetEl.value === "previous") {
            this.submitForm({ previousPageId: parseInt(targetEl.dataset.previousPageId) });
        } else if (targetEl.value === "next_skipped") {
            this.submitForm({ nextSkipped: true });
        } else if (targetEl.value === "finish" && !this.options.sessionInProgress) {
            // Prevent double click
            if (button.disabled) {
                return;
            }

            // Adding pop-up before the survey is submitted when not in live session
            this.dialog.add(ConfirmationDialog, {
                title: _t("Submit confirmation"),
                body: _t("Are you sure you want to submit the survey?"),
                confirmLabel: _t("Submit"),
                confirm: () => {
                    button.disabled = true;
                    button.dataset.originalHtml = button.innerHTML;

                    // Rotating messages for submit button
                    const buttonMessages = [
                        '<span class="spinner-border spinner-border-sm me-2"></span> Processing...',
                        '<span class="spinner-border spinner-border-sm me-2"></span> Finalizing...'
                    ];
                    let btnMessageIndex = 0;
                    button.innerHTML = buttonMessages[0];

                    const btnInterval = setInterval(() => {
                        btnMessageIndex = (btnMessageIndex + 1) % buttonMessages.length;
                        button.innerHTML = buttonMessages[btnMessageIndex];
                    }, 2000);

                    // Store interval ID to clear it later
                    button.dataset.intervalId = btnInterval;

                    this.waitForTimeout(() => {
                        this.submitForm({ isFinish: true });
                    }, 0);
                },
                cancel: () => {},
            });
        } else if (targetEl.value === "finish") {
            button.disabled = true;
            button.dataset.originalHtml = button.innerHTML;

            // Rotating messages for submit button
            const buttonMessages = [
                '<span class="spinner-border spinner-border-sm me-2"></span> Processing...',
                '<span class="spinner-border spinner-border-sm me-2"></span> Finalizing...'
            ];
            let btnMessageIndex = 0;
            button.innerHTML = buttonMessages[0];

            const btnInterval = setInterval(() => {
                btnMessageIndex = (btnMessageIndex + 1) % buttonMessages.length;
                button.innerHTML = buttonMessages[btnMessageIndex];
            }, 2000);

            // Store interval ID to clear it later
            button.dataset.intervalId = btnInterval;

            this.submitForm({ isFinish: true });
        } else {
            this.submitForm();
        }
    }
})