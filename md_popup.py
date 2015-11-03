"""
Markdown popup.

A markdown tooltip for SublimeText.
"""
import sublime
import markdown
from . import file_strip
import traceback
from plistlib import readPlistFromBytes
from .rgba import RGBA
import os
import re

_css_cache = {}
_lum_cache = {}

LUM_MIDPOINT = 127


def sublime_format_path(pth):
    """Format the path for sublime."""

    m = re.match(r"^([A-Za-z]{1}):(?:/|\\)(.*)", pth)
    if sublime.platform() == "windows" and m is not None:
        pth = m.group(1) + "/" + m.group(2)
    return pth.replace("\\", "/")


def scheme_lums(scheme_file):
    """Get the scheme lumincance."""
    color_scheme = os.path.normpath(scheme_file)
    scheme_file = os.path.basename(color_scheme)
    plist_file = readPlistFromBytes(
        re.sub(
            br"^[\r\n\s]*<!--[\s\S]*?-->[\s\r\n]*|<!--[\s\S]*?-->", b'',
            sublime.load_binary_resource(sublime_format_path(color_scheme))
        )
    )

    color_settings = plist_file["settings"][0]["settings"]
    rgba = RGBA(color_settings.get("background", '#FFFFFF'))
    return rgba.luminance()


def get_scheme_lum(view):
    """Get scheme lum."""

    lum = 255
    scheme = view.settings().get('color_scheme')
    if scheme is not None:
        if scheme in _lum_cache:
            lum = _lum_cache[scheme]
        else:
            try:
                lum = scheme_lums(scheme)
            except Exception:
                pass
    return lum


def get_theme_by_scheme_map(view):
    """Get mapped scheme if available."""

    css = None
    theme_map = sublime.load_settings('Preferences.sublime-settings').get('md_popup_theme_map', {})

    if theme_map:
        scheme = view.settings().get('color_scheme')
        if scheme is not None and scheme in theme_map:
            css = get_css(theme_map[scheme])
    return css


def get_theme_by_lums(lums):
    """Get theme based on lums."""

    if lums <= LUM_MIDPOINT:
        css_content = get_css('Packages/SublimeRandomCrap/themes/dark.css')
    else:
        css_content = get_css('Packages/SublimeRandomCrap/themes/light.css')
    return css_content


class _MdWrapper(markdown.Markdown):
    """
    Wrapper around Python Markdown's class.

    This allows us to gracefully continue when a module doesn't load.
    """

    Meta = {}

    def __init__(self, *args, **kwargs):
        """Call original init."""

        super(_MdWrapper, self).__init__(*args, **kwargs)

    def registerExtensions(self, extensions, configs):  # noqa
        """
        Register extensions with this instance of Markdown.

        Keyword arguments:

        * extensions: A list of extensions, which can either
           be strings or objects.  See the docstring on Markdown.
        * configs: A dictionary mapping module names to config options.

        """

        from markdown import util
        from markdown.extensions import Extension

        for ext in extensions:
            try:
                if isinstance(ext, util.string_type):
                    ext = self.build_extension(ext, configs.get(ext, {}))
                if isinstance(ext, Extension):
                    ext.extendMarkdown(self, globals())
                    # print(
                    #     'Successfully loaded extension "%s.%s".'
                    #     % (ext.__class__.__module__, ext.__class__.__name__)
                    # )
                elif ext is not None:
                    raise TypeError(
                        'Extension "%s.%s" must be of type: "markdown.Extension"'
                        % (ext.__class__.__module__, ext.__class__.__name__)
                    )
            except Exception:
                # We want to gracefully continue even if an extension fails.
                print(str(traceback.format_exc()))
                continue

        return self


def clear_cache():
    """Clear the css cache."""

    global _css_cache
    global _lum_cache
    _css_cache = {}
    _lum_cache = {}


def get_css(css_file):
    """
    Get css file.

    Strip out comments and carriage returns.
    """
    css = None
    if css_file in _css_cache:
        css = _css_cache[css_file]

    try:
        css = file_strip.comments.Comments('css').strip(
            sublime.load_resource(css_file).replace('\r', '')
        )
        _css_cache[css_file] = css
    except Exception as e:
        print(e)
        pass
    return css


def show_popup(
    view, content, md=True, location=-1,
    max_width=320, max_height=240,
    on_navigate=None, on_hide=None,
    css=None, append_css=None
):
    """Parse the color scheme if needed and show the styled pop-up."""

    extensions = [
        "markdown.extensions.attr_list",
        "markdown.extensions.codehilite",
        "SublimeRandomCrap.mdx.superfences",
        "SublimeRandomCrap.mdx.betterem",
        "SublimeRandomCrap.mdx.magiclink",
        "SublimeRandomCrap.mdx.inlinehilite",
        "markdown.extensions.nl2br",
        "markdown.extensions.admonition"
    ]

    configs = {
        "SublimeRandomCrap.mdx.inlinehilite": {
            "style_plain_text": True,
            "css_class": "inlinehilite",
            "use_codehilite_settings": False,
            "guess_lang": False
        },
        "markdown.extensions.codehilite": {
            "guess_lang": False
        }
    }

    if css is None:
        css_content = get_theme_by_scheme_map(view)

        if css_content is None:
            lums = get_scheme_lum(view)
            css_content = get_theme_by_lums(lums)
        else:
            css_content = get_css(css)
            if css_content is None:
                lums = get_scheme_lum(view)
                css_content = get_theme_by_lums(lums)

    if append_css is not None and isinstance(append_css, str):
        css_content += append_css

    if md:
        content = _MdWrapper(
            extensions=extensions,
            extension_configs=configs,
        ).convert(content).replace('&quot;', '"').replace('\n', '')

    print(content)
    html = "<style>%s</style>" % css_content if css_content else ''
    html += '<div class="content">%s</div>' % content

    view.show_popup(
        html, location=location, max_width=max_width,
        max_height=max_height, on_navigate=on_navigate, on_hide=on_hide
    )