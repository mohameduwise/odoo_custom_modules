import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { AIScreeningActionHelper } from "@ai_resume_analyzer_screening_odoo/views/ai_screening_helper_view";
import { registry } from "@web/core/registry";

export class AIScreeningKanbanRenderer extends KanbanRenderer {
    static template = "ai_resume_analyzer_screening_odoo.AIScreeningKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        AIScreeningActionHelper,
    };
}

export const AIScreeningKanbanView = {
    ...kanbanView,
    Renderer: AIScreeningKanbanRenderer,
};

registry.category("views").add("ai_screening_kanban", AIScreeningKanbanView);
