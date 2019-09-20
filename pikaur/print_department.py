""" This file is licensed under GPLv3, see https://www.gnu.org/licenses/ """

import sys
from datetime import datetime
from typing import TYPE_CHECKING, List, Tuple, Iterable, Union, Dict, Optional

import pyalpm

from .i18n import _, _n
from .pprint import (
    print_stderr, color_line, bold_line, format_paragraph, get_term_width,
    print_warning,
)
from .args import parse_args
from .core import PackageSource, InstallInfo
from .config import VERSION, PikaurConfig
from .version import get_common_version, get_version_diff
from .pacman import PackageDB

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from .aur import AURPackageInfo  # noqa
    from .install_info_fetcher import InstallInfoFetcher  # noqa


GROUP_COLOR = 4
REPLACEMENTS_COLOR = 14


AnyPackage = Union['AURPackageInfo', pyalpm.Package]


def print_version(pacman_version: str, quiet=False) -> None:
    if quiet:
        print(f'Pikaur v{VERSION}')
        print(pacman_version)
    else:
        sys.stdout.write(r"""
      /:}               _
     /--1             / :}
    /   |           / `-/
   |  ,  --------  /   /
   |'                 Y      Pikaur v""" + VERSION + r"""
  /                   l      (C) 2018 Pikaur development team
  l  /       \        l      Licensed under GPLv3
  j  ●   .   ●        l
 { )  ._,.__,   , -.  {      """ + pacman_version + r"""
  У    \  _/     ._/   \

""")


def print_not_found_packages(not_found_packages: List[str], repo=False) -> None:
    num_packages = len(not_found_packages)
    print_warning(
        bold_line(
            _n(
                "Following package cannot be found in repositories:",
                "Following packages cannot be found in repositories:",
                num_packages
            )
            if repo else
            _n(
                "Following package cannot be found in AUR:",
                "Following packages cannot be found in AUR:",
                num_packages
            )
        )
    )
    for package in not_found_packages:
        print_stderr(format_paragraph(package))


