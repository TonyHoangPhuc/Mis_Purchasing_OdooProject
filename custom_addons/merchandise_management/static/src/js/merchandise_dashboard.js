/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATE_COLORS = {
    draft: "#6b7280",
    submitted: "#f59e0b",
    to_approve: "#f97316",
    approved: "#3b82f6",
    po_created: "#8b5cf6",
    done: "#10b981",
    rejected: "#ef4444",
    cancel: "#9ca3af",
};

const STATE_LABELS = {
    draft: "Nháp",
    submitted: "Đã gửi",
    to_approve: "Chờ duyệt",
    approved: "Đã duyệt",
    po_created: "Đang xử lý",
    done: "Hoàn tất",
    rejected: "Từ chối",
    cancel: "Đã hủy",
};

export class MerchandiseDashboard extends Component {
    static template = "merchandise_management.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            kpi: {},
            pipeline: [],
            activities: [],
        });
        onMounted(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        const data = await this.orm.call("merchandise.dashboard", "get_dashboard_data", []);
        this.state.kpi = data.kpi;
        this.state.pipeline = data.pipeline;
        this.state.activities = data.activities;
        this.state.loading = false;
    }

    refreshDashboard() {
        return this.loadDashboard();
    }

    getStateColor(state) {
        return STATE_COLORS[state] || "#6b7280";
    }

    getStateLabel(state) {
        return STATE_LABELS[state] || state;
    }

    getPipelineByState(stateKey) {
        return this.state.pipeline.filter((item) => item.state === stateKey);
    }

    stripHtml(html) {
        if (!html) {
            return "";
        }
        return html.replace(/<[^>]+>/g, "");
    }

    openPOList() {
        return this.action.doAction("merchandise_management.action_mer_po_management");
    }

    openPRPipeline() {
        return this.action.doAction("merchandise_management.action_mer_purchase_request");
    }

    openPRList(domain, name) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: name || "Yêu cầu PR",
            res_model: "mer.purchase.request",
            views: [[false, "list"], [false, "form"]],
            domain: domain || [],
            target: "current",
        });
    }

    openPRRecord(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mer.purchase.request",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openActivity(activity) {
        if (activity?.res_id) {
            return this.openPRRecord(activity.res_id);
        }
    }

    onKpiClick(key) {
        const domainMap = {
            draft: [["state", "=", "draft"]],
            pending: [["state", "in", ["submitted", "to_approve"]]],
            processing: [["state", "in", ["approved", "po_created"]]],
            done: [["state", "=", "done"]],
            rejected: [["state", "=", "rejected"]],
        };
        const nameMap = {
            draft: "PR nháp",
            pending: "PR chờ duyệt",
            processing: "PR đang xử lý",
            done: "PR hoàn tất",
            rejected: "PR từ chối",
        };

        if (key === "qc_rejected") {
            return this.action.doAction({
                type: "ir.actions.act_window",
                name: "Lô hàng lỗi",
                res_model: "stock.picking",
                views: [[false, "list"], [false, "form"]],
                domain: [["wm_qc_status", "=", "rejected"], ["state", "!=", "cancel"]],
                target: "current",
            });
        }

        return this.openPRList(domainMap[key], nameMap[key]);
    }
}

registry.category("actions").add("merchandise_dashboard", MerchandiseDashboard);
