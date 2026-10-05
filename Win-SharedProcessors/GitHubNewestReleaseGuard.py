#!/usr/local/autopkg/python
"""Stop the recipe when the release that GitHubReleasesInfoProvider selected is
not the newest one.

The core processor GitHubReleasesInfoProvider walks the releases of a
repository from the newest and takes the first one that has a file whose name
matches asset_regex, however old that release is. When a vendor changes the
spelling of a file name, it goes back to the last release with the old
spelling and says nothing. This processor runs right after it, before the
download. It asks GitHub once for the newest releases of the same repository
(the repository is read from the API URL of the selected asset, so it cannot
differ from the provider's), finds the newest release that the provider could
take, and stops the recipe (ProcessorError) when the selected asset is not one
of that release's files. The message names the selected release, the newest
one, the files of the newest one (the new spelling of the name is among them)
and what to do.

The newest release is the first one in GitHub's list (the order that the
provider walks) that is not a draft and, unless include_prereleases is true
(read from the run's variables and tested for truth, as the provider does), not
a pre-release, and, when release_tag_pattern is given, whose tag matches it. The
guard compares positions in that list, not versions. A vendor that publishes two
lines of releases side by side names the line it follows with release_tag_pattern
(for example v1\\.4\\.), else a release of the other line on top stops the run, and a
release of the older line published after the newer one would pass unseen.
A release without files counts as the newest. A newest release that carries no
Windows installer file (a name ending in .msi, .exe or .msix) on purpose is accepted by
naming its tag in accepted_newest_release (in the override): the guard then passes
only while that release is still the newest and has no such file, only when no release
that lies between it and the selected one has one either, says so on every run
(in the log and in AutoPkg's summary), and stops again when a newer release appears.
A release with an installer file is a renamed installer: no acceptance is offered for
it and none is honoured, the cure is the pattern. A release_tag_pattern that leaves
newer releases out says so on every run, with their tags.

The provider inputs sort_by_highest_tag_names and latest_only change which
release the provider takes (GitHubReleasesInfoProvider.py:222-225, :148-149). The
guard does not model them: a recipe that sets either is refused with a message.

The request is anonymous and goes to the API of one fixed host. A redirect is
not followed: it is an error that names the status. The recipe stops when the
URL is not the API URL of an asset, when the request fails or is refused (the
message says when GitHub's limit for anonymous requests is the reason), when the
answer is not a list of releases, or when no release can be compared.
"""
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from autopkglib import Processor, ProcessorError

__all__ = [
    "GitHubNewestReleaseGuard",
    "parse_asset_url",
    "releases_url",
    "is_candidate",
    "newest_candidate",
    "release_with_asset",
    "pass_message",
    "accepted_message",
    "skipped_message",
    "installer_files",
    "releases_between",
    "fetch_json",
    "fetch_releases",
    "read_releases",
    "stop_message",
]

API_ROOT = "https://api.github.com"
# The only kind of URL that is accepted: the API record of one release asset.
# The repository to ask about is read from it.
ASSET_API_URL_PATTERN = re.compile(
    r"https://api\.github\.com/repos/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"/releases/assets/(?P<asset_id>[0-9]+)"
)
# Only to name the selected release in a message, never to decide: the download
# URL that the provider leaves in the run holds the tag and the file name.
DOWNLOAD_URL_PATTERN = re.compile(
    r"https://github\.com/[^/]+/[^/]+/releases/download/(?P<tag>[^/]+)/(?P<name>[^/?#]+)"
)
# The provider's own page size (GitHubReleasesInfoProvider.py, get_releases).
RELEASES_PER_PAGE = 30
# Pages that are read when every release of a page is a pre-release or a draft.
MAX_PAGES = 3
FETCH_TIMEOUT_SECONDS = 30
# A page of thirty releases with their texts is some hundreds of kilobytes
# (the longest of the first eight repositories: 0.8 MB); more than this is not one.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
USER_AGENT = "autopkg-GitHubNewestReleaseGuard"
MAX_ASSET_NAMES_SHOWN = 30
MAX_SHOWN_CHARACTERS = 80
RATE_LIMIT_STATUSES = (403, 429)

