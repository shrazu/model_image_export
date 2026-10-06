# Model Image Export

Odoo 20 module that exports the images of any model to a folder on the server.

In developer mode, open **Settings → Technical → Image Export → Export Images**, pick a model and click **Export**. The images of all its records are written to `<base path>/<Model name>/`, for example `Employee/` for `hr.employee`.

- Files are named after the record. Duplicate names get a `(copy)`, `(copy-1)`, … suffix.
- Only real image fields are exported; automatically resized copies (`image_1024`, `image_512`, …) are ignored.
- When a model has several image fields, each record gets its own folder and the files are named after the fields.
- A boolean field `x_image_exported` is added to the selected model and set on each exported record. Flagged records are left out of the next run; untick the flag to export a record again.
- **Exported Images** in the same menu lists the files written.

The wizard is restricted to the Settings administrator group.

## Configuration

The base folder is the system parameter `model_image_export.base_path` (default `/opt/odoo/photos`). The Odoo server process must be able to write to it.

## Requirements

Odoo 20, `base` module only.

## License

LGPL-3
