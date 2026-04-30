import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";

const STORAGE_KEY = "warehouse_management.hide_app_switcher";

class AppSwitcherToggle extends Component {
    static template = "warehouse_management.AppSwitcherToggle";
    static props = {};

    setup() {
        this.state = useState({ hidden: false });
        onMounted(() => {
            this.state.hidden = window.localStorage.getItem(STORAGE_KEY) === "1";
            this._applyState();
        });
    }

    toggleAppSwitcher() {
        this.state.hidden = !this.state.hidden;
        window.localStorage.setItem(STORAGE_KEY, this.state.hidden ? "1" : "0");
        this._applyState();
    }

    _applyState() {
        document.body.classList.toggle("o_hide_app_switcher", this.state.hidden);
    }
}

registry.category("systray").add(
    "warehouse_management_app_switcher_toggle",
    { Component: AppSwitcherToggle },
    { sequence: 1 }
);