# A tag that is safe to put in a command line that an operator copies: nothing that
# a shell reads. A tag comes from GitHub and can hold any character that git allows.
SAFE_TAG_PATTERN = re.compile(r"[A-Za-z0-9._+-]{1,80}")
UNSUPPORTED_PROVIDER_INPUTS = ("sort_by_highest_tag_names", "latest_only")
# A file whose name ends like this is a Windows installer. A release that has one is not
# a release "without an installer": a recipe that misses it has a pattern to correct.
INSTALLER_EXTENSIONS = (".msi", ".exe", ".msix")
MAX_INSTALLER_NAMES_SHOWN = 5
# Releases that are named in a message about the releases between two others.
MAX_BETWEEN_SHOWN = 5
# Tags that are named in the line about the releases that release_tag_pattern left out.
MAX_SKIPPED_TAGS_SHOWN = 5
# The variable of AutoPkg's end-of-run summary (the name ends in _summary_result, as AutoPkg
# collects it; the neighbours: cimian_importer_summary_result, url_downloader_summary_result).
SUMMARY_KEY = "github_newest_release_guard_summary_result"
SUMMARY_FIELDS = ["repository", "newest_release", "release_taken", "reason"]


def installer_files(release):
    """The names of the files of a release that end in a Windows installer's extension
    (INSTALLER_EXTENSIONS, in any letter case)."""
    names = []
    for asset in release.get("assets") or []:
        name = asset.get("name")
        if isinstance(name, str) and name.lower().endswith(INSTALLER_EXTENSIONS):
            names.append(name)
    return names


def names_text(names, limit):
    """Up to `limit` names, then how many more."""
    text = ", ".join(shown(name) for name in names[:limit])
    if len(names) > limit:
        text += " and %d more" % (len(names) - limit)
    return text


def releases_between(releases, newest, selected, include_prereleases, tag_pattern=None):
    """The candidates that are listed after `newest` and before `selected` (up to the end of the
    list when `selected` is None, a release that the list does not hold): releases that the
    provider passed on its way down, so none of them has a file that asset_regex takes."""
    found = []
    started = False
    for release in releases:
        if release is newest:
            started = True
            continue
        if not started:
            continue
        if selected is not None and release is selected:
            break
        if is_candidate(release, include_prereleases, tag_pattern):
            found.append(release)
    return found


def listed_above(releases, newest, selected):
    """True when `selected` is listed before `newest`: not an older release."""
    if selected is None:
        return False
    for release in releases:
        if release is selected:
            return True
        if release is newest:
            return False
    return False


def with_installers(newest, between):
    """The releases among the newest one and those between it and the selected one that have a
    Windows installer file: what an acceptance must not cover."""
    return [release for release in [newest] + list(between) if installer_files(release)]


def what_to_do(newest, between=()):
    """The advice at the end of a stop. An acceptance is offered only when no release among the
    newest one and those between it and the selected one has a Windows installer file, and
    its command only when the newest release's tag is safe to put in one."""
    two_lines = (
        "If the vendor publishes two lines of releases side by side, and only then, name the line you follow "
        "with release_tag_pattern in the override (a pattern hides the releases it leaves out: it is not a "
        "cure for a rename; every run says which ones it left out)."
    )
    blockers = with_installers(newest, between)
    if blockers:
        listed = "; ".join(
            "release %s (%s)" % (release_label(release), names_text(installer_files(release), MAX_INSTALLER_NAMES_SHOWN))
            for release in blockers[:MAX_BETWEEN_SHOWN])
        if len(blockers) > MAX_BETWEEN_SHOWN:
            listed += "; and %d more" % (len(blockers) - MAX_BETWEEN_SHOWN)
        return (
            "What to do: the newest release, or a release between it and the selected one, has Windows installer "
            "files: %s. That is a renamed installer, not a release without one: correct SEARCH_PATTERN (the "
            "provider's asset_regex) in the override so that it matches one of them. No acceptance is offered for it: "
            "accepted_newest_release is only for a newest release that has no file ending in %s. %s"
            % (listed, ", ".join(INSTALLER_EXTENSIONS), two_lines)
        )
    tag = newest.get("tag_name")
    if isinstance(tag, str) and SAFE_TAG_PATTERN.fullmatch(tag):
        accept = (
            "accept exactly that release in the override: `/usr/libexec/PlistBuddy -c "
            "'Set :Input:accepted_newest_release %s' <the override>` (for an override that has no such "
            "key yet: `Add :Input:accepted_newest_release string %s`)." % (tag, tag)
        )
    else:
        accept = (
            "accept exactly that release by putting its tag into the key accepted_newest_release of the "
            "override's Input (the tag has characters that a shell reads, so no command is printed; copy the "
            "tag exactly as the vendor's release page writes it, because the tag above is cleaned and cut for "
            "printing)."
        )
    return (
        "What to do: if the vendor has renamed the installer, correct SEARCH_PATTERN (the provider's "
        "asset_regex) in the override so that it matches a file of the newest release. If the newest "
        "release has no Windows installer on purpose (no file ending in %s) and you have looked at it, %s "
        "The recipe then takes the older release only while that release is the newest and has no such file; "
        "the next newer release stops it again. %s" % (", ".join(INSTALLER_EXTENSIONS), accept, two_lines)
    )


