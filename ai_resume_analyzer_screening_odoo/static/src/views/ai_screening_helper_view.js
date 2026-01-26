import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Component, onWillStart, useState } from "@odoo/owl";

export class AIScreeningActionHelper extends Component {
    static template = "ai_resume_analyzer_screening_odoo.AIScreeningActionHelper";
    static props = ["noContentHelp"];
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            hasDemoData: false,
            isRecruitmentUser: false,
        });
        onWillStart(async () => {
            const categoryTags = await this.orm.searchRead("hr.applicant.category", [], ["name"]);
            const demoTag = categoryTags.filter((tag) => tag.name === "AI Screening Demo");
            this.state.hasDemoData = demoTag.length === 1;
            this.state.isRecruitmentUser = await user.hasGroup("hr_recruitment.group_hr_recruitment_user");
        });
    }

    loadAIScreeningScenario() {
        this.actionService.doAction("ai_resume_analyzer_screening_odoo.action_load_ai_screening_sample_data");
    }

    actionCreateScreening() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "ai.resume.screening",
            views: [[false, "form"]],
            target: "current",
        });
    }
}
