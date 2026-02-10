/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";


/**
 * Patch the website form interaction to disable file validation
 */
const websiteForm = registry.category("public.interactions").get("website.form");

patch(websiteForm.prototype, {

    isFileInputValid(inputEl) {

        return true;
    },
});