def parse_accepted_tag(value):
    """The tag that accepted_newest_release names, or None when it names none.
    Anything but text is an error (the earlier true/false switch is gone)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    raise ProcessorError(
        "accepted_newest_release must be the tag of a release, as text, not %r (a switch that turned "
        "the whole check off does not exist)." % (value,)
    )


def parse_tag_pattern(value):
    """The compiled release_tag_pattern, or None when none is given. It is matched
    from the start of the tag, like the provider matches asset_regex."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProcessorError("release_tag_pattern must be a regular expression, as text, not %r." % (value,))
    if not value.strip():
        return None
    try:
        return re.compile(value)
    except re.error as err:
        raise ProcessorError("release_tag_pattern is not a regular expression: %s." % shown(str(err)))


def shown(value):
    """Text from GitHub for a message: printable characters only, and short."""
    text = value if isinstance(value, str) else "?"
    text = "".join(char if char.isprintable() else "?" for char in text)
    # A message marks commands with backticks: none that comes from GitHub is let through.
    text = text.replace("`", "'")
    if len(text) > MAX_SHOWN_CHARACTERS:
        text = text[:MAX_SHOWN_CHARACTERS] + "..."
    return text


# ---- the URL ----------------------------------------------------------------


def parse_asset_url(url):
    """Return (owner, repo, asset_id) of the API URL of a release asset, or
    raise ValueError with a reason that is safe to show."""
    if not isinstance(url, str):
        raise ValueError("it is not text")
    match = ASSET_API_URL_PATTERN.fullmatch(url)
    if match is None:
        raise ValueError("it is not the API URL of a release asset")
    owner, repo = match.group("owner"), match.group("repo")
    for name in (owner, repo):
        if not name.strip("."):
            raise ValueError("a name of the repository is made of dots only")
    return owner, repo, int(match.group("asset_id"))


def releases_url(owner, repo, page):
    """The one URL that is fetched: a page of the release list of the repository."""
    return "%s/repos/%s/%s/releases?per_page=%d&page=%d" % (
        API_ROOT, owner, repo, RELEASES_PER_PAGE, page)


def names_from_download_url(url):
    """(tag, file name) from the provider's download URL, or (None, None)."""
    if isinstance(url, str):
        match = DOWNLOAD_URL_PATTERN.fullmatch(url)
        if match:
            return (urllib.parse.unquote(match.group("tag")),
                    urllib.parse.unquote(match.group("name")))
    return None, None


# ---- the rule ---------------------------------------------------------------


def is_candidate(release, include_prereleases, tag_pattern=None):
    """True for a release that the provider could select from. A draft is never
    one (an anonymous list holds none; the provider has no rule for them). A
    pre-release is one only when include_prereleases is true (the provider:
    GitHubReleasesInfoProvider.py, select_asset). With a tag pattern (a compiled
    regular expression), only a release whose tag matches it from the start is
    one: the line of releases that the recipe follows."""
    if release.get("draft"):
        return False
    if release.get("prerelease") and not include_prereleases:
        return False
    if tag_pattern is not None:
        tag = release.get("tag_name")
        if not isinstance(tag, str) or tag_pattern.match(tag) is None:
            return False
    return True


def newest_candidate(releases, include_prereleases, tag_pattern=None):
    """The first release of the list, in GitHub's order (newest first, the order
    that the provider walks), that is a candidate. None when there is none. A
    release without files counts."""
    for release in releases:
        if is_candidate(release, include_prereleases, tag_pattern):
            return release
    return None


def asset_id_of(asset):
    """The id of an asset record as a number, or None."""
    value = asset.get("id")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def holds_asset(release, asset_id):
    return any(asset_id_of(asset) == asset_id for asset in release.get("assets") or [])


