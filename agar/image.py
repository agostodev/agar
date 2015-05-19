"""
The ``agar.image`` module contains classes to help work with images stored in the `Blobstore`_.
"""

from __future__ import with_statement

import logging
import mimetypes
import urlparse

from google.appengine.api import images, memcache, files, urlfetch
from google.appengine.api.images import NotImageError

from google.appengine.ext import db, blobstore, ndb

from agar.config import Config


IMAGE_HEADER_SIZE = 50000
TESTBED_INSTANCE = None


class ImageConfig(Config):
    """
    :py:class:`~agar.config.Config` settings for the ``agar.image`` library.
    Settings are under the ``agar_image`` namespace.

    The following settings (and defaults) are provided::

        agar_image_SERVING_URL_TIMEOUT = 60*60
        agar_image_SERVING_URL_LOOKUP_TRIES = 3
        agar_image_VALID_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif']

    To override ``agar.image`` settings, define values in the ``appengine_config.py`` file in the root of your project.
    """
    _prefix = 'agar_image'

    #: How long (in seconds) to cache the image serving URL (Default: ``60*60`` or one hour).
    SERVING_URL_TIMEOUT = 60*60
    #: How many times to try to download an image from a URL (Default: ``3``).
    SERVING_URL_LOOKUP_TRIES = 3
    #: Valid image mime types (Default: ``['image/jpeg', 'image/png', 'image/gif']``).
    VALID_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif']

#: **DEPRECATED** Use `~agar.image.ImageConfig.get_config`. The configuration object for ``agar.image`` settings.
config = ImageConfig.get_config(_cache=True)


