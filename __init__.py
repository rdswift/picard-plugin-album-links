"""Generate Album Links"""
#
# Copyright (C) 2026 Bob Swift
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

# This plugin is based on the Picard 2 plugin "Generate M3U playlist" by
# Francis Chin, Sambhav Kothari and Chris Hylen.  See original code at
# https://github.com/metabrainz/picard-plugins/blob/5a63f009/plugins/playlist/playlist.py

from PyQt6 import (
    QtCore,
    QtWidgets,
)

from picard.plugin3.api import (
    Album,
    BaseAction,
    OptionsPage,
    PluginApi,
    t_,
)

from .ui_options_album_links import Ui_AlbumLinksOptionsPage


USER_GUIDE_URL = 'https://picard-plugins-user-guides.readthedocs.io/en/latest/album_links/user_guide.html'


class Links:
    """Class to hold link information"""
    titles: dict[str, str] = {}
    enabled: list[str] = []


def get_selected_albums(api: PluginApi) -> list[Album]:
    """Get a list of the selected albums.

    Args:
        api (PluginApi): The plugin's api.

    Returns:
        list[Album]: List of the selected albums.
    """
    return [obj for obj in api.tagger.window.selected_objects if isinstance(obj, Album)]


def get_url_rels(album: Album) -> dict[str, set[str]]:
    """Get the list of URL rels for an album.

    Args:
        album (Album): Album object.

    Returns:
        dict[str, set[str]]: Dictionary mapping URL names to URLs.
    """
    url_rels = {}

    metadata = album._release_node_cache
    rels = metadata.get('relations', []) + metadata.get('release-group', {}).get('relations', [])
    for rel in rels:
        if rel.get('target-type', '') != 'url':
            continue

        if rel.get('ended', True):
            continue

        name = rel.get('type', '')
        if not name:
            continue

        if name in {'discography', 'discography entry'}:
            name = 'discography'

        if name not in Links.enabled:
            continue

        if name in Links.titles:
            name = Links.titles[name]
        else:
            continue

        url = rel.get('url', {}).get('resource', '')
        if not url:
            continue

        if name not in url_rels:
            url_rels[name] = set()

        url_rels[name].add(url)

    return url_rels


class AlbumLinks(BaseAction):
    TITLE = t_('ui.action.album_links.title', "Album links")

    def callback(self, objs) -> None:
        albums = get_selected_albums(self.api)
        if not albums:
            QtWidgets.QMessageBox.warning(
                self.api.tagger.window,
                self.api.tr('ui.dialog.no_albums.title', "No Albums"),
                self.api.tr(
                    'ui.dialog.no_albums.text',
                    "There are no albums selected, so no links to display.",
                ),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            return

        if len(albums) > 1:
            QtWidgets.QMessageBox.warning(
                self.api.tagger.window,
                self.api.tr('ui.dialog.multiple_albums.title', "Multiple Albums"),
                self.api.tr(
                    'ui.dialog.multiple_albums.text',
                    "There are multiple albums selected. Please select a single album to display its links.",
                ),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            return

        album = albums[0]
        url_rels = get_url_rels(album)

        if not url_rels:
            QtWidgets.QMessageBox.warning(
                self.api.tagger.window,
                self.api.tr('ui.dialog.no_links.title', "No Links"),
                self.api.tr(
                    'ui.dialog.no_links.text',
                    "There are no links to display for the selected album.",
                ),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            return

        text = f"Links for album: {album.metadata.get('album', 'Unknown Album')}\n\n"
        for name in sorted(url_rels.keys()):
            text += f"<p>{name}:</p>\n<ul>\n"
            for url in sorted(list(url_rels[name])):
                text += f"  <li><a href='{url}'>{url}</a></li>\n"
            text += "</ul>\n\n"

        msgbox = QtWidgets.QMessageBox()
        msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)
        msgbox.setWindowTitle(self.api.tr('ui.dialog.links.title', "Links"))
        msgbox.setText(text)
        msgbox.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msgbox.exec()


class AlbumLinksOptionsPage(OptionsPage):

    TITLE = t_("ui.options_page_title", "Album Links")
    OPTIONS = {
        'link_types': {'widgets': ['gb_select_links']},
    }
    HELP_URL = USER_GUIDE_URL

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ui = Ui_AlbumLinksOptionsPage()
        self.ui.setupUi(self)

    @staticmethod
    def _name(name: str) -> str:
        return f"option_{name.replace(' ', '_')}"

    def load(self):
        for link_type in sorted(Links.titles.keys()):
            option = QtWidgets.QCheckBox(Links.titles[link_type])
            option.setChecked(link_type in Links.enabled)
            option.setObjectName(self._name(link_type))
            self.ui.gb_select_links.layout().addWidget(option)

    def save(self):
        enabled = []
        for link_type in sorted(Links.titles.keys()):
            option: QtWidgets.QCheckBox = self.ui.gb_select_links.findChild(QtWidgets.QCheckBox, self._name(link_type))
            if option.isChecked():
                enabled.append(link_type)

        Links.enabled = enabled
        self.api.plugin_config['link_types'] = enabled


def enable(api: PluginApi):
    """Called when the plugin is enabled.

    Args:
        api (PluginApi): The api for the plugin.
    """

    # Set up link type names
    Links.titles['allmusic'] = "AllMusic"
    Links.titles['amazon asin'] = "Amazon"
    Links.titles['discography'] = api.tr('ui.link_title.discography', "Discography")
    Links.titles['discogs'] = "Discogs"
    Links.titles['lyrics'] = api.tr('ui.link_title.lyrics', "Lyrics")
    Links.titles['other databases'] = api.tr('ui.link_title.other', "Other Databases")
    Links.titles['wikidata'] = "Wikidata"
    Links.titles['wikipedia'] = "Wikipedia"
    Links.titles['secondhandsongs'] = "SecondHandSongs"
    Links.titles['vgmdb'] = "VGMdb"
    Links.titles['official homepage'] = api.tr('ui.link_title.homepage', "Official Homepage")

    # Initialize settings
    api.plugin_config.register_option(
        'link_types',
        ['allmusic', 'discogs', 'secondhandsongs', 'vgmdb'],
        title=api.tr("ui.option.title.link_types", "Links to display"),
        in_profile=True,
    )

    # Set the selected types
    Links.enabled = api.plugin_config['link_types'] or []

    # Register the action
    api.register_tools_menu_action(AlbumLinks)

    # Register the options page
    api.register_options_page(AlbumLinksOptionsPage)
