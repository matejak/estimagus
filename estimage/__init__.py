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

    def add_overridable_class(self, name, cls):
        self.class_dict[name] = cls

    def add_known_overridable_classes(self):
        for name, cls in self.EXTENDABLE_CLASSES.items():
            self.class_dict[name] = cls

    def get_class(self, name):
        return self.class_dict[name]

    def resolve_overrides(self, plugin):
        self.resolve_class_overrides(plugin)

    def resolve_class_overrides(self, plugin):
        for cls_name in self.class_dict:
            self._resolve_possible_class_override(cls_name, plugin)

    def _resolve_possible_class_override(self, cls_name, plugin):
        exposed_exports = getattr(plugin, "EXPORTS", dict())

        plugin_doesnt_export_current_symbol = cls_name not in exposed_exports
        if plugin_doesnt_export_current_symbol:
            return

        plugin_local_symbol_name = exposed_exports[cls_name]
        override = getattr(plugin, plugin_local_symbol_name, None)
        if override is None:
            msg = (
                    f"Looking for exported symbol '{plugin_local_symbol_name}', "
                    "which was not found")
            raise ValueError(msg)
        self._update_class_with_override(cls_name, override)

    def _update_class_io_with_override(self, new_class, original_class, override):
        if original_class not in persistence.LOADERS or original_class not in persistence.LOADERS:
            return

        for backend, loader in persistence.LOADERS[original_class].items():
            if override_loader := persistence.LOADERS[override].get(backend, None):
                fused_loader = type("loader", (override_loader, loader), dict())
                persistence.LOADERS[new_class][backend] = fused_loader

    def _update_class_with_override(self, cls_name, override):
        our_value = self.class_dict[cls_name]
        new_class = type(cls_name, (override, our_value), dict())
        self.class_dict[cls_name] = new_class
        self._update_class_io_with_override(new_class, our_value, override)