class BaseImage(object):
    @property
    def image(self):
        """
        The Google `Image`_ entity for the image.
        """
        if self.blob_key is not None:
            return images.Image(blob_key=self.blob_key)
        return None

    @property
    def format(self):
        """
        The format of the image (see `Image.format`_ for possible values).
        If there is no image data, this will be ``None``.
        """
        if self.image is not None:
            try:
                return self.image.format
            except NotImageError:
                data = blobstore.fetch_data(self.blob_key, 0, IMAGE_HEADER_SIZE)
                img = images.Image(image_data=data)
                return img.format
        return None

    @property
    def width(self):
        """
        The width of the image in pixels (see `Image.width`_ for more documentation).
        If there is no image data, this will be ``None``.
        """
        if self.image is not None:
            try:
                return self.image.width
            except NotImageError:
                data = blobstore.fetch_data(self.blob_key, 0, IMAGE_HEADER_SIZE)
                img = images.Image(image_data=data)
                return img.width
        return None

    @property
    def height(self):
        """
        The height of the image in pixels (see `Image.height`_ for more documentation).
        If there is no image data, this will be ``None``.
        """
        if self.image is not None:
            try:
                return self.image.height
            except NotImageError:
                data = blobstore.fetch_data(self.blob_key, 0, IMAGE_HEADER_SIZE)
                img = images.Image(image_data=data)
                return img.height
        return None

    @property
    def image_data(self):
        """
        The raw image data as returned by a `BlobReader`_.
        If there is no image data, this will be ``None``.
        """
        if self.blob_key is not None:
            return blobstore.BlobReader(self.blob_key).read()
        return None

    def get_serving_url(self, size=None, crop=False, secure_url=None):
        """
        Returns the serving URL for the image. It works just like the `Image.get_serving_url`_ function,
        but adds caching. The cache timeout is controlled by the :py:attr:`.SERVING_URL_TIMEOUT` setting.

        :param size: An integer supplying the size of resulting images.
            See `Image.get_serving_url`_ for more detailed argument information.
        :param crop: Specify ``true`` for a cropped image, and ``false`` for a re-sized image.
            See `Image.get_serving_url`_ for more detailed argument information.
        :param secure_url: Specify ``true`` for a https url.
            See `Image.get_serving_url`_ for more detailed argument information.
        :return: The serving URL for the image (see `Image.get_serving_url`_ for more detailed information).
        """
        config = ImageConfig.get_config(_cache=True)
        serving_url = None
        if self.blob_key is not None:
            namespace = "agar-image-serving-url"
            key = "%s-%s-%s" % (self.model_key, size, crop)
            serving_url = memcache.get(key, namespace=namespace)
            if serving_url is None:
                tries = 0
                while tries < config.SERVING_URL_LOOKUP_TRIES:
                    try:
                        tries += 1
                        serving_url = images.get_serving_url(str(self.blob_key), size=size, crop=crop, secure_url=secure_url)
                        if serving_url is not None:
                            break
                    except Exception, e:
                        if tries >= config.SERVING_URL_LOOKUP_TRIES:
                            logging.error("Unable to get image serving URL: %s" % e)
                if serving_url is not None:
                    memcache.set(key, serving_url, time=config.SERVING_URL_TIMEOUT, namespace=namespace)
        return serving_url

    @classmethod
    def get_entity(cls, key):
        return db.get(key)

    @classmethod
    def create_new_entity(cls, **kwargs):
        """
        Called to create a new entity. The default implementation simply creates the entity with the default constructor
        and calls ``put()``. This method allows the class to be mixed-in with :py:class:`agar.models.NamedModel`.

        :param kwargs: Parameters to be passed to the constructor.
        """
        image = cls(**kwargs)
        image.put()
        return image

    @classmethod
    def create(cls, blob_key=None, blob_info=None, data=None, filename=None, url=None, mime_type=None, **kwargs):
        """
        Create an ``Image``. Use this class method rather than creating an image with the constructor. You must provide one
        of the following parameters ``blob_info``, ``data``, or ``url`` to specify the image data to use.

        :param blob_key: The `Blobstore`_ data to use as the image data. If this parameter is not ``None``, all
            other parameters will be ignored as they are not needed (Only use with `NdbImage`).
        :param blob_info: The `Blobstore`_ data to use as the image data. If this parameter is not ``None``, all
            other parameters will be ignored as they are not needed (Do not use with `NdbImage`).
        :param data: The image data that should be put in the `Blobstore`_ and used as the image data.
        :param filename: The filename of the image data. If not provided, the filename will be guessed from the URL
            or, if there is no URL, it will be set to the stringified `Key`_ of the image entity.
        :param url: The URL to fetch the image data from and then place in the `Blobstore`_ to be used as the image data.
        :param mime_type: The `mime type`_ to use for the `Blobstore`_ image data.
            If ``None``, it will attempt to guess the mime type from the url fetch response headers or the filename.
        :param parent:  Inherited from `Model`_. The `Model`_ instance or `Key`_ instance for the entity that is the new
            image's parent.
        :param key_name: Inherited from `Model`_. The name for the new entity. The name becomes part of the primary key.
        :param key: Inherited from `Model`_. The explicit `Key`_ instance for the new entity.
            Cannot be used with ``key_name`` or ``parent``. If ``None``, falls back on the behavior for ``key_name`` and
            ``parent``.
        :param kwargs: Initial values for the instance's properties, as keyword arguments.  Useful if subclassing.
        :return: An instance of the ``Image`` class.
        """
        if filename is not None:
            filename = filename.encode('ascii', 'ignore')
        if url is not None:
            url = url.encode('ascii', 'ignore')
        if blob_info is not None:
            if issubclass(cls, Image):
                kwargs['blob_info'] = blob_info
            else:
                kwargs['blob_key'] = blob_info.key()
            return cls.create_new_entity(**kwargs)
        if blob_key is not None:
            if issubclass(cls, NdbImage):
                kwargs['blob_key'] = blob_key
            else:
                kwargs['blob_info'] = blob_key
            return cls.create_new_entity(**kwargs)
        if data is None:
            if url is not None:
                response = urlfetch.fetch(url)
                data = response.content
                mime_type = mime_type or response.headers.get('Content-Type', None)
                if filename is None:
                    path = urlparse.urlsplit(url)[2]
                    filename = path[path.rfind('/')+1:]
        if data is None:
            raise db.Error("No image data")
        image = cls.create_new_entity(source_url=url, **kwargs)
        filename = filename or image.model_key_string
        mime_type = mime_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        if mime_type not in ImageConfig.get_config(_cache=True).VALID_MIME_TYPES:
            message = "The image mime type (%s) isn't valid" % mime_type
            logging.warning(message)
            image.delete()
            raise images.BadImageError(message)
        gae_image = images.Image(data)
        format = gae_image.format
        new_format = None
        if mime_type == 'image/jpeg' and format != images.JPEG:
            new_format = images.JPEG
        if mime_type == 'image/png' and format != images.PNG:
            new_format = images.PNG
        if new_format is not None:
            data = images.crop(data, 0.0, 0.0, 1.0, 1.0, output_encoding=new_format, quality=100)
        try:
            blob_file_name = files.blobstore.create(mime_type=mime_type, _blobinfo_uploaded_filename=filename)
            with files.open(blob_file_name, 'a') as f:
                f.write(data)
            files.finalize(blob_file_name)
            image.blob_key = files.blobstore.get_blob_key(blob_file_name)
        except AssertionError:
            # Needed to create an Image from url or image_data in a unittest.
            # Hopefully we can remove this when this bug is fixed:
            # http://code.google.com/p/googleappengine/issues/detail?id=5301
            global TESTBED_INSTANCE
            _ = TESTBED_INSTANCE.get_stub('blobstore').CreateBlob(filename, data)
            image.blob_key = blobstore.BlobKey(filename)
        image.put()
        return image