def pretty_format_upgradeable(  # pylint: disable=too-many-statements
        packages_updates: List['InstallInfo'],
        verbose=False, print_repo=False, color=True, template: str = None
) -> str:

    _color_line = color_line
    _bold_line = bold_line
    if not color:
        _color_line = lambda line, *args: line  # noqa
        _bold_line = lambda line: line  # noqa

    def pretty_format(pkg_update: 'InstallInfo') -> Tuple[str, str]:  # pylint:disable=too-many-locals
        common_version, diff_weight = get_common_version(
            pkg_update.current_version or '', pkg_update.new_version or ''
        )
        user_config = PikaurConfig()
        color_config = user_config.colors
        version_color = color_config.get_int('Version')
        old_color = color_config.get_int('VersionDiffOld')
        new_color = color_config.get_int('VersionDiffNew')
        column_width = min(int(get_term_width() / 2.5), 37)

        sort_by = '{:04d}{}'.format(
            9999 - diff_weight,
            pkg_update.name
        )
        user_chosen_sorting = user_config.sync.UpgradeSorting
        if user_chosen_sorting == 'pkgname':
            sort_by = pkg_update.name
        elif user_chosen_sorting == 'repo':
            sort_by = '{}{}'.format(
                pkg_update.repository,
                pkg_update.name
            )

        pkg_name = pkg_update.name
        pkg_len = len(pkg_update.name)

        days_old = ''
        if pkg_update.devel_pkg_age_days:
            days_old = ' ' + _('({} days old)').format(pkg_update.devel_pkg_age_days)

        pkg_name = _bold_line(pkg_name)
        if (print_repo or verbose) and pkg_update.repository:
            pkg_name = '{}{}'.format(
                _color_line(pkg_update.repository + '/', 13),
                pkg_name
            )
            pkg_len += len(pkg_update.repository) + 1
        elif print_repo:
            pkg_name = '{}{}'.format(
                _color_line('aur/', 9),
                pkg_name
            )
            pkg_len += len('aur/')

        if pkg_update.required_by:
            required_by = ' ({})'.format(
                _('for {pkg}').format(
                    pkg=', '.join([p.package.name for p in pkg_update.required_by])
                )
            )
            pkg_len += len(required_by)
            dep_color = 3
            required_by = _color_line(' ({})', dep_color).format(
                _('for {pkg}').format(
                    pkg=_color_line(', ', dep_color).join([
                        _color_line(p.package.name, dep_color + 8) for p in pkg_update.required_by
                    ]) + _color_line('', dep_color, reset=False),
                )
            )
            pkg_name += required_by
        if pkg_update.provided_by:
            provided_by = ' ({})'.format(
                ' # '.join([p.name for p in pkg_update.provided_by])
            )
            pkg_len += len(provided_by)
            pkg_name += _color_line(provided_by, 2)
        if pkg_update.members_of:
            members_of = ' ({})'.format(
                _n('{grp} group', '{grp} groups', len(pkg_update.members_of)).format(
                    grp=', '.join([g for g in pkg_update.members_of]),
                )
            )
            pkg_len += len(members_of)
            members_of = _color_line(' ({})', GROUP_COLOR).format(
                _n('{grp} group', '{grp} groups', len(pkg_update.members_of)).format(
                    grp=_color_line(', ', GROUP_COLOR).join(
                        [_color_line(g, GROUP_COLOR + 8) for g in pkg_update.members_of]
                    ) + _color_line('', GROUP_COLOR, reset=False),
                )
            )
            pkg_name += _color_line(members_of, GROUP_COLOR)
        if pkg_update.replaces:
            replaces = ' (replaces {})'.format(
                ', '.join([g for g in pkg_update.replaces])
            )
            pkg_len += len(replaces)
            pkg_name += _color_line(replaces, REPLACEMENTS_COLOR)
            if not color:
                pkg_name = f'# {pkg_name}'

        return (
            template or (
                ' {pkg_name}{spacing}'
                ' {current_version}{spacing2}{version_separator}{new_version}{days_old}{verbose}'
            )
        ).format(
            pkg_name=pkg_name,
            days_old=days_old,
            current_version=(
                _color_line(common_version, version_color) +
                _color_line(
                    get_version_diff(pkg_update.current_version or '', common_version),
                    old_color
                )
            ),
            new_version=(
                _color_line(common_version, version_color) +
                _color_line(
                    get_version_diff(pkg_update.new_version or '', common_version),
                    new_color
                )
            ),
            version_separator=(
                ' -> ' if (pkg_update.current_version or pkg_update.new_version) else ''
            ),
            spacing=' ' * max(1, (column_width - pkg_len)),
            spacing2=' ' * max(1, (
                column_width - 18 -
                len(pkg_update.current_version or '') -
                max(-1, (pkg_len - column_width))
            )),
            verbose=(
                '' if not (verbose and pkg_update.description)
                else f'\n{format_paragraph(pkg_update.description)}'
            )
        ), sort_by

    return '\n'.join([
        line for line, _ in sorted(
            [
                pretty_format(pkg_update)
                for pkg_update in packages_updates
            ],
            key=lambda x: x[1],
        )
    ])


