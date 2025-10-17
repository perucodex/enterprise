# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from random import sample

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    iot_scale_ids = fields.Many2many(
        'iot.device',
        string="Scales",
        domain=[('type', '=', 'scale')],
        help="Choose the scales you want to use for this operation type. Those scales can be used to weigh the packages created."
    )
    auto_print_carrier_labels = fields.Boolean(
        "Auto Print Carrier Labels",
        help="If this checkbox is ticked, Odoo will automatically print the carrier labels of the picking when they are created. Note this requires a printer to be assigned to this report.")
    auto_print_export_documents = fields.Boolean(
        "Auto Print Export Documents",
        help="If this checkbox is ticked, Odoo will automatically print the export documents of the picking when they are created. Availability of export documents depends on the carrier and the destination. Note this requires a printer to be assigned to this report. ")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    allowed_printer_ids = fields.Many2many(
        'iot.device', default=lambda self: self._get_allowed_printer_ids(), store=False
    )

    def _get_allowed_printer_ids(self):
        report = self.env['ir.actions.report']
        return (
            report._get_report_from_name('delivery_iot.report_shipping_labels').device_ids.ids
            + report._get_report_from_name('delivery_iot.report_shipping_docs').device_ids.ids
        )

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        for attachment in message.attachment_ids:
            if (
                (self.picking_type_id.auto_print_carrier_labels and 'Label' in attachment.name)
                or (self.picking_type_id.auto_print_export_documents and 'ShippingDoc' in attachment.name)
            ):
                self.print_attachment(attachment)
        return message

    def print_attachment(self, attachments):
        res_user_printers = json.loads(
            self.env['ir.config_parameter'].sudo().get_param('delivery_iot.res_user_printers', '{}')
        )
        printer_identifier = res_user_printers.get(str(self.env.user.id))

        if printer_identifier:
            iot_box_identifier = self.env['iot.device'].sudo().search(
                [('identifier', '=', printer_identifier)], limit=1
            ).iot_id.identifier
        elif not self.allowed_printer_ids:
            return
        else:
            printer_identifier = self.allowed_printer_ids[0].identifier
            iot_box_identifier = self.allowed_printer_ids[0].iot_id.identifier

        self.env['iot.channel'].send_message({
            'iotDevice': {
                'iotIdentifiers': [iot_box_identifier],
                'identifiers': [{'identifier': printer_identifier}],
            },
            'print_id': 0,
            'document': attachments.datas,
        })
