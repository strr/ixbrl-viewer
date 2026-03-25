#!/usr/bin/env python3

#
# Fetches the latest live utr.xml (or, optionally, the file specified on the
# command line), extracts name and symbol, and writes it to src/data/utr.json
# for inclusion in the viewer.
#

import argparse
import datetime
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import NoReturn

import requests
from lxml import etree

UTR_URL = "https://www.xbrl.org/utr/utr.xml"
UTR_NS = "http://www.xbrl.org/2009/utr"
UTR_JSON_REPO_RELPATH = Path("iXBRLViewerPlugin/viewer/src/data/utr.json")
SUPPORTED_URL_PROTOCOLS = ("http://", "https://")


def abort(message: str | BaseException, code: int = 1) -> NoReturn:
    text = (
        f"{type(message).__name__}: {message}"
        if isinstance(message, BaseException)
        else message
    )
    print(f"❌ {text}")
    raise SystemExit(code)


def network_abort(message: str, code: int = 2) -> NoReturn:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}")
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("network_error=true\n")
        raise SystemExit(0)
    abort(message, code)


def elt_name(element_name: str) -> str:
    return f"{{{UTR_NS}}}{element_name}"


def extract_text(
    utrEntry: etree._Element, element_name: str, empty_or_missing_ok: bool = False
) -> str:
    """
    Extract text content of the named element from the given UTR entry.

    Args:
        utrEntry: The UTR entry element to extract from.
        element_name: The name of the child element to extract text from.
        empty_or_missing_ok: If True, return "" if the element is missing or has no text.

    Returns:
        The text content of the named element.

    Raises: ValueError if the element is missing or has no text and
        empty_or_missing_ok is False
    """
    if (
        (el := utrEntry.find(elt_name(element_name))) is not None
        and (t := el.text) is not None
        and t.strip() != ""
    ):
        return t
    if empty_or_missing_ok:
        return ""
    raise ValueError(
        f"Element {element_name} not found or has no text. See line {utrEntry.sourceline} onwards in UTR XML."
    )


def fetch_xml(utr_url: str) -> tuple[str, etree._Element]:
    if (utr_path := Path(utr_url)).is_file():
        xml_bytes: bytes = utr_path.read_bytes()
    elif utr_url.startswith(SUPPORTED_URL_PROTOCOLS):
        try:
            with requests.get(utr_url) as res:
                res.raise_for_status()
                xml_bytes = res.content
        except requests.exceptions.RequestException as e:
            network_abort(f"Network error fetching UTR: {e}")
    else:
        abort(
            f"{utr_url} is neither a local file nor a URL with a supported protocol ({', '.join(SUPPORTED_URL_PROTOCOLS)})."
        )
    return hashlib.sha256(xml_bytes).hexdigest(), etree.fromstring(
        xml_bytes, etree.XMLParser(remove_comments=True)
    )


def parse_units(
    root: etree._Element, utr_url: str, sha256: str
) -> tuple[dict[str, dict], int]:
    units: dict[str, dict] = defaultdict(dict)
    units["_source"] = {
        "url": utr_url,
        "sha256": sha256,
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }

    print(
        "Source metadata:",
        *(f"{key:12s}: {value}" for key, value in sorted(units["_source"].items())),
        sep="\n\t",
    )

    if (units_el := root.find(elt_name("units"))) is None:
        abort("Could not find <units> element in UTR XML.")
    for e in units_el:
        if e.find(elt_name("numeratorItemType")) is not None:
            # Skip complex units
            continue

        try:
            ns = extract_text(e, "nsUnit")
            unitId = extract_text(e, "unitId")
            unitName = extract_text(e, "unitName")
        except ValueError as exc:
            abort(exc)

        unitMetadata: dict[str, str] = {"n": unitName}
        if symbol := extract_text(e, "symbol", empty_or_missing_ok=True):
            unitMetadata["s"] = symbol
        units[ns][unitId] = unitMetadata

    unit_count = sum(len(v) for k, v in units.items() if k != "_source")
    return units, unit_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch UTR XML and extract unit names and symbols."
    )
    parser.add_argument(
        "utr_url",
        nargs="?",
        default=UTR_URL,
        help=f"URL or file path of the UTR XML source. Defaults to [{UTR_URL}].",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the output file even if its content is unchanged.",
    )
    parser.add_argument(
        "-o",
        "--output-path",
        type=Path,
        default=None,
        help=f"Path to write the output JSON. Defaults to <repo-root>/{UTR_JSON_REPO_RELPATH}.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    utr_url = args.utr_url
    print(f"Fetching source: {utr_url}")

    sha256, root = fetch_xml(utr_url)
    units, unit_count = parse_units(root, utr_url, sha256)

    if args.output_path is not None:
        path = Path(args.output_path).expanduser().resolve()
    else:
        if not (
            repo_root := next(
                (p for p in Path(__file__).parents if (p / ".git").exists()), None
            )
        ):
            abort("Could not find repository root (no .git directory found).")
        path = repo_root / UTR_JSON_REPO_RELPATH

    is_unchanged = path.exists() and sha256 == json.loads(path.read_text()).get(
        "_source", {}
    ).get("sha256")

    if is_unchanged and not args.force:
        print("✅ Source UTR XML unchanged (sha256 matches): skipping write.")
        return

    with path.open("w") as f:
        json.dump(units, f, indent=2, sort_keys=True)
        f.write("\n")

    display_path = (
        path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
    )
    summary = f"Wrote {unit_count} entries to {display_path}"
    if is_unchanged:
        print(f"🪠 Source UTR XML unchanged: forced write. {summary}")
    else:
        print(f"🆕 New UTR data found: {summary}")


if __name__ == "__main__":
    main()
