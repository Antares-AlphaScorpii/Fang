from pathlib import Path
import shutil
import re
import json
import subprocess
import urllib.parse
import urllib.request
import time

import click
from mutagen import File


AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".mp4",
    ".flac",
    ".wav",
    ".aiff",
    ".aif",
    ".ogg",
    ".opus",
    ".wma",
}


def get_audio_files(source_dir):
    """Find supported audio files recursively."""
    source = Path(source_dir)

    return [
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]


def clean_metadata_value(value):
    """Convert Mutagen metadata values into clean strings."""
    if value is None:
        return None

    if isinstance(value, list):
        if not value:
            return None
        value = value[0]

    value = str(value).strip()

    return value if value else None


def get_tag(audio, *names):
    """Get the first available metadata tag."""
    for name in names:
        if name in audio:
            value = clean_metadata_value(audio[name])
            if value:
                return value

    return None


def extract_metadata(file_path):
    """
    Extract Artist, Album Artist, Album and Title.

    Album Artist is preferred when available so featured artists
    do not split an album into separate artist folders.
    """
    try:
        audio = File(file_path, easy=True)

        if audio is None:
            return {
                "artist": None,
                "album_artist": None,
                "album": None,
                "title": None,
            }

        artist = get_tag(audio, "artist")
        album_artist = get_tag(audio, "albumartist", "album artist")
        album = get_tag(audio, "album")
        title = get_tag(audio, "title")

        return {
            "artist": artist,
            "album_artist": album_artist,
            "album": album,
            "title": title,
        }

    except Exception:
        return {
            "artist": None,
            "album_artist": None,
            "album": None,
            "title": None,
        }


def sanitize_name(name):
    """Make a metadata value safe for use as a macOS filename/folder."""
    if not name:
        return ""

    name = str(name).strip()

    # Characters that cannot safely appear in filenames.
    name = re.sub(r'[/:*?"<>|]', "-", name)

    # Remove control characters.
    name = re.sub(r"[\x00-\x1f]", "", name)

    # Avoid trailing periods/spaces.
    name = name.rstrip(". ")

    return name or "Unknown"


def normalize_filename(name):
    """
    Normalize a filename for comparison.

    This is intentionally forgiving. Fang should recognize things like:

        Lights
        13. Lights
        01 - Lights
        Ellie Goulding - Lights
        Lights (Official Audio)

    as reasonable filenames for the track 'Lights'.
    """
    name = Path(name).stem

    name = name.lower()

    # Remove common track-number prefixes.
    name = re.sub(
        r"^\s*(?:track\s*)?\d{1,3}\s*[\-_.:)]*\s*",
        "",
        name,
    )

    # Replace separators with spaces.
    name = re.sub(r"[_\-–—]+", " ", name)

    # Remove common parenthetical/bracketed extras.
    name = re.sub(
        r"\s*[\(\[]\s*(?:official\s+audio|official\s+video|lyrics?|audio|video|"
        r"explicit|clean|remastered?|radio\s+edit|single\s+version)\s*[\)\]]",
        "",
        name,
        flags=re.IGNORECASE,
    )

    # Normalize whitespace.
    name = re.sub(r"\s+", " ", name).strip()

    return name


def filename_matches_title(filename, title, artist=None):
    """
    Decide whether an existing filename is reasonably similar
    to the metadata title.

    Returns:
        True  = keep the existing filename
        False = Fang may suggest a rename
    """
    if not title:
        return False

    filename_normalized = normalize_filename(filename)
    title_normalized = normalize_filename(title)

    if not filename_normalized or not title_normalized:
        return False

    # Exact title match.
    if filename_normalized == title_normalized:
        return True

    # Existing filename contains the complete title.
    if title_normalized in filename_normalized:
        return True

    # Metadata title contains the filename.
    if filename_normalized in title_normalized:
        return True

    # Also recognize "Artist - Title".
    if artist:
        artist_normalized = normalize_filename(artist)

        combined = f"{artist_normalized} {title_normalized}".strip()

        if filename_normalized == combined:
            return True

        if (
            artist_normalized in filename_normalized
            and title_normalized in filename_normalized
        ):
            return True

    return False


