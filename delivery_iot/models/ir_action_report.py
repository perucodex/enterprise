import json
from odoo import models


class IrActionReport(models.Model):
    _inherit = 'ir.actions.report'

    def render_document(self, device_id_list, res_ids, data=None):
        """Send the dictionary in message to the iot_box via websocket,
        or return the data to be sent by longpolling.
        """
        # only override the method for delivery_iot reports
        if self.report_name not in ['delivery_iot.report_shipping_labels', 'delivery_iot.report_shipping_docs']:
            return super().render_document(device_id_list, res_ids, data)

        # set the default printer id in the system parameters for auto printing
        icp_sudo = self.env['ir.config_parameter'].sudo()
        res_user_printers = json.loads(icp_sudo.get_param('delivery_iot.res_user_printers', '{}'))

        device_ids = self.env['iot.device'].browse(device_id_list)
        for device in device_ids:
            res_user_printers[str(self.env.user.id)] = device.identifier
        icp_sudo.set_param('delivery_iot.res_user_printers', json.dumps(res_user_printers))

        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.picking'),
            ('res_id', 'in', res_ids),
            '|', ('name', 'ilike', '%.zplii'), ('name', 'ilike', '%.zpl'),
        ], order='id desc', limit=1)
        if not attachment:
            return []

        return [{
            "iotBoxId": device.iot_id.id,
            "deviceId": device.id,
            "deviceIdentifier": device.identifier,
            "deviceName": device.display_name,
            "document": attachment.datas,
        } for device in device_ids]  # As it is called via JS, we format keys to camelCase