def release_with_asset(releases, asset_id):
    """The release of the list that has the asset, or None."""
    for release in releases:
        if holds_asset(release, asset_id):
            return release
    return None


def check_releases(releases):
    """Raise ValueError with a reason that is safe to show when the answer is
    not a list of release records as far as this processor reads them."""
    if not isinstance(releases, list):
        raise ValueError("the answer is not a list of releases")
    for release in releases:
        if not isinstance(release, dict):
            raise ValueError("an entry of the list is not a release record")
        assets = release.get("assets")
        if assets is not None and (
            not isinstance(assets, list) or not all(isinstance(asset, dict) for asset in assets)
        ):
            raise ValueError("the files of a release are not a list of records")


# ---- the messages -----------------------------------------------------------


def release_label(release):
    """The tag of a release, with its title when that is another text (the
    provider's line `Selected asset ... from release ...` names the title)."""
    tag = release.get("tag_name")
    title = release.get("name")
    text = "'%s'" % shown(tag)
    if isinstance(title, str) and title.strip() and title != tag:
        text += " (titled '%s')" % shown(title)
    return text


def asset_names_text(release):
    names = [shown(asset.get("name")) for asset in release.get("assets") or []]
    if not names:
        return "none (the release has no files)"
    if len(names) > MAX_ASSET_NAMES_SHOWN:
        more = len(names) - MAX_ASSET_NAMES_SHOWN
        names = names[:MAX_ASSET_NAMES_SHOWN] + ["and %d more" % more]
    return ", ".join(names)


def describe_selected(releases, asset_id, download_url):
    """(release text, file text, listed) for the selected asset: from the list
    when it holds the asset, else from the download URL that the provider left."""
    found = release_with_asset(releases, asset_id)
    if found is not None:
        for asset in found["assets"]:
            if asset_id_of(asset) == asset_id:
                return "release " + release_label(found), "'%s'" % shown(asset.get("name")), True
    tag, name = names_from_download_url(download_url)
    where = "not in the list that was read"
    release_text = ("release '%s' (%s)" % (shown(tag), where)) if tag else "a release that is %s" % where
    file_text = ("'%s'" % shown(name)) if name else "asset %d (its name is not known)" % asset_id
    return release_text, file_text, False


NOT_LISTED_NOTE = (
    "The selected file is not in the list that was read: either GitHub's list changed after the provider "
    "read it (run the recipe again before changing anything), or its release is older than the %d releases "
    "that were read."
)


def newest_kind(include_prereleases, tag_pattern=None):
    text = "newest release" if include_prereleases else "newest release that is not a pre-release"
    if tag_pattern is not None:
        text += " whose tag matches '%s'" % shown(tag_pattern.pattern)
    return text


def pass_message(owner, repo, newest, include_prereleases, tag_pattern=None):
    """The line of a run that passes (printed with -v)."""
    return "The selected release %s of %s/%s is the %s." % (
        release_label(newest), owner, repo, newest_kind(include_prereleases, tag_pattern))


def accepted_message(owner, repo, newest, releases, asset_id, download_url):
    """The line of a run that takes an older release on purpose: always printed,
    one line, with the reason and the files of the accepted release."""
    release_text, file_text, _ = describe_selected(releases, asset_id, download_url)
    names = [asset.get("name") for asset in newest.get("assets") or []]
    count = len(names)
    files = "no files" if not count else "%d file%s (%s)" % (
        count, "" if count == 1 else "s", names_text(names, MAX_INSTALLER_NAMES_SHOWN))
    return (
        "An older release is taken on purpose: the newest release of %s/%s, %s, has %s and "
        "the override accepts it as the newest (accepted_newest_release); the provider took %s, file %s. "
        "A newer release stops the run again."
        % (owner, repo, release_label(newest), files, release_text, file_text)
    )


def skipped_by_pattern(releases, newest, include_prereleases):
    """The releases listed above `newest` that would count but for release_tag_pattern."""
    found = []
    for release in releases:
        if release is newest:
            break
        if is_candidate(release, include_prereleases, None):
            found.append(release)
    return found


