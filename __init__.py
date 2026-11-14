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

from PyQt6 import QtWidgets

from picard.plugin3.api import (
    Album,
    BaseAction,
    OptionsPage,
    PluginApi,
    t_,
)

from .ui_album_links import Ui_AlbumLinksPage
from .ui_options_album_links import Ui_AlbumLinksOptionsPage


USER_GUIDE_URL = 'https://picard-plugins-user-guides.readthedocs.io/en/latest/album_links/user_guide.html'


class Links:
    """Class to hold link information"""
    titles: dict[str, str] = {}
    enabled: list[str] = []
    mapping: dict[str, str] = {
        'discography entry': 'discography',
        'IMDB samples': 'production',
        'purchase for mail-order': 'get the music',
        'purchase for download': 'get the music',
        'download for free': 'get the music',
        'free streaming': 'get the music',
        'streaming': 'get the music',
    }


def get_selected_albums(api: PluginApi) -> list[Album]:
    """Get a list of the selected albums.

    Args:
        api (PluginApi): The plugin's api.

    Returns:
        list[Album]: List of the selected albums.
    """
    return [obj for obj in api.tagger.window.selected_objects if isinstance(obj, Album)]


def parse_rel(rel: dict) -> tuple[str, str] | None:
    """Parse a relation.

    Args:
        rel (dict): Relation node.

    Returns:
        tuple[str, str] | None: Tuple of link type and url.  Returns None if no match.
    """
    if rel.get('target-type', '') != 'url':
        return

    if rel.get('ended', True):
        return

    name = rel.get('type', '')
    if not name:
        return

    if name in Links.mapping:
        name = Links.mapping[name]

    if name not in Links.enabled:
        return

    if name in Links.titles:
        name = Links.titles[name]
    else:
        return

    url = rel.get('url', {}).get('resource', '')
    if not url:
        return

    return name, url


def get_url_rels(album: Album) -> dict[str, dict[str, str]]:
    """Get the list of URL rels for an album.

    Args:
        album (Album): Album object.

    Returns:
        dict[str, dict[str, str]]: Dictionary mapping URL names to URLs.
    """
    url_rels: dict[str, dict[str, str]] = {}

    def add_rel(rel_tuple: tuple[str, str], extra: str = ""):
        name, url = rel_tuple
        if name not in url_rels:
            url_rels[name] = {}
        url_rels[name][url] = extra

    metadata = album._release_node_cache

    # Process release relations
    for rel in metadata.get('relations', []):
        result = parse_rel(rel)
        if result:
            add_rel(result, extra='r')

    # Process release group relations
    for rel in metadata.get('release-group', {}).get('relations', []):
        result = parse_rel(rel)
        if result:
            add_rel(result, extra='rg')

    # Process track relations
    for medium in metadata.get('media', []):
        medium: dict
        m_num = str(medium.get('position', 0))
        for track in medium.get('tracks', []):
            track: dict
            t_num = track.get('number', '') or str(track.get('position', 0))
            for rel in track.get('recording', {}).get('relations', []):
                rel: dict
                result = parse_rel(rel)
                if result:
                    add_rel(result, extra=f"{m_num}:{t_num}")

                # Add the relations for works associated with the track
                for w_rel in rel.get('work', {}).get('relations', []):
                    w_rel: dict
                    result = parse_rel(w_rel)
                    if result:
                        add_rel(result, extra=f"{m_num}:{t_num}:w")

    return url_rels


class AlbumLinksPage(QtWidgets.QDialog):
    """Dialog for displaying the links"""
    def __init__(self):
        super().__init__()
        self.ui = Ui_AlbumLinksPage()
        self.ui.setupUi(self)


class AlbumLinks(BaseAction):
    """Action to display the links for the selected album"""

    TITLE = t_('ui.action.album_links.title', "Album links")

    def callback(self, objs) -> None:
        """Extract and display the links in a dialog"""

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
        show_extra = self.api.plugin_config['show_source']
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

        page = AlbumLinksPage()
        page.setWindowTitle(self.api.tr("ui.options_page_title", "Album Links"))

        def _store_size(*args, **kwargs):
            dialog_size = page.size()
            self.api.plugin_persist['dialog_height'] = dialog_size.height()
            self.api.plugin_persist['dialog_width'] = dialog_size.width()
            page.accept()

        page.ui.buttonBox.accepted.connect(_store_size)
        page.ui.buttonBox.rejected.connect(_store_size)

        dialog_size = page.size()
        height = max(self.api.plugin_persist['dialog_height'], dialog_size.height())
        width = max(self.api.plugin_persist['dialog_width'], dialog_size.width())
        page.resize(width, height)

        text = self.api.tr('ui.dialog.album', "Links for album: {album}").format(album=album.metadata.get('album', 'Unknown Album'),)
        page.ui.page_text.setText(text)

        def _make_extra_entry(extra: str) -> str:
            if not show_extra:
                return ""
            extra = extra.strip()
            if not extra:
                return ""
            if extra == 'r':
                e_text = self.api.tr("ui.dialog.release", "Release")
            elif extra == 'rg':
                e_text = self.api.tr("ui.dialog.release_group", "Release Group")
            elif ':' not in extra:
                e_text = extra
            else:
                parts = extra.split(':')
                if len(parts) > 2:
                    e_text = self.api.tr("ui.dialog.work", "Track {disc_number}:{track_number} Work").format(
                        disc_number=parts[0],
                        track_number=parts[1],
                    )
                else:
                    e_text = self.api.tr("ui.dialog.track", "Track {disc_number}:{track_number}").format(
                        disc_number=parts[0],
                        track_number=parts[1],
                    )
            return f" ({e_text})"

        text = ""
        for name in sorted(url_rels.keys(), key=lambda x: x.lower()):
            text += "<p>" + self.api.tr('ui.dialog.link', "{link_type}:").format(link_type=name,) + "</p>\n<ul>\n"
            for url in sorted(list(url_rels[name])):
                text += f"  <li><a href='{url}'>{url}</a>{_make_extra_entry(url_rels[name][url])}</li>\n"
            text += "</ul>\n\n"

        page.ui.links_list_text.setText(text.strip())

        page.exec()


