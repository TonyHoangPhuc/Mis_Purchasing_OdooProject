from datetime import timedelta

from odoo import api, fields, models


class MerchandiseDashboard(models.AbstractModel):
    _name = "merchandise.dashboard"
    _description = "Merchandise Dashboard Data"

    @api.model
    def _format_relative_datetime(self, value):
        if not value:
            return ""

        now = fields.Datetime.now()
        delta = now - value

        if delta < timedelta(minutes=1):
            return "Vừa xong"
        if delta < timedelta(hours=1):
            return f"{int(delta.total_seconds() // 60)} phút trước"
        if delta < timedelta(days=1):
            return f"{int(delta.total_seconds() // 3600)} giờ trước"
        return f"{delta.days} ngày trước"

    @api.model
    def get_dashboard_data(self):
        purchase_request_model = self.env["mer.purchase.request"]

        total_draft = purchase_request_model.search_count([("state", "=", "draft")])
        total_pending = purchase_request_model.search_count([("state", "in", ["submitted", "to_approve"])])
        total_processing = purchase_request_model.search_count([("state", "in", ["approved", "po_created"])])
        total_done = purchase_request_model.search_count([("state", "=", "done")])
        total_rejected = purchase_request_model.search_count([("state", "=", "rejected")])
        qc_rejected = self.env["stock.picking"].search_count(
            [("wm_qc_status", "=", "rejected"), ("state", "!=", "cancel")]
        )

        recent_prs = purchase_request_model.search([], order="date_request desc, id desc", limit=24)
        pipeline = []
        for request in recent_prs:
            if "store_id" in request._fields and request.store_id:
                location_name = request.store_id.name
            else:
                location_name = request.warehouse_id.name if request.warehouse_id else ""

            pipeline.append(
                {
                    "id": request.id,
                    "name": request.name,
                    "state": request.state,
                    "state_label": dict(request._fields["state"].selection).get(request.state, request.state),
                    "store": location_name,
                    "date": request.date_request.strftime("%d/%m/%Y") if request.date_request else "",
                    "user": request.user_id.name if request.user_id else "",
                    "purchase_order_count": getattr(request, "purchase_order_count", 0),
                    "internal_picking_count": getattr(request, "internal_picking_count", 0),
                }
            )

        messages = self.env["mail.message"].search(
            [("model", "=", "mer.purchase.request"), ("message_type", "in", ["comment", "email"])],
            order="date desc",
            limit=15,
        )
        activities = []
        for message in messages:
            body = message.body or ""
            activities.append(
                {
                    "id": message.id,
                    "res_id": message.res_id,
                    "author": message.author_id.name if message.author_id else "Hệ thống",
                    "date": fields.Datetime.to_string(message.date),
                    "date_label": self._format_relative_datetime(message.date),
                    "body_short": body[:160],
                    "is_qc_reject": "lỗi" in body.lower() or "qc" in body.lower(),
                }
            )

        return {
            "kpi": {
                "draft": total_draft,
                "pending": total_pending,
                "processing": total_processing,
                "done": total_done,
                "rejected": total_rejected,
                "qc_rejected": qc_rejected,
            },
            "pipeline": pipeline,
            "activities": activities,
        }
