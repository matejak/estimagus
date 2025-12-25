Plugins
=======

Estimagus features a powerful plugin system.
The point is to have simple base code that doesn't use extensive configuration, at the same time allowing users to customize the behavior according to their needs.
Exising entities and existing functionality follows the `open for extension, closed for modification` principle.


Overview
--------

Plugins are mainly about extending classes.
A plugin is a Python module that is loaded by the plugin resolver (PluginResolver).
The resolver processes the module, and if it determines that it contains classes intended to extend existing classes, it creates a the extended type dynamically.
When the resolver is asked for the particular class, it returns an extension that is extended by all of the active plugins in the order plugins were specified.


Plugin
++++++

The plugin has to define a mapping ``EXPORTS``.
It maps from the set of base type names to the set of names of classes defined in that plugin module.

If the plugin extends the web interface, it can also define a mapping ``TEMPLATE_OVERRIDES``.
It maps from the set of base template names to the set of names of templates in the ``templates`` subdirectory of the plugin module.
Such extending templates may have ``{% extends ancestor_of_<plugin name> %}`` if they should extend whoever the actual parent is (it can even be an extension of another plugin).


Application
+++++++++++

Classes that can be extended are marked as such using the ``@PluginResolver.class_is_extendable("<name>")`` decorator.
The name then matches the name in the ``EXPORTS`` mapping source.

At some point, you need to load plugins.
Typically, plugins are known, and are loaded using the ``estimage.get_plugin`` function.
Then, they are fed to the resolver using ``resolver.resolve_extension``.
The last thing to do is to ask resolver for the type, so it can either pass the base one, or the extended using ``resolver.get_final_class``.
