import hashlib
import mimetypes
import os

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import split_every
from odoo.tools.osutil import clean_filename


FLAG_FIELD = 'x_image_exported'


class ImageExportWizard(models.TransientModel):
    _name = 'image.export.wizard'
    _description = "Export Images"

    model_id = fields.Many2one(
        'ir.model', string="Model", required=True, ondelete='cascade',
        domain=[('transient', '=', False), ('abstract', '=', False)],
    )
    image_field_names = fields.Char(string="Image Fields", compute='_compute_export_info')
    folder_name = fields.Char(string="Folder Name", compute='_compute_export_info')
    target_path = fields.Char(string="Export Folder", compute='_compute_export_info')

    @api.depends('model_id')
    def _compute_export_info(self):
        base_path = self.env['ir.config_parameter'].sudo().get_str('model_image_export.base_path')
        for wizard in self:
            field_names = wizard._get_image_field_names()
            wizard.image_field_names = ', '.join(field_names)
            wizard.folder_name = wizard._get_folder_name()
            wizard.target_path = bool(base_path and wizard.folder_name) and os.path.join(base_path, wizard.folder_name)

    def _get_image_field_names(self):
        """ Stored image fields of the model, without the resized copies of another field. """
        self.ensure_one()
        if not self.model_id or self.model_id.model not in self.env:
            return []
        return [
            name
            for name, field in self.env[self.model_id.model]._fields.items()
            if isinstance(field, fields.Image) and field.store and not field.related
        ]

    def _get_folder_name(self):
        self.ensure_one()
        if not self.model_id:
            return False
        return clean_filename(self.model_id.with_context(lang='en_US').name)

    def _ensure_flag_field(self):
        """ Add the "Image Exported" flag to the selected model if it is missing. """
        self.ensure_one()
        if FLAG_FIELD not in self.env[self.model_id.model]._fields:
            self.env['ir.model.fields'].sudo().create({
                'name': FLAG_FIELD,
                'field_description': "Image Exported",
                'model_id': self.model_id.id,
                'ttype': 'boolean',
                'state': 'manual',
                'copied': False,
                'help': "Set once the images of this record have been exported. "
                        "Flagged records are left out of the next image export.",
            })

    @staticmethod
    def _get_unique_stem(stem, used_stems):
        """ Return ``stem``, or ``stem (copy)``, ``stem (copy-1)``, ... when taken. """
        if stem not in used_stems:
            return stem
        candidate = f"{stem} (copy)"
        index = 0
        while candidate in used_stems:
            index += 1
            candidate = f"{stem} (copy-{index})"
        return candidate

    @staticmethod
    def _get_image_checksum(image):
        return hashlib.sha1(image.content).hexdigest()

    def action_export(self):
        self.ensure_one()
        field_names = self._get_image_field_names()
        if not field_names:
            raise UserError(self.env._("%(model)s has no image field.", model=self.model_id.name))
        directory = self.target_path
        if not directory:
            raise UserError(self.env._(
                "No export folder is configured. Set the system parameter 'model_image_export.base_path'."
            ))
        try:
            os.makedirs(directory, exist_ok=True)
            used_stems = {
                entry.name if entry.is_dir() else os.path.splitext(entry.name)[0]
                for entry in os.scandir(directory)
            }
        except OSError as error:
            raise UserError(self.env._(
                "The export folder %(path)s cannot be used: %(error)s",
                path=directory, error=error.strerror,
            ))

        # one folder per record as soon as a record can hold several images
        folder_per_record = len(field_names) > 1
        ExportLog = self.env['image.export.log']
        logs_by_record = {}
        for log in ExportLog.search([('model', '=', self.model_id.model)]):
            logs_by_record.setdefault(log.res_id, {})[log.field_name] = log
            # names already given to records, even if the file is gone
            used_stems.add(log.record_name)

        self._ensure_flag_field()
        Model = self.env[self.model_id.model]
        exported = skipped = without_image = 0
        flagged = Model.search_count([(FLAG_FIELD, '=', True)])
        for record_ids in split_every(100, Model.search([(FLAG_FIELD, '=', False)]).ids):
            records = Model.browse(record_ids)
            done_ids = []
            for record in records:
                record_logs = logs_by_record.get(record.id, {})
                stem = next((log.record_name for log in record_logs.values()), None)
                has_image = False
                for field_name in field_names:
                    image = record[field_name]
                    if not image:
                        continue
                    has_image = True
                    log = record_logs.get(field_name)
                    checksum = self._get_image_checksum(image)
                    if log and log.checksum == checksum and os.path.isfile(os.path.join(directory, log.filename)):
                        skipped += 1
                        continue
                    if not stem:
                        stem = self._get_unique_stem(clean_filename(record.display_name or ''), used_stems)
                        used_stems.add(stem)
                    extension = mimetypes.guess_extension(image.mimetype or '') or '.png'
                    if folder_per_record:
                        filename = os.path.join(stem, field_name + extension)
                    else:
                        filename = stem + extension
                    path = os.path.join(directory, filename)
                    try:
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, 'wb') as image_file:
                            image_file.write(image.content)
                        if log and log.filename != filename:
                            # the replaced image has another format
                            old_path = os.path.join(directory, log.filename)
                            if os.path.isfile(old_path):
                                os.remove(old_path)
                    except OSError as error:
                        raise UserError(self.env._(
                            "The image of %(record)s could not be written to %(path)s: %(error)s",
                            record=record.display_name, path=directory, error=error.strerror,
                        ))
                    values = {
                        'record_name': stem,
                        'filename': filename,
                        'checksum': checksum,
                        'export_date': fields.Datetime.now(),
                    }
                    if log:
                        log.write(values)
                    else:
                        ExportLog.create({
                            'model': record._name,
                            'res_id': record.id,
                            'field_name': field_name,
                            **values,
                        })
                    exported += 1
                if has_image:
                    done_ids.append(record.id)
                else:
                    without_image += 1
            Model.browse(done_ids).write({FLAG_FIELD: True})
            records.invalidate_recordset()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Image Export"),
                'message': self.env._(
                    "Exported: %(exported)s, already exported: %(skipped)s, records without image: %(without_image)s. Folder: %(path)s",
                    exported=exported, skipped=skipped + flagged, without_image=without_image, path=directory,
                ),
                'type': 'success' if exported else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