def skipped_message(owner, repo, tag_pattern, skipped):
    """The line of every run in which release_tag_pattern left newer releases out."""
    tags = ", ".join("'%s'" % shown(release.get("tag_name")) for release in skipped[:MAX_SKIPPED_TAGS_SHOWN])
    if len(skipped) > MAX_SKIPPED_TAGS_SHOWN:
        tags += " and %d more" % (len(skipped) - MAX_SKIPPED_TAGS_SHOWN)
    return (
        "release_tag_pattern '%s' left out %d newer release%s of %s/%s: %s. If one of them carries the installer "
        "that this recipe should take, the pattern hides a rename."
        % (shown(tag_pattern.pattern), len(skipped), "" if len(skipped) == 1 else "s", owner, repo, tags)
    )


def selected_tag_text(releases, asset_id, download_url):
    """The tag of the selected release for the summary: from the list, else from the download URL."""
    found = release_with_asset(releases, asset_id)
    if found is not None:
        return shown(found.get("tag_name"))
    tag, _ = names_from_download_url(download_url)
    return shown(tag) if tag else "not in the list that was read"


def summary_result(owner, repo, newest, taken, reasons):
    """The entry of AutoPkg's end-of-run table (and of its report plist). The values are
    text, as the table needs: tags and a reason, nothing else."""
    return {
        "summary_text": "The release guard let a run go on with something to look at:",
        "report_fields": list(SUMMARY_FIELDS),
        "data": {
            "repository": "%s/%s" % (owner, repo),
            "newest_release": shown(newest.get("tag_name")),
            "release_taken": taken,
            "reason": "; ".join(reasons),
        },
    }


def between_text(between):
    """The releases that lie between the newest and the selected one, with their files."""
    parts = ["release %s, with the files: %s" % (release_label(release), asset_names_text(release))
             for release in between[:MAX_BETWEEN_SHOWN]]
    if len(between) > MAX_BETWEEN_SHOWN:
        parts.append("and %d more" % (len(between) - MAX_BETWEEN_SHOWN))
    return "; ".join(parts)


def accept_note(accepted, newest, between, above):
    """What to say about a set accepted_newest_release that did not let the run go on."""
    tag = shown(accepted)
    if newest.get("tag_name") != accepted:
        return "accepted_newest_release is '%s', which is not the newest release. " % tag
    if installer_files(newest):
        return ("accepted_newest_release is '%s', but that release has Windows installer files (%s): it is "
                "no longer accepted. " % (tag, names_text(installer_files(newest), MAX_INSTALLER_NAMES_SHOWN)))
    if any(installer_files(release) for release in between):
        return ("accepted_newest_release is '%s', but a release between it and the selected one has Windows "
                "installer files: an acceptance does not cover a rename below it. " % tag)
    if above:
        return ("accepted_newest_release is '%s', but the provider took a release that is listed above it: an "
                "acceptance covers an older release only. " % tag)
    return ""


def stop_message(owner, repo, include_prereleases, newest, releases, asset_id, download_url,
                 tag_pattern=None, accepted=None, between=(), above=False):
    """The text of the error for a selected release that is not the newest."""
    release_text, file_text, listed = describe_selected(releases, asset_id, download_url)
    text = (
        "The release that GitHubReleasesInfoProvider selected for %s/%s is not the %s. "
        "Selected: %s, file %s. "
        "Newest: release %s, with the files: %s. "
        % (owner, repo, newest_kind(include_prereleases, tag_pattern), release_text, file_text,
           release_label(newest), asset_names_text(newest))
    )
    if between:
        text += "Between them in the list: %s. " % between_text(list(between))
    text += (
        "AutoPkg's provider takes the first release, newest first, that has a file matching "
        "asset_regex, however old, and says nothing: a new spelling of the file name in the "
        "newest release sends the recipe back to an older one. "
    )
    if not listed:
        text += NOT_LISTED_NOTE % len(releases) + " "
    if accepted is not None:
        text += accept_note(accepted, newest, list(between), above)
    return text + what_to_do(newest, between)


def rate_limit_message(code, headers):
    """The text for an answer that is GitHub's rate limit, or None when it is
    not one. The limit for anonymous requests is a few dozen an hour for one
    address, and this processor sends no credential."""
    if code not in RATE_LIMIT_STATUSES or headers is None:
        return None
    remaining = headers.get("X-RateLimit-Remaining")
    retry_after = headers.get("Retry-After")
    if remaining != "0" and retry_after is None:
        return None
    when = ""
    try:
        if remaining == "0" and headers.get("X-RateLimit-Reset") is not None:
            moment = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(headers.get("X-RateLimit-Reset"))))
            when = " The limit resets at %s." % moment
        elif retry_after is not None:
            when = " GitHub asks to wait %d seconds." % int(retry_after)
    except (ValueError, OverflowError, OSError):
        when = ""
    return (
        "GitHub's limit for anonymous requests is used up (GitHub answered %d); the guard "
        "sends no credential.%s Run the recipe again later." % (code, when)
    )