def identify_with_acoustid(
    file_path,
    api_key,
    existing_metadata=None,
):
    """
    Identify an audio file using AcoustID and MusicBrainz.

    AcoustID may return several matches. Fang checks all matches
    that contain MusicBrainz recording IDs and compares them with
    existing metadata when available.
    """
    if not api_key:
        return None

    existing_metadata = existing_metadata or {}

    existing_artist = (
        existing_metadata.get("artist") or ""
    ).strip().lower()

    existing_title = (
        existing_metadata.get("title") or ""
    ).strip().lower()

    existing_album = (
        existing_metadata.get("album") or ""
    ).strip().lower()

    try:
        result = subprocess.run(
            [
                "fpcalc",
                "-json",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        fp_data = json.loads(result.stdout)

        duration = int(
            float(
                fp_data.get("duration", 0)
            )
        )

        fingerprint = fp_data.get("fingerprint")

        if not duration or not fingerprint:
            return None

        params = {
            "format": "json",
            "client": api_key,
            "duration": duration,
            "fingerprint": fingerprint,
            "meta": "recordingids",
        }

        url = (
            "https://api.acoustid.org/v2/lookup?"
            + urllib.parse.urlencode(params)
        )

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Fang/1.0"},
        )

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        if data.get("status") != "ok":
            return None

        results = sorted(
            data.get("results", []),
            key=lambda item: item.get("score", 0),
            reverse=True,
        )

        candidates = []

        for acoustid_result in results:
            score = acoustid_result.get("score", 0)

            if score < 0.70:
                continue

            recordings = acoustid_result.get(
                "recordings",
                [],
            )

            for recording_item in recordings:
                recording_id = recording_item.get("id")

                if recording_id:
                    candidates.append(
                        (
                            score,
                            recording_id,
                        )
                    )

        if not candidates:
            return None

        best_match = None
        best_match_score = -1

        for acoustid_score, recording_id in candidates:
            try:
                mb_url = (
                    "https://musicbrainz.org/ws/2/recording/"
                    + urllib.parse.quote(recording_id)
                    + "?"
                    + urllib.parse.urlencode(
                        {
                            "fmt": "json",
                            "inc": (
                                "artist-credits+"
                                "releases+"
                                "release-groups"
                            ),
                        }
                    )
                )

                mb_request = urllib.request.Request(
                    mb_url,
                    headers={
                        "User-Agent": "Fang/1.0",
                        "Accept": "application/json",
                    },
                )

                with urllib.request.urlopen(
                    mb_request,
                    timeout=20,
                ) as response:
                    recording = json.loads(
                        response.read().decode("utf-8")
                    )

                title = (
                    recording.get("title") or ""
                ).strip()

                artist_credit = recording.get(
                    "artist-credit",
                    [],
                )

                artist_parts = []

                for item in artist_credit:
                    if "artist" in item:
                        name = item["artist"].get(
                            "name",
                            "",
                        )

                        if name:
                            artist_parts.append(name)

                    joinphrase = item.get(
                        "joinphrase",
                        "",
                    )

                    if joinphrase:
                        artist_parts.append(
                            joinphrase
                        )

                artist = "".join(
                    artist_parts
                ).strip()

                if not artist or not title:
                    continue

                candidate_artist = artist.lower()
                candidate_title = title.lower()

                match_score = acoustid_score

                if (
                    existing_artist
                    and candidate_artist == existing_artist
                ):
                    match_score += 2.0

                elif existing_artist:
                    continue

                if (
                    existing_title
                    and candidate_title == existing_title
                ):
                    match_score += 2.0

                elif existing_title:
                    continue

                release_groups = recording.get(
                    "release-groups",
                    [],
                )

                releases = recording.get(
                    "releases",
                    [],
                )

                album = None

                if release_groups:
                    album = (
                        release_groups[0].get("title")
                    )

                # If no release group is available,
                # prefer a dated official release.
                if not album and releases:
                    dated_official = [
                        release
                        for release in releases
                        if (
                            release.get("date")
                            and release.get("status")
                            == "Official"
                        )
                    ]

                    if dated_official:
                        dated_official.sort(
                            key=lambda release: (
                                release.get("date")
                                or ""
                            )
                        )

                        album = dated_official[0].get(
                            "title"
                        )

                    if not album:
                        album = releases[0].get(
                            "title"
                        )

                if (
                    existing_album
                    and album
                    and album.lower()
                    == existing_album
                ):
                    match_score += 1.0

                if (
                    existing_title
                    and candidate_title
                    == existing_title
                    and existing_artist
                    and candidate_artist
                    == existing_artist
                ):
                    match_score += 3.0

                if match_score > best_match_score:
                    best_match_score = match_score

                    best_match = {
                        "artist": artist,
                        "album_artist": artist,
                        "album": album,
                        "title": title,
                        "acoustid_score": acoustid_score,
                        "musicbrainz_recording_id": (
                            recording_id
                        ),
                    }

                time.sleep(1.0)

            except Exception:
                continue

        return best_match

    except Exception:
        return None


def build_proposed_operation(
    file_path,
    output_dir,
    problematic_folder="Unorganized",
    metadata=None,
):
    """
    Analyze one file and return a reviewable operation dictionary.

    This function NEVER moves or renames anything.
    """
    if metadata is None:
        metadata = extract_metadata(file_path)

    artist = metadata["artist"]
    album_artist = metadata["album_artist"]
    album = metadata["album"]
    title = metadata["title"]

    # Album Artist is preferred for folder organization.
    folder_artist = album_artist or artist

    artist_safe = sanitize_name(folder_artist) if folder_artist else ""
    album_safe = sanitize_name(album) if album else ""
    title_safe = sanitize_name(title) if title else ""

    # ---------------------------------------------------------
    # Complete metadata
    # ---------------------------------------------------------
    if artist_safe and album_safe and title_safe:
        target_dir = output_dir / artist_safe / album_safe

        # Preserve a filename that already makes sense.
        if filename_matches_title(
            file_path.name,
            title,
            artist=artist,
        ):
            target_file = target_dir / file_path.name
            action = "keep"
            status = "keep"
            reason = "Existing filename matches the track metadata."

        else:
            target_file = target_dir / f"{title_safe}{file_path.suffix}"
            action = "rename"
            status = "rename"
            reason = "Metadata provides a more useful track filename."

        return {
            "source": file_path,
            "target": target_file,
            "action": action,
            "status": status,
            "metadata_status": "complete",
            "metadata": metadata,
            "reason": reason,
        }

    # ---------------------------------------------------------
    # Partial metadata
    # ---------------------------------------------------------
    if artist_safe or album_safe or title_safe:
        target_parts = [output_dir, problematic_folder]

        if artist_safe:
            target_parts.append(artist_safe)

        if album_safe:
            target_parts.append(album_safe)

        target_dir = Path(*target_parts)

        if title_safe:
            target_file = target_dir / f"{title_safe}{file_path.suffix}"
            action = "rename"
            reason = "Partial metadata can provide a more useful filename."
        else:
            target_file = target_dir / file_path.name
            action = "move"
            reason = "Metadata is incomplete, so the original filename is preserved."

        return {
            "source": file_path,
            "target": target_file,
            "action": action,
            "status": "review",
            "metadata_status": "partial",
            "metadata": metadata,
            "reason": reason,
        }

    # ---------------------------------------------------------
    # No useful metadata
    # ---------------------------------------------------------
    target_file = output_dir / problematic_folder / file_path.name

    return {
        "source": file_path,
        "target": target_file,
        "action": "move",
        "status": "problem",
        "metadata_status": "none",
        "metadata": metadata,
        "reason": "No useful music metadata was found.",
    }


def analyze_music(
    source_dir,
    output_dir,
    problematic_folder="Unorganized",
    acoustid_api_key=None,
):
    """
    Analyze the music library without changing anything.

    Returns a list of reviewable operations.
    """
    source_dir = Path(source_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()

    audio_files = get_audio_files(source_dir)

    operations = []

    for file_path in sorted(audio_files):
        operation = build_proposed_operation(
            file_path,
            output_dir,
            problematic_folder,
        )

        metadata = operation.get("metadata", {})

        metadata_complete = all(
            metadata.get(key)
            for key in (
                "artist",
                "album",
                "title",
            )
        )

        # Only use AcoustID when embedded metadata is incomplete.
        if (
            not metadata_complete
            and acoustid_api_key
        ):
            identified = identify_with_acoustid(
                file_path,
                acoustid_api_key,
                existing_metadata=metadata,
            )

            if identified:
                for key in (
                    "artist",
                    "album_artist",
                    "album",
                    "title",
                ):
                    value = identified.get(key)

                    if value:
                        metadata[key] = value

                # Rebuild the proposed operation using the
                # metadata supplied by AcoustID.
                operation = build_proposed_operation(
                    file_path,
                    output_dir,
                    problematic_folder,
                    metadata=metadata,
                )
                operation["acoustid"] = True
                operation["acoustid_score"] = identified.get(
                    "acoustid_score"
                )
                operation["reason"] = (
                    "Missing metadata was supplemented "
                    "with an AcoustID match."
                )

            # Keep requests spaced out.
            time.sleep(0.4)

        operations.append(operation)

    return operations


def apply_operations(operations):
    """
    Apply approved operations.

    Only operations explicitly passed to this function are executed.
    """
    results = []

    for operation in operations:
        source = operation["source"]
        target = operation["target"]

        try:
            if not source.exists():
                results.append({
                    **operation,
                    "success": False,
                    "error": "Source file no longer exists.",
                })
                continue

            target.parent.mkdir(parents=True, exist_ok=True)

            final_target = target

            # Never overwrite an existing file.
            if final_target.exists() and final_target.resolve() != source.resolve():
                base_name = final_target.stem
                suffix = final_target.suffix
                counter = 1

                while final_target.exists():
                    final_target = (
                        final_target.parent
                        / f"{base_name}_{counter}{suffix}"
                    )
                    counter += 1

            shutil.move(str(source), str(final_target))

            results.append({
                **operation,
                "target": final_target,
                "success": True,
                "error": None,
            })

        except Exception as error:
            results.append({
                **operation,
                "success": False,
                "error": str(error),
            })

    return results


def print_analysis(operations, output_dir):
    """Print a command-line review of proposed changes."""
    click.echo(f"📁 Found {len(operations)} audio files")
    click.echo("🔍 REVIEW MODE - No files will be changed\n")

    counts = {
        "keep": 0,
        "rename": 0,
        "review": 0,
        "problem": 0,
    }

    for operation in operations:
        status = operation["status"]
        counts[status] += 1

        source = operation["source"]
        target = operation["target"]

        if status == "keep":
            icon = "🟢"
        elif status == "rename":
            icon = "🔵"
        elif status == "review":
            icon = "🟡"
        else:
            icon = "🔴"

        click.echo(f"{icon} {source.name}")
        click.echo(
            f"   → {target.relative_to(output_dir)}"
        )
        click.echo(
            f"   Reason: {operation['reason']}\n"
        )

    click.echo("=" * 60)
    click.echo("SUMMARY")
    click.echo("=" * 60)
    click.echo(f"Total files:              {len(operations)}")
    click.echo(f"Keep existing filename:   {counts['keep']}")
    click.echo(f"Rename suggested:         {counts['rename']}")
    click.echo(f"Needs review:             {counts['review']}")
    click.echo(f"No useful metadata:       {counts['problem']}")
    click.echo(f"Output directory:         {output_dir}")
    click.echo()
    click.echo("💡 This was a REVIEW ONLY.")
    click.echo("   No files were moved or renamed.")


@click.command()
@click.argument(
    "source",
    type=click.Path(exists=True, file_okay=False),
)
@click.argument(
    "output",
    type=click.Path(file_okay=False),
)
@click.option(
    "--apply",
    is_flag=True,
    help="Apply all proposed operations. Default is review-only.",
)
@click.option(
    "--problematic-folder",
    default="Unorganized",
    help="Folder for files with incomplete or missing metadata.",
)
def main(source, output, apply, problematic_folder):
    """
    Fang music organizer.

    SOURCE is the folder containing your music.

    OUTPUT is the folder where Fang will organize the music.

    By default Fang only analyzes and previews changes.

    Use --apply only when you intentionally want to apply
    every proposed operation.
    """
    output_dir = Path(output).expanduser().resolve()

    operations = analyze_music(
        source_dir=source,
        output_dir=output_dir,
        problematic_folder=problematic_folder,
    )

    if not operations:
        click.echo(f"❌ No audio files found in {source}")
        return

    if not apply:
        print_analysis(operations, output_dir)
        return

    click.echo(f"📁 Found {len(operations)} audio files")
    click.echo("🚀 APPLY MODE - Proposed operations WILL be applied\n")

    results = apply_operations(operations)

    successful = sum(
        1 for result in results if result["success"]
    )
    failed = len(results) - successful

    for result in results:
        if result["success"]:
            click.echo(
                f"✓ {result['source'].name}"
                f" → {result['target']}"
            )
        else:
            click.echo(
                f"✗ {result['source'].name}"
                f" → {result['error']}"
            )

    click.echo("\n" + "=" * 60)
    click.echo("SUMMARY")
    click.echo("=" * 60)
    click.echo(f"Successful operations: {successful}")
    click.echo(f"Failed operations:     {failed}")


if __name__ == "__main__":
    main()
