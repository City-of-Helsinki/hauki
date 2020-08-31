import requests_cache
from django.core.management.base import BaseCommand, CommandError

from hours.importer.base import get_importers


class Command(BaseCommand):
    help = "Import data for opening hours"

    importer_types = ['connections', 'targets', 'openings']

    def __init__(self):
        super().__init__()
        self.importers = get_importers()
        self.imp_list = ', '.join(sorted(self.importers.keys()))
        self.missing_args_message = "Enter the name of the hours importer module. Valid importers: %s" % self.imp_list

    def add_arguments(self, parser):
        parser.add_argument('module', type=str)

        parser.add_argument('--cached', dest='cached', action='store_true', help='cache HTTP requests')
        parser.add_argument('--all', action='store_true', dest='all', help='Import all entities')
        parser.add_argument('--url', action='store', dest='url', help='Import from a given URL')
        parser.add_argument('--single', action='store', dest='single', help='Import only single entity')
        parser.add_argument('--date', action='store', dest='date', help='Import data starting at given date')
        parser.add_argument('--remap', action='store_true', dest='remap',
                            help='Remap all deleted entities to new ones')
        parser.add_argument('--force', action='store_true', dest='force',
                            help='Allow deleting any number of entities if necessary')

        for imp in self.importer_types:
            parser.add_argument('--%s' % imp, dest=imp, action='store_true', help='import %s' % imp)

    def handle(self, *args, **options):
        if options['cached']:
            requests_cache.install_cache('hours_import')
        module = options['module']
        if module not in self.importers:
            raise CommandError("Importer %s not found. Valid importers: %s" % (module, self.imp_list))
        imp_class = self.importers[module]
        importer = imp_class(options)

        # Activate the default language for the duration of the import
        # to make sure translated fields are populated correctly.
        # old_lang = get_language()
        # activate(settings.LANGUAGES[0][0])
        for imp_type in self.importer_types:
            print(imp_type)
            name = "import_%s" % imp_type
            method = getattr(importer, name, None)
            print(method)
            if options[imp_type]:
                if not method:
                    raise CommandError("Importer %s does not support importing %s" % (name, imp_type))
            else:
                if not options['all']:
                    continue

            if method:
                kwargs = {}
                url = options.pop('url', None)
                if url:
                    kwargs['url'] = url
                print('calling method')
                print(method)
                method(**kwargs)