# ---- the request ------------------------------------------------------------


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The release list is a plain answer of the one fixed host. A redirect
    would send the request elsewhere: it is an error (HTTPError)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_request(request):
    """Send the request without following redirects."""
    opener = urllib.request.build_opener(NoRedirect)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def fetch_json(url, what):
    """GET the URL and return the decoded JSON. No credential is sent. The one
    place where the network is used: tests replace open_request()."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with open_request(request) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as err:
        code, reason, headers = err.code, err.reason, err.headers
        limited = rate_limit_message(code, headers)
        err.close()
        if limited:
            raise ProcessorError(limited)
        if code == 404:
            raise ProcessorError(
                "GitHub answered 404 Not Found for %s: the repository does not exist or is not public." % what)
        redirect = " (a redirect is not followed)" if 300 <= code < 400 else ""
        raise ProcessorError("GitHub answered %s %s for %s%s." % (code, shown(reason), what, redirect))
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as err:
        raise ProcessorError("%s could not be fetched: %s" % (what[:1].upper() + what[1:], shown(str(err))))
    if len(body) > MAX_RESPONSE_BYTES:
        raise ProcessorError("The answer for %s is larger than %d bytes." % (what, MAX_RESPONSE_BYTES))
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as err:
        raise ProcessorError("The answer for %s is not JSON: %s" % (what, shown(str(err))))


def fetch_releases(owner, repo, page):
    """One page of the release list of the repository, checked for its shape."""
    what = "the release list of %s/%s" % (owner, repo)
    releases = fetch_json(releases_url(owner, repo, page), what)
    try:
        check_releases(releases)
    except ValueError as err:
        raise ProcessorError("The answer for %s is unusable: %s." % (what, err))
    return releases


def read_releases(owner, repo, include_prereleases, tag_pattern=None):
    """Read pages of the list, newest first, until a page holds a candidate, the
    list ends or MAX_PAGES are read. Returns every release that was read."""
    seen = []
    for page in range(1, MAX_PAGES + 1):
        batch = fetch_releases(owner, repo, page)
        seen.extend(batch)
        if newest_candidate(batch, include_prereleases, tag_pattern) is not None:
            break
        if len(batch) < RELEASES_PER_PAGE:
            break
    return seen


class GitHubNewestReleaseGuard(Processor):
    description = __doc__
    input_variables = {
        "github_asset_api_url": {
            "required": True,
            "description": (
                "The API URL of the release asset that the provider selected, "
                "https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>. "
                "In a recipe it is fed from the output of the core processor "
                "GitHubReleasesInfoProvider (expected: asset_url). The repository "
                "that is asked about is the one in this URL."
            ),
        },
        "include_prereleases": {
            "required": False,
            "description": (
                "Read from the run's variables, not passed by a step, and tested for "
                "truth like the provider's input of the same name: when it is true "
                "(or any non-empty value, the text false included) a pre-release can "
                "be the newest release; when it is not, a pre-release is skipped."
            ),
        },
        "accepted_newest_release": {
            "required": False,
            "default": "",
            "description": (
                "Empty (the default): the run stops when the selected release is not the "
                "newest. The tag of a release: when that release is the newest and the "
                "provider took an older one, the run goes on and says so in every run; when "
                "a newer release appears, it stops again. For a newest release that has no "
                "Windows installer on purpose, after somebody looked at it. Set in an "
                "override, never in a recipe."
            ),
        },
        "release_tag_pattern": {
            "required": False,
            "default": "",
            "description": (
                "Empty (the default): every release is of the line that the recipe follows. "
                "A regular expression matched from the start of a tag: only a release whose "
                "tag matches counts as the newest, for a vendor that publishes two lines of "
                "releases side by side. Set in an override."
            ),
        },
        "sort_by_highest_tag_names": {
            "required": False,
            "description": (
                "The provider's input of the same name. Not supported: when it is true "
                "(or any non-empty value) the guard refuses the recipe."
            ),
        },
        "latest_only": {
            "required": False,
            "description": (
                "The provider's input of the same name. Not supported: when it is true "
                "(or any non-empty value) the guard refuses the recipe."
            ),
        },
        "url": {
            "required": False,
            "description": (
                "The download URL that the provider left in the run. Used only to "
                "name the selected release in the message when the list does not "
                "hold the asset."
            ),
        },
    }
    output_variables = {
        SUMMARY_KEY: {
            "description": (
                "Set only when the run goes on with something that a person should look at: "
                "an older release taken on purpose (accepted_newest_release) or newer releases "
                "that release_tag_pattern left out. AutoPkg puts it into its end-of-run table "
                "and its report plist: the repository, the newest release's tag, the tag taken "
                "and the reason. Tags only: no secret, no path."
            ),
        },
    }

    def main(self):
        # A result of an earlier recipe of the same run must not be reported again.
        self.env.pop(SUMMARY_KEY, None)
        asset_url = self.env.get("github_asset_api_url")
        try:
            owner, repo, asset_id = parse_asset_url(asset_url)
        except ValueError as err:
            raise ProcessorError(
                "github_asset_api_url is not the API URL of a release asset "
                "(https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>): %s." % err
            )
        if self.env.get("allow_older_release"):
            raise ProcessorError(
                "allow_older_release does not exist any more: it turned the whole check off. Name the "
                "release that you accept in accepted_newest_release instead (the tag of the newest "
                "release)."
            )
        accepted = parse_accepted_tag(self.env.get("accepted_newest_release"))
        tag_pattern = parse_tag_pattern(self.env.get("release_tag_pattern"))
        for name in UNSUPPORTED_PROVIDER_INPUTS:
            if self.env.get(name):
                raise ProcessorError(
                    "The guard compares by the order of GitHub's list and does not support the provider's "
                    "input %s, which changes which release the provider takes. Remove it from the "
                    "override's Input; for a vendor that publishes two lines of releases side by side, "
                    "name the line with release_tag_pattern instead." % name
                )
        include_prereleases = bool(self.env.get("include_prereleases"))
        releases = read_releases(owner, repo, include_prereleases, tag_pattern)
        if not releases:
            raise ProcessorError(
                "GitHub lists no release of %s/%s, so the selected release cannot be compared "
                "with the newest one." % (owner, repo)
            )
        newest = newest_candidate(releases, include_prereleases, tag_pattern)
        if newest is None:
            raise ProcessorError(
                "Among the %d newest releases of %s/%s GitHub lists none that the provider could "
                "take (every one is a pre-release, a draft or not of the line named by "
                "release_tag_pattern), so the selected release cannot be compared with the newest "
                "one. If that is right for this vendor, set include_prereleases to true or correct "
                "release_tag_pattern in the override." % (len(releases), owner, repo)
            )
        download_url = self.env.get("url")
        reasons = []
        if tag_pattern is not None:
            skipped = skipped_by_pattern(releases, newest, include_prereleases)
            if skipped:
                self.output(skipped_message(owner, repo, tag_pattern, skipped), verbose_level=0)
                reasons.append("release_tag_pattern left out %d newer release%s" % (
                    len(skipped), "" if len(skipped) == 1 else "s"))
        if holds_asset(newest, asset_id):
            self.output(pass_message(owner, repo, newest, include_prereleases, tag_pattern))
            if accepted is not None:
                self.output(
                    "accepted_newest_release is '%s' but is not needed: the selected release is the "
                    "newest." % shown(accepted)
                )
            if reasons:
                self.env[SUMMARY_KEY] = summary_result(owner, repo, newest, shown(newest.get("tag_name")), reasons)
            return
        selected = release_with_asset(releases, asset_id)
        between = releases_between(releases, newest, selected, include_prereleases, tag_pattern)
        above = listed_above(releases, newest, selected)
        if (accepted is not None and newest.get("tag_name") == accepted and not above
                and not with_installers(newest, between)):
            self.output(accepted_message(owner, repo, newest, releases, asset_id, download_url), verbose_level=0)
            reasons.append("accepted_newest_release: an older release is taken on purpose")
            self.env[SUMMARY_KEY] = summary_result(
                owner, repo, newest, selected_tag_text(releases, asset_id, download_url), reasons)
            return
        raise ProcessorError(
            stop_message(owner, repo, include_prereleases, newest, releases, asset_id, download_url,
                         tag_pattern, accepted, between, above)
        )


if __name__ == "__main__":
    processor = GitHubNewestReleaseGuard()
    processor.execute_shell()
