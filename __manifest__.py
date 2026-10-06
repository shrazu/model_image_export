{
    'name': 'Model Image Export',
    'summary': 'Export the images of any model to a folder on the server',

    'description': """
Model Image Export
==================

Adds an "Export Images" wizard under Settings > Technical > Image Export.
The user picks a model; the images of all its records are written to a
folder named after the model, under the path set in the
``model_image_export.base_path`` system parameter. Images that were already
exported are skipped.
    """,

    'author': 'Shamim Hossen',

    'category': 'Tools',
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',

    # Required modules
    'depends': [
        'base',
    ],

    # Data files
    'data': [
        'security/ir.access.csv',
        'data/ir_config_parameter.xml',
        'views/image_export_wizard_views.xml',
        'views/image_export_log_views.xml',
        'views/menus.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
