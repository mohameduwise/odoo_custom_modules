
import { patch } from '@web/core/utils/patch';
import {SurveyForm} from '@survey/interactions/survey_form'
import { fadeIn, fadeOut } from "@survey/utils";
import { rpc } from "@web/core/network/rpc";

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
     *   screen transition
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
            this._showLoadingOverlay();
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

    _showLoadingOverlay() {
        const loadingHtml = `
            <div class="o_survey_loading_screen">
                <div class="o_survey_loading_content">
                    <div class="o_survey_spinner"></div>
                    <h3>Processing your response...</h3>
                    <p>Please wait</p>
                </div>
            </div>
        `;
        $('body').append(loadingHtml);
    }

})