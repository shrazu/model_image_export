from odoo import fields, models


class ImageExportLog(models.Model):
    _name = 'image.export.log'
    _description = "Exported Image"
    _order = 'id desc'
    _rec_name = 'filename'

    model = fields.Char(string="Model", required=True, index=True, readonly=True)
    res_id = fields.Integer(string="Record ID", required=True, readonly=True)
    field_name = fields.Char(string="Image Field", required=True, readonly=True)
    record_name = fields.Char(
        string="Export Name", required=True, readonly=True,
        help="File or folder name given to the record in the model's export folder.",
    )
    filename = fields.Char(
        string="File", required=True, readonly=True,
        help="Path of the exported file, relative to the model's export folder.",
    )
    checksum = fields.Char(string="Checksum", readonly=True)
    export_date = fields.Datetime(string="Exported On", default=fields.Datetime.now, readonly=True)

    _record_field_uniq = models.Constraint(
        'unique(model, res_id, field_name)',
        "An image field of a record can only be logged once.",
    )
