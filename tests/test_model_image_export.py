import io
import os
import tempfile
from unittest.mock import patch

from PIL import Image

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import BinaryBytes


@tagged('post_install', '-at_install')
class TestModelImageExport(TransactionCase):

    def setUp(self):
        super().setUp()
        base_path = tempfile.TemporaryDirectory()
        self.addCleanup(base_path.cleanup)
        self.env['ir.config_parameter'].set_str('model_image_export.base_path', base_path.name)
        self.directory = os.path.join(base_path.name, 'Contact')

    def _image(self, color, image_format='PNG'):
        buffer = io.BytesIO()
        Image.new('RGB', (64, 64), color).save(buffer, image_format)
        return BinaryBytes(buffer.getvalue())

    def _partner(self, name, color='#ff0000'):
        return self.env['res.partner'].create({
            'name': name,
            'image_1920': color and self._image(color),
        })

    def _wizard(self, model='res.partner'):
        return self.env['image.export.wizard'].create({
            'model_id': self.env['ir.model']._get(model).id,
        })

    def _read(self, filename):
        with open(os.path.join(self.directory, filename), 'rb') as image_file:
            return image_file.read()

    def _log(self, record, field_name='image_1920'):
        return self.env['image.export.log'].search([
            ('model', '=', record._name), ('res_id', '=', record.id), ('field_name', '=', field_name),
        ])

    def test_wizard_info(self):
        wizard = self._wizard()
        self.assertEqual(wizard.image_field_names, 'image_1920')
        self.assertEqual(wizard.folder_name, 'Contact')
        self.assertEqual(wizard.target_path, self.directory)

    def test_export_writes_image_named_after_record(self):
        partner = self._partner('Mr John')
        self._wizard().action_export()
        self.assertEqual(self._read('Mr John.png'), partner.image_1920.content)
        log = self._log(partner)
        self.assertEqual(log.filename, 'Mr John.png')
        self.assertEqual(log.record_name, 'Mr John')
        self.assertTrue(partner.x_image_exported)

    def test_exported_record_is_skipped(self):
        partner = self._partner('Mr John')
        self._wizard().action_export()
        path = os.path.join(self.directory, 'Mr John.png')
        with open(path, 'wb') as image_file:
            image_file.write(b'marker')
        action = self._wizard().action_export()
        self.assertEqual(self._read('Mr John.png'), b'marker')
        self.assertIn('Exported: 0,', action['params']['message'])
        self.assertEqual(len(self._log(partner)), 1)

    def test_flagged_record_is_excluded(self):
        partner = self._partner('Mr John')
        self._wizard().action_export()
        os.remove(os.path.join(self.directory, 'Mr John.png'))
        self._wizard().action_export()
        self.assertFalse(os.path.exists(os.path.join(self.directory, 'Mr John.png')))
        partner.x_image_exported = False
        self._wizard().action_export()
        self.assertEqual(self._read('Mr John.png'), partner.image_1920.content)
        self.assertTrue(partner.x_image_exported)

    def test_duplicate_names_get_copy_suffix(self):
        partners = self._partner('Mrs Jane') + self._partner('Mrs Jane') + self._partner('Mrs Jane')
        self._wizard().action_export()
        self.assertEqual(
            sorted(self._log(partner).filename for partner in partners),
            ['Mrs Jane (copy).png', 'Mrs Jane (copy-1).png', 'Mrs Jane.png'],
        )
        another = self._partner('Mrs Jane')
        self._wizard().action_export()
        self.assertEqual(self._log(another).filename, 'Mrs Jane (copy-2).png')

    def test_record_without_image(self):
        partner = self._partner('No Photo', color=False)
        self._wizard().action_export()
        self.assertFalse(self._log(partner))
        self.assertFalse(os.path.exists(os.path.join(self.directory, 'No Photo.png')))
        self.assertFalse(partner.x_image_exported)

    def test_replaced_image_is_exported_after_flag_reset(self):
        partner = self._partner('Mr John')
        self._wizard().action_export()
        partner.write({'image_1920': self._image('#0000ff', 'JPEG'), 'x_image_exported': False})
        self._wizard().action_export()
        self.assertEqual(self._log(partner).filename, 'Mr John.jpg')
        self.assertEqual(self._read('Mr John.jpg'), partner.image_1920.content)
        self.assertFalse(os.path.exists(os.path.join(self.directory, 'Mr John.png')))

    def test_model_without_image_field(self):
        wizard = self._wizard('res.currency.rate')
        self.assertFalse(wizard.image_field_names)
        with self.assertRaises(UserError):
            wizard.action_export()

    def test_several_image_fields_use_record_folder(self):
        partner = self._partner('Mr John')
        wizard = self._wizard()
        with patch.object(
            type(wizard), '_get_image_field_names', lambda self: ['image_1920', 'image_128'],
        ):
            wizard.action_export()
        self.assertEqual(
            sorted(os.listdir(os.path.join(self.directory, 'Mr John'))),
            ['image_128.png', 'image_1920.png'],
        )
        self.assertEqual(self._log(partner, 'image_128').filename, os.path.join('Mr John', 'image_128.png'))
