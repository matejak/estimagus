from . import persistence


class PluginResolver:
    EXTENDABLE_CLASSES = dict()

    def __init__(self):
        self.class_dict = dict()

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
        for cls_name in self.class_dict:
            self._resolve_possible_class_extension(cls_name, plugin)

    def _resolve_possible_class_extension(self, cls_name, plugin):
        exposed_exports = getattr(plugin, "EXPORTS", dict())

        plugin_doesnt_export_current_symbol = cls_name not in exposed_exports
        if plugin_doesnt_export_current_symbol:
            return

        plugin_local_symbol_name = exposed_exports[cls_name]
        extension = getattr(plugin, plugin_local_symbol_name, None)
        if extension is None:
            msg = (
                    f"Looking for exported symbol '{plugin_local_symbol_name}', "
                    "which was not found")
            raise ValueError(msg)
        self._update_class_with_extension(cls_name, extension)

    def _update_class_io_with_extension(self, new_class, original_class, extension):
        if original_class not in persistence.LOADERS or original_class not in persistence.LOADERS:
            return

        for backend, loader in persistence.LOADERS[original_class].items():
            if extension_loader := persistence.LOADERS[extension].get(backend, None):
                fused_loader = type("loader", (extension_loader, loader), dict())
                persistence.LOADERS[new_class][backend] = fused_loader

        for backend, saver in persistence.SAVERS[original_class].items():
            if extension_saver := persistence.SAVERS[extension].get(backend, None):
                fused_saver = type("saver", (extension_saver, saver), dict())
                persistence.SAVERS[new_class][backend] = fused_saver

    def _update_class_with_extension(self, cls_name, extension):
        our_value = self.class_dict[cls_name]
        new_class = type(cls_name, (extension, our_value), dict())
        self.class_dict[cls_name] = new_class
        self._update_class_io_with_extension(new_class, our_value, extension)
