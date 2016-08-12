# -*- coding: utf-8 -*-
from Acquisition import aq_base
from collective.themesitesetup.interfaces import DEFAULT_DISABLED_PROFILE_NAME
from collective.themesitesetup.interfaces import DEFAULT_ENABLED_LOCALES_NAME
from collective.themesitesetup.interfaces import DEFAULT_ENABLED_MODELS_NAME
from collective.themesitesetup.interfaces import DEFAULT_ENABLED_PROFILE_NAME
from collective.themesitesetup.utils import createTarball
from collective.themesitesetup.utils import getMessageCatalogs
from collective.themesitesetup.utils import getSettings
from collective.themesitesetup.utils import isEnabled
from collective.themesitesetup.utils import overrideModels
from plone.app.theming.interfaces import IThemePlugin
from plone.app.theming.interfaces import THEME_RESOURCE_NAME
from plone.dexterity.fti import DexterityFTIModificationDescription
from plone import api
from plone.resource.utils import queryResourceDirectory
from plone.supermodel import loadString
from plone.supermodel.parser import SupermodelParseError
from zope.app.i18n.translationdomain import TranslationDomain
from zope.component import getSiteManager
from zope.event import notify
from zope.i18n import ITranslationDomain
from zope.interface import implements
from zope.lifecycleevent import ObjectModifiedEvent
import logging

logger = logging.getLogger('collective.themesitesetup')


# noinspection PyPep8Naming
class GenericSetupPlugin(object):
    """This plugin can be used to import generic setup profiles
    when theme is enabled or disabled.

    Relative directory paths for importable generic setup profiles can
    be defined in the theme manifest::

        [theme:genericsetup]
        install = profile
        uninstall =

    """

    implements(IThemePlugin)

    dependencies = ()

    def onDiscovery(self, theme, settings, dependenciesSettings):
        pass

    def onCreated(self, theme, settings, dependenciesSettings):
        pass

    def onEnabled(self, theme, settings, dependenciesSettings):
        res = queryResourceDirectory(THEME_RESOURCE_NAME, theme)
        if res is None:
            return

        # We need to get settings by ourselves to avoid p.a.theming caching
        settings = getSettings(res)
        if not isEnabled(settings):
            return

        directoryName = DEFAULT_ENABLED_PROFILE_NAME
        if 'install' in settings:
            directoryName = settings['install']

        directory = None
        if res.isDirectory(directoryName):
            directory = res[directoryName]

        if directory:
            tarball = createTarball(directory)
            portal_setup = api.portal.get_tool('portal_setup')
            portal_setup.runAllImportStepsFromProfile(
                None, purge_old=False, archive=tarball)

        localesDirectoryName = DEFAULT_ENABLED_LOCALES_NAME
        if 'locales' in settings:
            localesDirectoryName = settings['locales']

        if res.isDirectory(localesDirectoryName):
            catalogs = getMessageCatalogs(res[localesDirectoryName])
            sm = getSiteManager()
            for domain in catalogs:
                util = sm.queryUtility(ITranslationDomain, name=domain)
                if not isinstance(util, TranslationDomain):
                    name = str('collective.themesitesetup.domain.' + domain)
                    util = TranslationDomain()
                    util.__name__ = name
                    util.__parent__ = aq_base(sm)
                    util.domain = domain
                    sm._setObject(
                        name, util, set_owner=False, suppress_events=True)
                    sm.registerUtility(
                        util, provided=ITranslationDomain, name=domain)
                for language in catalogs[domain]:
                    name = '.'.join(['collective.themesitesetup.catalog',
                                     res.__name__, domain, language])
                    if name in util:
                        try:
                            del util[name]
                        except ValueError:
                            pass
                    util[name] = catalogs[domain][language]

        modelsDirectoryName = DEFAULT_ENABLED_MODELS_NAME
        if 'models' in settings:
            modelsDirectoryName = settings['models']
        override = overrideModels(settings)

        if res.isDirectory(modelsDirectoryName):
            types_tool = api.portal.get_tool('portal_types')
            directory = res[modelsDirectoryName]
            for name in directory.listDirectory():
                if not name.endswith('.xml') or not directory.isFile(name):
                    continue
                fti = types_tool.get(name[:-4])
                if not fti:
                    continue
                model = unicode(directory.readFile(name), 'utf-8', 'ignore')
                if fti.model_source == model:
                    continue
                try:
                    loadString(model, fti.schema_policy)  # fail for errors
                except SupermodelParseError:
                    logger.error(
                        u'Error while parsing {0:s}/{1:s}/{2:s}'.format(
                            res.__name__, modelsDirectoryName, name))
                    raise
                # Set model source when model is empty of override is enabled
                desc = DexterityFTIModificationDescription('model_source',
                                                           fti.model_source)
                if not fti.model_source:
                    fti.model_source = model
                    notify(ObjectModifiedEvent(fti, desc))
                elif not loadString(fti.model_source, fti.schema_policy).schema.names():  # noqa
                    fti.model_source = model
                    notify(ObjectModifiedEvent(fti, desc))
                elif override:
                    fti.model_source = model
                    notify(ObjectModifiedEvent(fti, desc))

    def onDisabled(self, theme, settings, dependenciesSettings):
        res = queryResourceDirectory(THEME_RESOURCE_NAME, theme)
        if res is None:
            return

        # We need to get settings by ourselves to avoid p.a.theming caching
        settings = getSettings(res)
        if not isEnabled(settings):
            return

        directoryName = DEFAULT_DISABLED_PROFILE_NAME
        if 'uninstall' in settings:
            directoryName = settings['uninstall']

        directory = None
        if res.isDirectory(directoryName):
            directory = res[directoryName]

        if directory:
            tarball = createTarball(directory)
            portal_setup = api.portal.get_tool('portal_setup')
            portal_setup.runAllImportStepsFromProfile(
                None, purge_old=False, archive=tarball)

        localesDirectoryName = DEFAULT_ENABLED_LOCALES_NAME
        if 'locales' in settings:
            localesDirectoryName = settings['locales']

        if res.isDirectory(localesDirectoryName):
            catalogs = getMessageCatalogs(res[localesDirectoryName])
            sm = getSiteManager()
            for domain in catalogs:
                util = sm.queryUtility(ITranslationDomain, name=domain)
                if isinstance(util, TranslationDomain):
                    for language in catalogs[domain]:
                        name = '.'.join(['collective.themesitesetup.catalog',
                                         res.__name__, domain, language])
                        if name in util:
                            try:
                                del util[name]
                            except ValueError:
                                pass
                    name = str('collective.themesitesetup.domain.' + domain)
                    if name in sm.objectIds():
                        sm._delObject(name, suppress_events=True)
                        sm.unregisterUtility(
                            util, provided=ITranslationDomain, name=domain)

    def onRequest(self, request, theme, settings, dependenciesSettings):
        pass
