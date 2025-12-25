Persistence
===========

Estimagus aims to be as stateless as possible.
Users obviously want to work with states to configure it, but when it comes to processing data, the goal is to be able to deduce everything from a dataset that is imported once.
Nevertheless, things need to be saved and loaded, and Estimagus is prepared for that.


Estimagus defines the :class:`estimage.persistence.abstract.Saver` and :class:`estimage.persistence.abstract.Loader` to help with IO.
