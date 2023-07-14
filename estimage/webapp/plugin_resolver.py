import collections

from .. import PluginResolver


class WebappPluginResolver(PluginResolver):
    def __init__(self):
        super().__init__()
        self.template_dict = collections.defaultdict(list)

    def resolve_extension(self, plugin):
        super().resolve_extension(plugin)
        self.resolve_templates_extension(plugin)

    def resolve_templates_extension(self, plugin):
        template_extensions = getattr(plugin, "TEMPLATE_EXPORTS", dict())
        for name, extended_by in template_extensions.items():
            self.template_dict[name].append(extended_by)

    def get_extended_templates(self, env):
        for name, extensions in self.template_dict.items():
            compiled_template = env.get_template(f"{name}.html")
            for extension in extensions:
                compiled_template = env.get_template(f"{name}.html")