def pretty_format_sysupgrade(
        install_info: 'InstallInfoFetcher',
        verbose=False,
        manual_package_selection=False
) -> str:

    color = True

    repo_packages_updates = install_info.repo_packages_install_info
    thirdparty_repo_packages_updates = install_info.thirdparty_repo_packages_install_info
    aur_updates = install_info.aur_updates_install_info
    repo_replacements = install_info.repo_replacements_install_info
    thirdparty_repo_replacements = install_info.thirdparty_repo_replacements_install_info

    new_repo_deps: Optional[List['InstallInfo']] = \
        install_info.new_repo_deps_install_info
    new_thirdparty_repo_deps: Optional[List['InstallInfo']] = \
        install_info.new_thirdparty_repo_deps_install_info
    new_aur_deps: Optional[List['InstallInfo']] = \
        install_info.aur_deps_install_info

    if manual_package_selection:
        color = False
        new_repo_deps = None
        new_thirdparty_repo_deps = None
        new_aur_deps = None

    _color_line = color_line
    _bold_line = bold_line
    if not color:
        _color_line = lambda line, *args: line  # noqa
        _bold_line = lambda line: line  # noqa

    result = []

    if repo_replacements:
        result.append('\n{} {}'.format(
            _color_line('::', 12),
            _bold_line(_n(
                "Repository package suggested as a replacement:",
                "Repository packages suggested as a replacement:",
                len(repo_replacements)))
        ))
        result.append(pretty_format_upgradeable(
            repo_replacements,
            verbose=verbose, color=color,
            print_repo=PikaurConfig().sync.get_bool('AlwaysShowPkgOrigin')
        ))
    if thirdparty_repo_replacements:
        result.append('\n{} {}'.format(
            _color_line('::', 12),
            _bold_line(_n(
                "Third-party repository package suggested as a replacement:",
                "Third-party repository packages suggested as a replacement:",
                len(repo_packages_updates)))
        ))
        result.append(pretty_format_upgradeable(
            thirdparty_repo_replacements,
            verbose=verbose, color=color,
            print_repo=PikaurConfig().sync.get_bool('AlwaysShowPkgOrigin')
        ))

    if repo_packages_updates:
        result.append('\n{} {}'.format(
            _color_line('::', 12),
            _bold_line(_n(
                "Repository package will be installed:",
                "Repository packages will be installed:",
                len(repo_packages_updates)))
        ))
        result.append(pretty_format_upgradeable(
            repo_packages_updates,
            verbose=verbose, color=color,
            print_repo=PikaurConfig().sync.get_bool('AlwaysShowPkgOrigin')
        ))
    if new_repo_deps:
        result.append('\n{} {}'.format(
            _color_line('::', 11),
            _bold_line(_n("New dependency will be installed from repository:",
                          "New dependencies will be installed from repository:",
                          len(new_repo_deps)))
        ))
        result.append(pretty_format_upgradeable(
            new_repo_deps,
            verbose=verbose, color=color,
            print_repo=PikaurConfig().sync.get_bool('AlwaysShowPkgOrigin')
        ))
    if thirdparty_repo_packages_updates:
        result.append('\n{} {}'.format(
            _color_line('::', 12),
            _bold_line(_n("Third-party repository package will be installed:",
                          "Third-party repository packages will be installed:",
                          len(thirdparty_repo_packages_updates)))
        ))
        result.append(pretty_format_upgradeable(
            thirdparty_repo_packages_updates,
            verbose=verbose, color=color, print_repo=True
        ))
    if new_thirdparty_repo_deps:
        result.append('\n{} {}'.format(
            _color_line('::', 11),
            _bold_line(_n("New dependency will be installed from third-party repository:",
                          "New dependencies will be installed from third-party repository:",
                          len(new_thirdparty_repo_deps)))
        ))
        result.append(pretty_format_upgradeable(
            new_thirdparty_repo_deps,
            verbose=verbose, color=color,
            print_repo=PikaurConfig().sync.get_bool('AlwaysShowPkgOrigin')
        ))
    if aur_updates:
        result.append('\n{} {}'.format(
            _color_line('::', 14),
            _bold_line(_n("AUR package will be installed:",
                          "AUR packages will be installed:",
                          len(aur_updates)))
        ))
        result.append(pretty_format_upgradeable(
            aur_updates,
            verbose=verbose, color=color, print_repo=False
        ))
    if new_aur_deps:
        result.append('\n{} {}'.format(
            _color_line('::', 11),
            _bold_line(_n("New dependency will be installed from AUR:",
                          "New dependencies will be installed from AUR:",
                          len(new_aur_deps)))
        ))
        result.append(pretty_format_upgradeable(
            new_aur_deps,
            verbose=verbose, color=color, print_repo=False
        ))
    result += ['']
    return '\n'.join(result)


