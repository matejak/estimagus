from . import persistence


class PluginResolver:
    EXTENDABLE_CLASSES = dict()

    def __init__(self):
        self.class_dict = dict()
        self.global_symbol_prefix = ""

    @classmethod
    def class_is_extendable(cls, name):
        def wrapper(extendable):
            cls.EXTENDABLE_CLASSES[name] = extendable
            return extendable
        return wrapper

    def add_extendable_class(self, name, cls):
        self.class_dict[name] = cls

    def add_known_extendable_classes(self):
        for name, cls in self.EXTENDABLE_CLASSES.items():
            self.class_dict[name] = cls

    def get_class(self, name):
        return self.class_dict[name]

    def resolve_extension(self, plugin):
        self.resolve_class_extension(plugin)

    def resolve_class_extension(self, plugin):
        for class_type in self.class_dict:
            self._resolve_possible_class_extension(class_type, plugin)

    def _resolve_possible_class_extension(self, class_type, plugin):
        exposed_exports = getattr(plugin, "EXPORTS", dict())

        plugin_doesnt_export_current_symbol = class_type not in exposed_exports
        if plugin_doesnt_export_current_symbol:
            return

        plugin_local_symbol_name = exposed_exports[class_type]
        extension = getattr(plugin, plugin_local_symbol_name, None)
        if extension is None:
            msg = (
                    f"Looking for exported symbol '{plugin_local_symbol_name}', "
                    "which was not found")
            raise ValueError(msg)
        self._update_class_with_extension(class_type, extension)

    def _update_class_io_with_extension(self, new_class, original_class, extension):
        for backend, loader in persistence.LOADERS[original_class].items():
            fused_loader = loader
            if extension_loader := persistence.LOADERS[extension].get(backend, None):
                fused_loader = type("loader", (extension_loader, loader), dict())
            persistence.LOADERS[new_class][backend] = fused_loader

        for backend, saver in persistence.SAVERS[original_class].items():
            fused_saver = saver
            if extension_saver := persistence.SAVERS[extension].get(backend, None):
                fused_saver = type("saver", (extension_saver, saver), dict())
            persistence.SAVERS[new_class][backend] = fused_saver

    def _update_class_with_extension(self, class_type, extension):
        our_value = self.class_dict[class_type]
        extension_module_name = extension.__module__.split('.')[-1]
        class_name = f"{our_value.__name__}_{extension_module_name}"
        if self.global_symbol_prefix:
            class_name = f"{self.global_symbol_prefix}__{class_name}"
        new_class = type(class_name, (extension, our_value), dict())
        globals()[class_name] = new_class
        self.class_dict[class_type] = new_class
        self._update_class_io_with_extension(new_class, our_value, extension)
