import collections

from . import persistence


class PluginResolver:
    EXTENDABLE_CLASSES = dict()

    def __init__(self):
        self.class_dict = dict()
        self.class_names = collections.defaultdict(tuple)
        self.class_bases = collections.defaultdict(tuple)
        self.subclass_dict = dict()
        self.global_symbol_prefix = ""

    @classmethod
    def class_is_extendable(cls, name):
        def wrapper(extendable):
            cls.EXTENDABLE_CLASSES[name] = extendable
            return extendable
        return wrapper

    def add_extendable_class(self, name, cls):
        self.class_dict[name] = cls
        self.class_bases[name] = (cls,)

    def add_known_extendable_classes(self):
        for name, cls in self.EXTENDABLE_CLASSES.items():
            self.add_extendable_class(name, cls)

    def get_class(self, name):
        return self.class_dict[name]

    def resolve_extension(self, plugin, override=None):
        if override:
            exposed_exports = override
        else:
            exposed_exports = getattr(plugin, "EXPORTS", dict())

        for class_name in self.class_dict:
            self.resolve_class_extension(class_name, plugin, exposed_exports)

    def resolve_class_extension(self, class_name, plugin, exposed_exports):
        plugin_doesnt_export_current_symbol = class_name not in exposed_exports
        if plugin_doesnt_export_current_symbol:
            return

        plugin_local_symbol_name = exposed_exports[class_name]
        class_extension = getattr(plugin, plugin_local_symbol_name, None)
        if class_extension is None:
            msg = (
                    f"Looking for exported symbol '{plugin_local_symbol_name}', "
                    "which was not found")
            raise ValueError(msg)
        self._update_class_with_extension(class_name, class_extension)

    # TODO: Refactor
    # What this should do:
    # given an extension class and an original (maybe extended) class, extend the loader of the original class by the loader of the extended class
    # If the extension doesn't define a loader, give it the loader of the very base (or should it examine the mro and dynamically generate the loader?)
    # Register newly determined loaders
    def _update_class_saver_or_loader_with_extension(self, structure, class_name, new_class, original_class, extension):
        know_extension = extension in structure
        for backend, saver_or_loader in structure[original_class].items():
            know_backend = backend in structure[extension]
            extended_saver_or_loader = saver_or_loader
            if know_extension and know_backend:
                foo = structure[extension][backend]
                extension_already_incorporated = issubclass(saver_or_loader, foo)
                if not extension_already_incorporated:
                    extended_saver_or_loader = type("saver_or_loader", (foo, saver_or_loader), dict())
            else:
                fallback_saver_or_loader = structure[self.EXTENDABLE_CLASSES[class_name]][backend]
                structure[extension][backend] = fallback_saver_or_loader
            structure[new_class][backend] = extended_saver_or_loader

    def _update_class_io_with_extension(self, class_name, new_class, original_class, extension):
        self._update_class_saver_or_loader_with_extension(persistence.LOADERS, class_name, new_class, original_class, extension)
        self._update_class_saver_or_loader_with_extension(persistence.SAVERS, class_name, new_class, original_class, extension)

    def _register_class_to_enable_caching(self, class_name, cls):
        globals()[class_name] = cls

    def _create_class(self, class_name):
        new_class_name = self.global_symbol_prefix
        base_and_extensions_string = "__".join(self.class_names[class_name])
        new_class_name += f"__{base_and_extensions_string}"
        new_class = type(new_class_name, self.class_bases[class_name], dict())
        return new_class

    def get_final_class(self, name):
        return self.class_dict[name]

    def _process_extension(self, class_name, extension):
        extension_module_name = extension.__module__.split('.')[-1]
        self.class_names[class_name] = (f"{extension_module_name}_{extension.__name__}",) + self.class_names[class_name]
        self.class_bases[class_name] = (extension,) + self.class_bases[class_name]

    def _update_class_with_extension(self, class_name, extension):
        original_class = self.get_final_class(class_name)
        self._process_extension(class_name, extension)
        new_class = self._create_class(class_name)
        self._register_class_to_enable_caching(class_name, new_class)
        self.class_dict[class_name] = new_class
        self._update_class_io_with_extension(class_name, new_class, original_class, extension)