class Image(db.Model, BaseImage):
    """
    A model class that helps create and work with images stored in the `Blobstore`_.
    Please note that you should never call the constructor for this class directly when creating an image.
    Instead, use the :py:meth:`create` method.
    """
    #: The `BlobInfo`_ entity for the image's `Blobstore`_ value.
    blob_info = blobstore.BlobReferenceProperty()
    #: The original URL that the image data was fetched from, if applicable.
    source_url = db.StringProperty(required=False, default=None)
    #: The create timestamp.
    created = db.DateTimeProperty(auto_now_add=True)
    #: The last modified timestamp.
    modified = db.DateTimeProperty(auto_now=True)

    @property
    def model_key(self):
        return self.key()

    @property
    def model_key_string(self):
        return str(self.model_key)

    def get_blob_key(self):
        if self.blob_info is not None:
            return self.blob_info.key()
        return None
    def set_blob_key(self, blob_key):
        self.blob_info = blob_key
    #: The `BlobKey`_ entity for the image's `Blobstore`_ value.
    blob_key = property(get_blob_key, set_blob_key)

    def fetch_data(self, *args, **kwargs):
        return blobstore.fetch_data(self.blob_key, *args, **kwargs)

    def delete(self, **kwargs):
        """
        Delete the image and its attached `Blobstore`_ storage.

        :param kwargs: Parameters to be passed to parent classes ``delete()`` method.
        """
        if self.blob_info is not None:
            self.blob_info.delete()
        super(Image, self).delete(**kwargs)


class NdbImage(ndb.model.Model, BaseImage):
    """
    An NDB model class that helps create and work with images stored in the `Blobstore`_.
    Please note that you should never call the constructor for this class directly when creating an image.
    Instead, use the :py:meth:`create` method.
    """
    #: The `BlobKey`_ entity for the image's `Blobstore`_ value.
    blob_key = ndb.model.BlobKeyProperty(required=False)
    #: The original URL that the image data was fetched from, if applicable.
    source_url = ndb.model.StringProperty(required=False, default=None)
    #: The create timestamp.
    created = ndb.model.DateTimeProperty(auto_now_add=True)
    #: The last modified timestamp.
    modified = ndb.model.DateTimeProperty(auto_now=True)

    @property
    def model_key(self):
        return self.key

    @property
    def model_key_string(self):
        return self.model_key.urlsafe()

    def get_blob_info(self):
        if self.blob_key is not None:
            return blobstore.BlobInfo.get(self.blob_key)
        return None
    def set_blob_info(self, blob_info):
        self.blob_key = blob_info.key()
    #: The `BlobInfo`_ entity for the image's `Blobstore`_ value.
    blob_info = property(get_blob_info, set_blob_info)

    def fetch_data(self, *args, **kwargs):
        return blobstore.fetch_data(self.blob_info, *args, **kwargs)

    #noinspection PyUnusedLocal
    def delete(self, **kwargs):
        """
        Delete the image and its attached `Blobstore`_ storage.

        :param kwargs: Ignored.
        """
        self.key.delete()

    @classmethod
    def _pre_delete_hook(cls, key):
        image = key.get()
        if image.blob_info is not None:
            image.blob_info.delete()

    @classmethod
    def get_entity(cls, key):
        return key.get()

    @classmethod
    def create_new_entity(cls, **kwargs):
        """
        Called to create a new entity. The default implementation simply creates the entity with the default constructor
        and calls ``put()``. This method allows the class to be mixed-in with :py:class:`agar.models.NamedModel`.

        :param kwargs: Parameters to be passed to the constructor.
        """
        image = cls(**kwargs)
        image.put()
        return image