class AlbumLinksOptionsPage(OptionsPage):
    """Album Links Options Page"""

    TITLE = t_("ui.options_page_title", "Album Links")
    OPTIONS = {
        'link_types': {'widgets': ['gb_select_links']},
        'show_source': {'widgets': ['cb_show_link_source']},
    }
    HELP_URL = USER_GUIDE_URL

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ui = Ui_AlbumLinksOptionsPage()
        self.ui.setupUi(self)

    @staticmethod
    def _name(name: str) -> str:
        """Remove spaces and create an appropriate widget name.

        Args:
            name (str): Link type name.

        Returns:
            str: Widget name for the link type.
        """
        return f"option_{name.replace(' ', '_')}"

    def load(self):
        self.ui.cb_show_link_source.setChecked(self.api.plugin_config['show_source'])

        layout = self.ui.gb_select_links.layout()
        for i in reversed(range(layout.count())):
            layout.itemAt(i).widget().setParent(None)

        enabled = self.api.plugin_config['link_types'] or []
        for link_type in sorted(Links.titles.keys(), key=lambda x: x.lower()):
            option = QtWidgets.QCheckBox(Links.titles[link_type])
            option.setChecked(link_type in enabled)
            option.setObjectName(self._name(link_type))
            layout.addWidget(option)

    def save(self):
        self.api.plugin_config['show_source'] = self.ui.cb_show_link_source.isChecked()

        enabled = []
        for link_type in sorted(Links.titles.keys(), key=lambda x: x.lower()):
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
    Links.titles['BookBrainz'] = "BookBrainz"
    Links.titles['cover art link'] = api.tr('ui.link_title.cover_art', "Cover Art")
    Links.titles['crowdfunding'] = api.tr('ui.link_title.crowdfunding', "Crowd Funding")
    Links.titles['discography'] = api.tr('ui.link_title.discography', "Discography")
    Links.titles['discogs'] = "Discogs"
    Links.titles['fanpage'] = api.tr('ui.link_title.fanpage', "Fan Page")
    Links.titles['get the music'] = api.tr('ui.link_title.get_music', "Get the Music")
    Links.titles['license'] = api.tr('ui.link_title.license', "License")
    Links.titles['lyrics'] = api.tr('ui.link_title.lyrics', "Lyrics")
    Links.titles['official homepage'] = api.tr('ui.link_title.homepage', "Official Homepage")
    Links.titles['other databases'] = api.tr('ui.link_title.other', "Other Databases")
    Links.titles['production'] = api.tr('ui.link_title.production', "Production")
    Links.titles['review'] = api.tr('ui.link_title.review', "Review")
    Links.titles['secondhandsongs'] = "SecondHandSongs"
    Links.titles['show notes'] = api.tr('ui.link_title.show_notes', "Show Notes")
    Links.titles['songfacts'] = api.tr('ui.link_title.songfacts', "Song Facts")
    Links.titles['vgmdb'] = "VGMdb"
    Links.titles['wikidata'] = "Wikidata"
    Links.titles['wikipedia'] = "Wikipedia"

    # Initialize settings
    api.plugin_config.register_option(
        'link_types',
        ['allmusic', 'discogs', 'secondhandsongs', 'vgmdb'],
        title=api.tr("ui.option.title.link_types", "Links to display"),
        in_profile=True,
    )
    api.plugin_config.register_option(
        'show_source',
        True,
        title=api.tr("ui.option.title.link_rels", "Show link source"),
        in_profile=True,
    )
    api.plugin_persist.register_option('dialog_height', -1)
    api.plugin_persist.register_option('dialog_width', -1)

    # Set the selected types
    Links.enabled = api.plugin_config['link_types'] or []

    # Register the action
    api.register_tools_menu_action(AlbumLinks)

    # Register the options page
    api.register_options_page(AlbumLinksOptionsPage)
