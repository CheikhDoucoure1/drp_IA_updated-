from django.apps import AppConfig


class DrpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'drp'

    def ready(self):
        self._patch_context_copy_for_python314()

    @staticmethod
    def _patch_context_copy_for_python314():
        """
        Django 4.2 uses copy(super()) in BaseContext.__copy__ which breaks on
        Python 3.14 because super() objects no longer have __dict__.
        Replace with a correct shallow-copy implementation.
        """
        from django.template.context import BaseContext

        def _fixed_copy(self):
            duplicate = self.__class__.__new__(self.__class__)
            duplicate.__dict__ = self.__dict__.copy()
            duplicate.dicts = self.dicts[:]
            return duplicate

        BaseContext.__copy__ = _fixed_copy