def pretty_format_repo_name(repo_name: str) -> str:
    return color_line(f'{repo_name}/', len(repo_name) % 5 + 10)


def print_ignored_package(package_name) -> None:
    from .updates import get_remote_package_version

    current = PackageDB.get_local_dict().get(package_name)
    current_version = current.version if current else ''
    new_version = get_remote_package_version(package_name)
    install_infos = [InstallInfo(
        name=package_name,
        current_version=current_version or '',
        new_version=new_version or '',
        package=None,
    )]
    print_stderr('{} {}'.format(
        color_line('::', 11),
        _("Ignoring package update {}").format(
            pretty_format_upgradeable(
                install_infos,
                template="{pkg_name} ({current_version} => {new_version})"
            ))
        if (current_version and new_version) else
        _("Ignoring package {}").format(
            pretty_format_upgradeable(
                install_infos,
                template=(
                    "{pkg_name} {current_version}"
                    if current_version else
                    "{pkg_name} {new_version}"
                )
            ))
    ))


def print_package_uptodate(package_name: str, package_source: PackageSource) -> None:
    print_warning(
        _("{name} {version} {package_source} package is up to date - skipping").format(
            name=package_name,
            version=bold_line(
                PackageDB.get_local_dict()[package_name].version
            ),
            package_source=package_source.name
        )
    )


# @TODO: weird pylint behavior if remove `return` from the end:
def print_package_search_results(  # pylint:disable=useless-return,too-many-locals
        packages: Iterable[AnyPackage],
        local_pkgs_versions: Dict[str, str],
        enumerated=False,
        enumerate_from=0,
) -> None:

    from .aur import AURPackageInfo  # noqa  pylint:disable=redefined-outer-name

    def get_sort_key(pkg: AnyPackage) -> float:
        if (
                isinstance(pkg, AURPackageInfo) and
                isinstance(pkg.numvotes, int) and
                isinstance(pkg.popularity, float)
        ):
            return (pkg.numvotes + 1) * (pkg.popularity + 1)
        return 1

    args = parse_args()
    local_pkgs_names = local_pkgs_versions.keys()
    for pkg_idx, package in enumerate(sorted(
            packages,
            key=get_sort_key,
            reverse=True
    )):
        # @TODO: return only packages for the current architecture
        pkg_name = package.name
        if args.quiet:
            print(pkg_name)
        else:

            idx = ''
            if enumerated:
                idx = bold_line(f'{pkg_idx+enumerate_from}) ')

            repo = color_line('aur/', 9)
            if isinstance(package, pyalpm.Package):
                repo = pretty_format_repo_name(package.db.name)

            groups = ''
            if getattr(package, 'groups', None):
                groups = color_line('({}) '.format(' '.join(package.groups)), GROUP_COLOR)

            installed = ''
            if pkg_name in local_pkgs_names:
                if package.version != local_pkgs_versions[pkg_name]:
                    installed = color_line(_("[installed: {version}]").format(
                        version=local_pkgs_versions[pkg_name],
                    ) + ' ', 14)
                else:
                    installed = color_line(_("[installed]") + ' ', 14)

            rating = ''
            if (
                    isinstance(package, AURPackageInfo)
            ) and (
                package.numvotes is not None
            ) and (
                package.popularity is not None
            ):
                rating = color_line('({}, {:.2f})'.format(
                    package.numvotes,
                    package.popularity
                ), 3)

            color_config = PikaurConfig().colors
            version_color = color_config.get_int('Version')
            version = package.version

            if isinstance(package, AURPackageInfo) and package.outofdate is not None:
                version_color = color_config.get_int('VersionDiffOld')
                version = "{} [{}: {}]".format(
                    package.version,
                    _("outofdate"),
                    datetime.fromtimestamp(package.outofdate).strftime('%Y/%m/%d')
                )

            print("{}{}{} {} {}{}{}".format(
                idx,
                repo,
                bold_line(pkg_name),
                color_line(version, version_color),
                groups,
                installed,
                rating
            ))
            print(format_paragraph(f'{package.desc}'))
    return
