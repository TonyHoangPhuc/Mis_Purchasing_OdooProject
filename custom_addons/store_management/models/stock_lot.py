from odoo import models


class StockLot(models.Model):
    _inherit = "stock.lot"

    def _compute_expiration_date(self):
        regular_lots = self.filtered(lambda lot: not lot.env.context.get("skip_auto_expiry_defaults"))
        if regular_lots:
            super(StockLot, regular_lots)._compute_expiration_date()
        for lot in self - regular_lots:
            if not lot.expiration_date:
                lot.expiration_date = False

    def _compute_dates(self):
        regular_lots = self.filtered(lambda lot: not lot.env.context.get("skip_auto_expiry_defaults"))
        if regular_lots:
            super(StockLot, regular_lots)._compute_dates()
        for lot in self - regular_lots:
            if not lot.use_date:
                lot.use_date = False
            if not lot.removal_date:
                lot.removal_date = False
            if not lot.alert_date:
                lot.alert_date = False
